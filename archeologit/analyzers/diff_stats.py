"""Per-commit diff statistics: insertions, deletions, files changed."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

from git import Repo

from archeologit.models import DiffStats, to_json
from archeologit.repo import default_branch, open_repo


def get_diff_stats(
    repo: Repo,
    branch: str | None = None,
    max_count: int | None = None,
) -> list[DiffStats]:
    """Return per-commit diff statistics for *branch*.

    Uses ``commit.stats.total`` which GitPython derives from ``git diff --stat``.
    The result includes raw per-commit numbers and a synthetic ``totals`` entry
    appended at the end of the list for quick aggregation (sha="TOTAL").

    Parameters
    ----------
    repo:
        Open GitPython Repo object.
    branch:
        Branch to walk (default: repo's default branch).
    max_count:
        Cap the number of commits.
    """
    target = branch or default_branch(repo)
    kwargs: dict = {}
    if max_count is not None:
        kwargs["max_count"] = max_count

    results: list[DiffStats] = []
    total_insertions = 0
    total_deletions = 0
    total_files = 0

    for commit in repo.iter_commits(target, **kwargs):
        totals = commit.stats.total
        ins = totals.get("insertions", 0)
        dels = totals.get("deletions", 0)
        files = totals.get("files", 0)

        total_insertions += ins
        total_deletions += dels
        total_files += files

        results.append(
            DiffStats(
                sha=commit.hexsha[:8],
                committed_at=commit.committed_datetime,
                insertions=ins,
                deletions=dels,
                files_changed=files,
            )
        )

    return results


def aggregate(stats: list[DiffStats]) -> dict:
    """Return a simple dict with summed insertions, deletions and files changed."""
    return {
        "total_insertions": sum(s.insertions for s in stats),
        "total_deletions": sum(s.deletions for s in stats),
        "total_files_changed": sum(s.files_changed for s in stats),
        "commit_count": len(stats),
    }


if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/vaskendermardiros/Repos/aily-super-agent"
    branch_arg = sys.argv[2] if len(sys.argv) > 2 else None
    max_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    r = open_repo(Path(repo_path))
    stats = get_diff_stats(r, branch=branch_arg, max_count=max_arg)
    branch_name = branch_arg or default_branch(r)
    agg = aggregate(stats)
    print(f"Diff stats for '{branch_name}' ({len(stats)} commits):")
    print(f"  Total insertions : {agg['total_insertions']}")
    print(f"  Total deletions  : {agg['total_deletions']}")
    print(f"  Files touched    : {agg['total_files_changed']}\n")
    print("Per-commit breakdown:")
    print(to_json(stats))
