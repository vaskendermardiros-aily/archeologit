"""Thin helpers for opening a repo and querying its structure."""

from __future__ import annotations

from pathlib import Path

from git import InvalidGitRepositoryError, Repo


def open_repo(path: str | Path = ".") -> Repo:
    """Open a git repository at *path* (or any of its parents)."""
    try:
        repo = Repo(str(path), search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise ValueError(f"No git repository found at or above: {path}")
    return repo


def default_branch(repo: Repo) -> str:
    """Return 'main' or 'master' depending on what exists, else the first branch."""
    names = {ref.name.split("/")[-1] for ref in repo.references}
    for candidate in ("main", "master"):
        if candidate in names:
            return candidate
    branches = list(repo.branches)
    if not branches:
        raise ValueError("Repository has no branches.")
    return branches[0].name


def list_branches(repo: Repo, remote: bool = False) -> list[str]:
    """Return local branch names. Include remote-tracking refs if *remote* is True."""
    if remote:
        return [ref.name for ref in repo.remote().refs]
    return [branch.name for branch in repo.branches]


def resolve_ref_to_branch(repo: Repo, sha: str) -> str | None:
    """Try to find a branch name whose tip matches *sha*."""
    for ref in repo.references:
        if ref.commit.hexsha == sha:
            return ref.name.split("/")[-1]
    return None


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "/Users/vaskendermardiros/Repos/aily-super-agent"
    r = open_repo(path)
    main_branch = default_branch(r)
    branches = list_branches(r)
    print(f"Repo: {r.working_dir}")
    print(f"Default branch: {main_branch}")
    print(f"Local branches ({len(branches)}): {', '.join(branches)}")
