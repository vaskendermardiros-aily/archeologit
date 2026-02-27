"""CLI entrypoint for archeologit.

Usage:
    python main.py [--repo PATH] [--branch BRANCH] [--max N] [--output FILE] <command>

Commands:
    log          Commit log for a branch
    merges       Merge events into the default/specified branch
    authors      Author stats per branch (or a single branch)
    folders      Folder-level structure changes
    diffstats    Per-commit insertions/deletions/files-changed
    loc          Cumulative LOC approximation over time
    all          Run all analyzers and write a combined JSON report

Options:
    --repo PATH              Path to the git repository (default: aily-super-agent)
    --branch NAME            Branch to analyse (default: repo default branch)
    --max N                  Cap commits per analyzer (default: unlimited)
    --exclude-author NAME    Exclude commits by this author (repeatable)
    --output FILE            Write JSON output to FILE (default: print to stdout)
    --json                   Force JSON output even for commands that normally print a summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archeologit.analyzers import (
    get_branch_authors,
    get_commit_log,
    get_diff_stats,
    get_folder_changes,
    get_loc_over_time,
    get_merges_to_main,
)
from archeologit.analyzers.diff_stats import aggregate as diff_aggregate
from archeologit.models import to_json
from archeologit.repo import default_branch, open_repo


def _exclude(items, exclude_authors: list[str]):
    """Filter out items whose author_name is in *exclude_authors* (case-insensitive)."""
    if not exclude_authors:
        return items
    lowered = {a.lower() for a in exclude_authors}
    return [i for i in items if getattr(i, "author_name", "").lower() not in lowered]


def cmd_log(args: argparse.Namespace) -> None:
    repo = open_repo(args.repo)
    log = get_commit_log(repo, branch=args.branch, max_count=args.max)
    log = _exclude(log, args.exclude_authors)
    if args.json or args.output:
        _emit(to_json(log), args.output)
    else:
        branch = args.branch or default_branch(repo)
        print(f"Commit log: '{branch}' — {len(log)} commits\n")
        for c in log[:20]:
            print(f"  {c.short_sha}  {c.committed_at.date()}  {c.author_name:<20}  {c.message[:60]!r}")
        if len(log) > 20:
            print(f"  ... and {len(log) - 20} more")


def cmd_merges(args: argparse.Namespace) -> None:
    repo = open_repo(args.repo)
    merges = get_merges_to_main(repo, branch=args.branch, max_count=args.max)
    if args.json or args.output:
        _emit(to_json(merges), args.output)
    else:
        branch = args.branch or default_branch(repo)
        classic = sum(1 for m in merges if m.merge_style == "classic")
        squash = sum(1 for m in merges if m.merge_style == "squash")
        print(f"Merges into '{branch}': {len(merges)} event(s) ({classic} classic, {squash} squash/rebase)\n")
        for m in merges:
            pr = f"PR #{m.pr_number}" if m.pr_number else m.merged_branch
            style = f"[{m.merge_style}]"
            print(f"  {m.merge_commit_sha}  {m.merged_at.date()}  {style:<10} ← {pr:<15}  {m.message[:50]!r}")


def cmd_authors(args: argparse.Namespace) -> None:
    repo = open_repo(args.repo)
    branches_arg = [args.branch] if args.branch else None
    data = get_branch_authors(repo, branches=branches_arg, max_count=args.max)
    if args.exclude_authors:
        lowered = {a.lower() for a in args.exclude_authors}
        for ba in data:
            ba.authors = [a for a in ba.authors if a.author_name.lower() not in lowered]
    if args.json or args.output:
        _emit(to_json(data), args.output)
    else:
        for ba in data:
            print(f"Branch: {ba.branch_name} — {len(ba.authors)} contributor(s)")
            for a in ba.authors:
                print(
                    f"  {a.author_name:<25}  commits={a.commit_count:<5}"
                    f"  +{a.lines_added}/-{a.lines_removed}"
                )
            print()


def cmd_folders(args: argparse.Namespace) -> None:
    repo = open_repo(args.repo)
    changes = get_folder_changes(repo, branch=args.branch, max_count=args.max)
    if args.json or args.output:
        _emit(to_json(changes), args.output)
    else:
        branch = args.branch or default_branch(repo)
        print(f"Folder changes on '{branch}': {len(changes)} event(s)\n")
        for fc in changes[:40]:
            print(f"  {fc.sha}  {fc.committed_at.date()}  {fc.change_type:<10}  {fc.directory}")
        if len(changes) > 40:
            print(f"  ... and {len(changes) - 40} more")


def cmd_diffstats(args: argparse.Namespace) -> None:
    repo = open_repo(args.repo)
    stats = get_diff_stats(repo, branch=args.branch, max_count=args.max)
    agg = diff_aggregate(stats)
    if args.json or args.output:
        _emit(
            json.dumps({"aggregate": agg, "per_commit": json.loads(to_json(stats))}, indent=2),
            args.output,
        )
    else:
        branch = args.branch or default_branch(repo)
        print(f"Diff stats for '{branch}' ({agg['commit_count']} commits):")
        print(f"  Total insertions : {agg['total_insertions']}")
        print(f"  Total deletions  : {agg['total_deletions']}")
        print(f"  Files touched    : {agg['total_files_changed']}\n")
        print("  sha       date        +ins    -del  files")
        for s in stats[:20]:
            print(f"  {s.sha}  {s.committed_at.date()}  +{s.insertions:<6} -{s.deletions:<6} {s.files_changed}")
        if len(stats) > 20:
            print(f"  ... and {len(stats) - 20} more")


def cmd_loc(args: argparse.Namespace) -> None:
    repo = open_repo(args.repo)
    snapshots = get_loc_over_time(repo, branch=args.branch, max_count=args.max)
    if args.json or args.output:
        _emit(to_json(snapshots), args.output)
    else:
        branch = args.branch or default_branch(repo)
        if snapshots:
            print(
                f"LOC evolution on '{branch}': "
                f"{snapshots[0].cumulative_loc} → {snapshots[-1].cumulative_loc} "
                f"({len(snapshots)} snapshots)\n"
            )
        print("  sha       date        cumulative_loc")
        for s in snapshots[::max(1, len(snapshots) // 20)]:
            print(f"  {s.sha}  {s.committed_at.date()}  {s.cumulative_loc}")


def cmd_all(args: argparse.Namespace) -> None:
    repo = open_repo(args.repo)
    branch = args.branch or default_branch(repo)
    branches_arg = [branch] if args.branch else None

    print(f"Running all analyzers on '{repo.working_dir}' (branch: {branch}) …")

    log = get_commit_log(repo, branch=branch, max_count=args.max)
    log = _exclude(log, args.exclude_authors)
    print(f"  commit_log    : {len(log)} commits")

    merges = get_merges_to_main(repo, branch=branch, max_count=args.max)
    print(f"  merges        : {len(merges)} merge events")

    authors = get_branch_authors(repo, branches=branches_arg, max_count=args.max)
    if args.exclude_authors:
        lowered = {a.lower() for a in args.exclude_authors}
        for ba in authors:
            ba.authors = [a for a in ba.authors if a.author_name.lower() not in lowered]
    print(f"  authors       : analysed {len(authors)} branch(es)")

    folders = get_folder_changes(repo, branch=branch, max_count=args.max)
    print(f"  folders       : {len(folders)} folder-change events")

    diff_stats = get_diff_stats(repo, branch=branch, max_count=args.max)
    agg = diff_aggregate(diff_stats)
    print(f"  diff_stats    : +{agg['total_insertions']} / -{agg['total_deletions']} lines total")

    loc = get_loc_over_time(repo, branch=branch, max_count=args.max)
    if loc:
        print(f"  loc           : {loc[0].cumulative_loc} → {loc[-1].cumulative_loc} (net LOC)")

    report = {
        "repo": str(repo.working_dir),
        "branch": branch,
        "commit_log": json.loads(to_json(log)),
        "merges": json.loads(to_json(merges)),
        "authors": json.loads(to_json(authors)),
        "folder_changes": json.loads(to_json(folders)),
        "diff_stats": {
            "aggregate": agg,
            "per_commit": json.loads(to_json(diff_stats)),
        },
        "loc_over_time": json.loads(to_json(loc)),
    }

    output_path = args.output or "report.json"
    Path(output_path).write_text(json.dumps(report, indent=2))
    print(f"\nFull report written to: {output_path}")


def _emit(text: str, output_path: str | None) -> None:
    if output_path:
        Path(output_path).write_text(text)
        print(f"Output written to: {output_path}")
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    # Shared flags available on every subcommand (and the top-level parser)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default="/Users/vaskendermardiros/Repos/aily-super-agent", metavar="PATH", help="Path to the git repo (default: aily-super-agent)")
    common.add_argument("--branch", default=None, metavar="NAME", help="Branch to analyse")
    common.add_argument("--max", type=int, default=None, metavar="N", help="Cap commits per analyzer")
    common.add_argument(
        "--exclude-author",
        dest="exclude_authors",
        metavar="NAME",
        action="append",
        default=[],
        help="Exclude commits by this author name (repeatable, e.g. --exclude-author ailyoperations)",
    )
    common.add_argument("--output", default=None, metavar="FILE", help="Write JSON output to FILE")
    common.add_argument("--json", action="store_true", help="Force JSON output")

    parser = argparse.ArgumentParser(
        prog="archeologit",
        description="Analyse a git repository's evolution over time.",
        parents=[common],
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("log", parents=[common], help="Commit log for a branch")
    sub.add_parser("merges", parents=[common], help="Merge events into the default/specified branch")
    sub.add_parser("authors", parents=[common], help="Author stats per branch")
    sub.add_parser("folders", parents=[common], help="Folder-level structure changes")
    sub.add_parser("diffstats", parents=[common], help="Per-commit insertions/deletions/files-changed")
    sub.add_parser("loc", parents=[common], help="Cumulative LOC approximation over time")
    sub.add_parser("all", parents=[common], help="Run all analyzers and write a combined JSON report")

    return parser


_COMMANDS = {
    "log": cmd_log,
    "merges": cmd_merges,
    "authors": cmd_authors,
    "folders": cmd_folders,
    "diffstats": cmd_diffstats,
    "loc": cmd_loc,
    "all": cmd_all,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
