"""Detect merge events into the default/main branch.

Two merge styles are supported:

- **classic**: a commit with 2+ parents (traditional ``git merge``).
- **squash**: a single-parent commit whose message contains a GitHub/GitLab
  PR reference like ``(#1055)`` or ``!42``.  This is the common pattern when
  teams use "Squash and merge" or "Rebase and merge" on GitHub/GitLab.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from git import Repo

from archeologit.models import MergeEvent, to_json
from archeologit.repo import default_branch, open_repo, resolve_ref_to_branch

# Matches GitHub "(#123)" or GitLab "!123" PR/MR references in commit messages
_PR_RE = re.compile(r"\(#(\d+)\)|(?:^|\s)!(\d+)(?:\s|$)")


def _extract_pr_number(message: str) -> int | None:
    m = _PR_RE.search(message)
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def get_merges_to_main(
    repo: Repo,
    branch: str | None = None,
    max_count: int | None = None,
    include_squash: bool = True,
) -> list[MergeEvent]:
    """Return merge events on *branch* (the integration branch, e.g. main/master).

    Detects both merge styles:

    - **classic** — commits with two or more parents (``git merge``).
      The second parent is resolved to a branch name where possible.
    - **squash/rebase** — single-parent commits on *branch* whose message
      contains a PR/MR reference such as ``(#1055)``.  Enabled when
      *include_squash* is True (default).

    Parameters
    ----------
    repo:
        Open GitPython Repo object.
    branch:
        The integration branch to inspect (default: repo's default branch).
    max_count:
        Cap the total commits to walk.
    include_squash:
        Also detect squash/rebase PRs via PR number in commit message.
    """
    target = branch or default_branch(repo)
    kwargs: dict = {}
    if max_count is not None:
        kwargs["max_count"] = max_count

    # sha → branch-name lookup for classic merge resolution
    sha_to_branch: dict[str, str] = {}
    for ref in repo.references:
        sha_to_branch[ref.commit.hexsha] = ref.name.split("/")[-1]

    results: list[MergeEvent] = []
    for commit in repo.iter_commits(target, **kwargs):
        message = commit.message.strip()

        if len(commit.parents) >= 2:
            # Classic merge commit
            merged_tip = commit.parents[1]
            merged_branch = (
                sha_to_branch.get(merged_tip.hexsha)
                or resolve_ref_to_branch(repo, merged_tip.hexsha)
                or merged_tip.hexsha[:8]
            )
            results.append(
                MergeEvent(
                    merge_commit_sha=commit.hexsha[:8],
                    merged_at=commit.committed_datetime,
                    message=message,
                    merged_branch=merged_branch,
                    pr_number=_extract_pr_number(message),
                    merge_style="classic",
                )
            )

        elif include_squash:
            pr_number = _extract_pr_number(message)
            if pr_number is not None:
                results.append(
                    MergeEvent(
                        merge_commit_sha=commit.hexsha[:8],
                        merged_at=commit.committed_datetime,
                        message=message,
                        merged_branch=f"PR #{pr_number}",
                        pr_number=pr_number,
                        merge_style="squash",
                    )
                )

    return results


if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/vaskendermardiros/Repos/aily-super-agent"
    branch_arg = sys.argv[2] if len(sys.argv) > 2 else None

    r = open_repo(Path(repo_path))
    merges = get_merges_to_main(r, branch=branch_arg)
    branch_name = branch_arg or default_branch(r)
    classic = sum(1 for m in merges if m.merge_style == "classic")
    squash = sum(1 for m in merges if m.merge_style == "squash")
    print(f"Found {len(merges)} merge event(s) on '{branch_name}' ({classic} classic, {squash} squash/rebase):\n")
    print(to_json(merges))
