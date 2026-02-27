"""Shared dataclasses for all analyzer outputs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def to_json(data: Any, indent: int = 2) -> str:
    if isinstance(data, list):
        serializable = [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in data]
    elif hasattr(data, "__dataclass_fields__"):
        serializable = asdict(data)
    else:
        serializable = data
    return json.dumps(serializable, indent=indent, default=_default_serializer)


@dataclass
class CommitInfo:
    sha: str
    short_sha: str
    author_name: str
    author_email: str
    committed_at: datetime
    message: str
    changed_paths: list[str] = field(default_factory=list)


@dataclass
class MergeEvent:
    merge_commit_sha: str
    merged_at: datetime
    message: str
    merged_branch: str  # branch name if resolvable, PR number for squash merges, or second-parent sha
    pr_number: int | None  # set for squash/rebase PRs detected via "(#NNN)" in message
    merge_style: str  # "classic" (2-parent merge commit) | "squash" (single commit with PR ref)


@dataclass
class AuthorStats:
    author_name: str
    author_email: str
    commit_count: int
    lines_added: int
    lines_removed: int


@dataclass
class BranchAuthors:
    branch_name: str
    authors: list[AuthorStats] = field(default_factory=list)


@dataclass
class FolderChange:
    sha: str
    committed_at: datetime
    directory: str
    change_type: str  # "added", "removed", "modified", "renamed"


@dataclass
class DiffStats:
    sha: str
    committed_at: datetime
    insertions: int
    deletions: int
    files_changed: int


@dataclass
class LOCSnapshot:
    sha: str
    committed_at: datetime
    cumulative_loc: int  # running insertions - deletions from repo start
