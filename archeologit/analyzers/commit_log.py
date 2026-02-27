"""Extract a flat commit log from a branch."""

from __future__ import annotations

import sys
from pathlib import Path

from git import Repo

from archeologit.models import CommitInfo, to_json
from archeologit.repo import default_branch, open_repo


def get_commit_log(
    repo: Repo,
    branch: str | None = None,
    max_count: int | None = None,
    include_paths: bool = True,
) -> list[CommitInfo]:
    """Return a list of :class:`CommitInfo` for *branch* (default: default branch).

    Parameters
    ----------
    repo:
        Open GitPython Repo object.
    branch:
        Branch name to walk. Falls back to the repo's default branch.
    max_count:
        Cap the number of commits returned (most-recent first).
    include_paths:
        When True, populate ``changed_paths`` with the list of file paths
        touched by each commit. Slightly slower due to stat computation.
    """
    target = branch or default_branch(repo)
    kwargs: dict = {}
    if max_count is not None:
        kwargs["max_count"] = max_count

    results: list[CommitInfo] = []
    for commit in repo.iter_commits(target, **kwargs):
        paths: list[str] = []
        if include_paths:
            paths = list(commit.stats.files.keys())

        results.append(
            CommitInfo(
                sha=commit.hexsha,
                short_sha=commit.hexsha[:8],
                author_name=commit.author.name or "",
                author_email=commit.author.email or "",
                committed_at=commit.committed_datetime,
                message=commit.message.strip(),
                changed_paths=paths,
            )
        )
    return results


if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/vaskendermardiros/Repos/aily-super-agent"
    branch_arg = sys.argv[2] if len(sys.argv) > 2 else None
    max_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    r = open_repo(Path(repo_path))
    log = get_commit_log(r, branch=branch_arg, max_count=max_arg)
    print(f"Showing {len(log)} commits on '{branch_arg or default_branch(r)}':\n")
    print(to_json(log))
