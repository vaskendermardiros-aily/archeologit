"""Approximate lines-of-code evolution over time."""

from __future__ import annotations

import sys
from pathlib import Path

from git import Repo

from archeologit.models import LOCSnapshot, to_json
from archeologit.repo import default_branch, open_repo


def get_loc_over_time(
    repo: Repo,
    branch: str | None = None,
    max_count: int | None = None,
    sample_every: int = 1,
) -> list[LOCSnapshot]:
    """Return cumulative LOC snapshots over the commit history of *branch*.

    The cumulative LOC is approximated as a running total of
    ``insertions - deletions`` starting from the first (oldest) commit on the
    branch.  This is a fast approximation; it does not reflect deleted files
    whose lines were previously counted, but it accurately tracks the net
    line-count trend over time.

    Commits are returned in chronological order (oldest first).

    Parameters
    ----------
    repo:
        Open GitPython Repo object.
    branch:
        Branch to walk (default: repo's default branch).
    max_count:
        Cap the number of commits to walk (most-recent first before reversal).
    sample_every:
        Take a snapshot every N commits to reduce output size on large repos.
        1 (default) = every commit.
    """
    target = branch or default_branch(repo)
    kwargs: dict = {}
    if max_count is not None:
        kwargs["max_count"] = max_count

    # Collect in reverse (newest first) then reverse to chronological
    commits = list(repo.iter_commits(target, **kwargs))
    commits.reverse()  # oldest → newest

    results: list[LOCSnapshot] = []
    cumulative = 0

    for i, commit in enumerate(commits):
        totals = commit.stats.total
        cumulative += totals.get("insertions", 0) - totals.get("deletions", 0)

        if i % sample_every == 0 or i == len(commits) - 1:
            results.append(
                LOCSnapshot(
                    sha=commit.hexsha[:8],
                    committed_at=commit.committed_datetime,
                    cumulative_loc=cumulative,
                )
            )

    return results


if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/vaskendermardiros/Repos/aily-super-agent"
    branch_arg = sys.argv[2] if len(sys.argv) > 2 else None
    max_arg = int(sys.argv[3]) if len(sys.argv) > 3 else None
    sample_arg = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    r = open_repo(Path(repo_path))
    snapshots = get_loc_over_time(r, branch=branch_arg, max_count=max_arg, sample_every=sample_arg)
    branch_name = branch_arg or default_branch(r)
    if snapshots:
        print(
            f"LOC evolution on '{branch_name}': "
            f"{snapshots[0].cumulative_loc} → {snapshots[-1].cumulative_loc} "
            f"({len(snapshots)} snapshots)\n"
        )
    print(to_json(snapshots))
