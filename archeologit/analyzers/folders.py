"""Track directory-level structure changes over time."""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

from git import Repo

from archeologit.models import FolderChange, to_json
from archeologit.repo import default_branch, open_repo


def _extract_directories(path_str: str, depth: int = 2) -> list[str]:
    """Return the ancestor directory names up to *depth* levels for a file path."""
    parts = PurePosixPath(path_str).parts
    dirs: list[str] = []
    # parts[-1] is the filename itself; everything before is a directory level
    for i in range(1, min(len(parts), depth + 1)):
        dirs.append(str(PurePosixPath(*parts[:i])))
    return dirs


def get_folder_changes(
    repo: Repo,
    branch: str | None = None,
    depth: int = 2,
    max_count: int | None = None,
) -> list[FolderChange]:
    """Return directory-level change events extracted from commit diffs.

    For each commit, diff against its first parent to find which paths changed.
    Each changed file path is decomposed into its ancestor directories (up to
    *depth* levels), and a :class:`FolderChange` is emitted for every unique
    (commit, directory, change_type) combination.

    Parameters
    ----------
    repo:
        Open GitPython Repo object.
    branch:
        Branch to walk (default: repo's default branch).
    depth:
        How many directory levels to track (1 = top-level only, 2 = two levels).
    max_count:
        Cap the number of commits to walk.
    """
    target = branch or default_branch(repo)
    kwargs: dict = {}
    if max_count is not None:
        kwargs["max_count"] = max_count

    # Map GitPython diff change_type codes to human-readable labels
    _change_map = {
        "A": "added",
        "D": "removed",
        "M": "modified",
        "R": "renamed",
        "C": "copied",
        "T": "type-changed",
    }

    results: list[FolderChange] = []
    for commit in repo.iter_commits(target, **kwargs):
        if not commit.parents:
            # Initial commit: diff vs empty tree
            diffs = commit.diff(None)
        else:
            diffs = commit.parents[0].diff(commit)

        seen: set[tuple[str, str]] = set()
        for diff in diffs:
            change_label = _change_map.get(diff.change_type, diff.change_type)
            # Use a_path for deletions, b_path for additions/modifications
            path = diff.b_path or diff.a_path or ""
            if not path:
                continue
            for directory in _extract_directories(path, depth=depth):
                key = (directory, change_label)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    FolderChange(
                        sha=commit.hexsha[:8],
                        committed_at=commit.committed_datetime,
                        directory=directory,
                        change_type=change_label,
                    )
                )

    return results


if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/vaskendermardiros/Repos/aily-super-agent"
    branch_arg = sys.argv[2] if len(sys.argv) > 2 else None
    depth_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    max_arg = int(sys.argv[4]) if len(sys.argv) > 4 else 50

    r = open_repo(Path(repo_path))
    changes = get_folder_changes(r, branch=branch_arg, depth=depth_arg, max_count=max_arg)
    branch_name = branch_arg or default_branch(r)
    print(f"Found {len(changes)} folder change event(s) on '{branch_name}' (depth={depth_arg}):\n")
    print(to_json(changes))
