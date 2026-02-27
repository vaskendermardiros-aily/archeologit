"""Aggregate author contribution stats per branch."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from git import Repo

from archeologit.models import AuthorStats, BranchAuthors, to_json
from archeologit.repo import default_branch, list_branches, open_repo


def get_branch_authors(
    repo: Repo,
    branches: list[str] | None = None,
    max_count: int | None = None,
) -> list[BranchAuthors]:
    """Return per-branch author stats (commits + lines added/removed).

    Parameters
    ----------
    repo:
        Open GitPython Repo object.
    branches:
        Explicit list of branch names to analyse. Defaults to all local branches.
    max_count:
        Cap commits walked per branch (most-recent first).
    """
    target_branches = branches or list_branches(repo)
    kwargs: dict = {}
    if max_count is not None:
        kwargs["max_count"] = max_count

    results: list[BranchAuthors] = []
    for branch_name in target_branches:
        # author_email → running totals
        stats: dict[str, dict] = defaultdict(
            lambda: {"name": "", "commits": 0, "added": 0, "removed": 0}
        )

        for commit in repo.iter_commits(branch_name, **kwargs):
            key = commit.author.email or commit.author.name or "unknown"
            entry = stats[key]
            entry["name"] = commit.author.name or key
            entry["commits"] += 1
            entry["added"] += commit.stats.total["insertions"]
            entry["removed"] += commit.stats.total["deletions"]

        authors = [
            AuthorStats(
                author_name=v["name"],
                author_email=email,
                commit_count=v["commits"],
                lines_added=v["added"],
                lines_removed=v["removed"],
            )
            for email, v in sorted(stats.items(), key=lambda x: -x[1]["commits"])
        ]
        results.append(BranchAuthors(branch_name=branch_name, authors=authors))

    return results


if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/vaskendermardiros/Repos/aily-super-agent"
    branch_arg = sys.argv[2] if len(sys.argv) > 2 else None
    branches_arg = [branch_arg] if branch_arg else None

    r = open_repo(Path(repo_path))
    data = get_branch_authors(r, branches=branches_arg)
    print(f"Author stats across {len(data)} branch(es):\n")
    print(to_json(data))
