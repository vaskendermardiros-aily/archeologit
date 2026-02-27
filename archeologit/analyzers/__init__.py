"""Analyzer functions — each returns plain dataclass-based structures."""

# Lazy re-exports: import only when the package itself is imported (not when
# individual modules are run via `python -m`), which prevents a harmless but
# noisy RuntimeWarning from runpy.
from importlib import import_module as _im


def __getattr__(name: str):  # noqa: N807
    _map = {
        "get_commit_log": ("commit_log", "get_commit_log"),
        "get_merges_to_main": ("merges", "get_merges_to_main"),
        "get_branch_authors": ("authors", "get_branch_authors"),
        "get_folder_changes": ("folders", "get_folder_changes"),
        "get_diff_stats": ("diff_stats", "get_diff_stats"),
        "get_loc_over_time": ("loc", "get_loc_over_time"),
    }
    if name in _map:
        mod_name, attr = _map[name]
        mod = _im(f"archeologit.analyzers.{mod_name}")
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "get_commit_log",
    "get_merges_to_main",
    "get_branch_authors",
    "get_folder_changes",
    "get_diff_stats",
    "get_loc_over_time",
]
