# archeologit

Analyse how a git repository has evolved over time. Extracts high-level metrics from git history — commits, PR merges, contributor activity, folder structure changes, and lines-of-code growth — and outputs structured data ready for further analysis or visualisation.

## Features

- **Commit log** — full history for any branch with author, date, message, and changed paths
- **Merge detection** — finds PRs merged into main, supporting both classic merge commits and squash/rebase workflows (GitHub `(#NNN)` style)
- **Author stats** — per-branch contributor breakdown: commit count, lines added, lines removed
- **Folder structure evolution** — which directories appeared, changed, or were removed over time
- **Diff stats** — per-commit insertions/deletions/files-changed with aggregated totals
- **LOC over time** — cumulative net lines-of-code approximation across the repo's history

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (or pip)

## Setup

```bash
git clone <this repo>
cd archeologit
uv sync
```

## Usage

All commands share a common set of flags that can be placed before or after the subcommand:

```
uv run python main.py [OPTIONS] <command>
```

### Options

| Flag | Description |
|------|-------------|
| `--repo PATH` | Path to the git repo to analyse (default: `aily-super-agent`) |
| `--branch NAME` | Branch to analyse (default: repo's default branch) |
| `--max N` | Cap the number of commits walked (useful for large repos) |
| `--exclude-author NAME` | Exclude commits by this author; repeatable |
| `--output FILE` | Write JSON output to a file instead of stdout |
| `--json` | Force JSON output for commands that normally print a summary |

### Commands

#### `log` — commit history

```bash
uv run python main.py log
uv run python main.py log --max 50 --exclude-author ailyoperations
uv run python main.py log --branch develop --json
```

#### `merges` — PRs merged into main

Detects both classic merge commits (2-parent) and squash/rebase merges (GitHub `(#NNN)` in message).

```bash
uv run python main.py merges
uv run python main.py merges --max 100
```

#### `authors` — contributor stats per branch

```bash
uv run python main.py authors
uv run python main.py authors --branch main --exclude-author ailyoperations
```

#### `folders` — directory-level structure changes

```bash
uv run python main.py folders
uv run python main.py folders --max 200
```

#### `diffstats` — insertions / deletions per commit

```bash
uv run python main.py diffstats
uv run python main.py diffstats --max 50 --json
```

#### `loc` — lines-of-code over time

Approximate cumulative LOC (net insertions − deletions) from the first commit to the latest.

```bash
uv run python main.py loc
uv run python main.py loc --max 500
```

#### `all` — run everything and write a report

Runs all six analyzers and writes a combined `report.json` (or a custom path via `--output`).

```bash
uv run python main.py all
uv run python main.py all --repo /path/to/any/repo --output my_report.json
uv run python main.py all --exclude-author ailyoperations --exclude-author dependabot
```

### Run individual analyzers directly

Each analyzer module is also runnable on its own for quick inspection:

```bash
uv run python -m archeologit.repo
uv run python -m archeologit.analyzers.commit_log . main 20
uv run python -m archeologit.analyzers.merges . main
uv run python -m archeologit.analyzers.authors . main
uv run python -m archeologit.analyzers.folders . main 2 50
uv run python -m archeologit.analyzers.diff_stats . main 30
uv run python -m archeologit.analyzers.loc . main 100 5
```

Arguments (all optional, positional): `repo_path  branch  max_count  [extra]`

## Output format

All commands produce JSON-serialisable dataclasses. The `all` report structure:

```json
{
  "repo": "/path/to/repo",
  "branch": "main",
  "commit_log": [ ... ],
  "merges": [ ... ],
  "authors": [ ... ],
  "folder_changes": [ ... ],
  "diff_stats": {
    "aggregate": { "total_insertions": 0, "total_deletions": 0, ... },
    "per_commit": [ ... ]
  },
  "loc_over_time": [ ... ]
}
```

## Project layout

```
archeologit/
├── __init__.py
├── models.py              # Shared dataclasses (CommitInfo, MergeEvent, ...)
├── repo.py                # Repo open + branch helpers
└── analyzers/
    ├── commit_log.py
    ├── merges.py
    ├── authors.py
    ├── folders.py
    ├── diff_stats.py
    └── loc.py
main.py                    # CLI entrypoint
```

## Roadmap

- Streamlit dashboard for interactive visualisation
- Date range filtering (`--since`, `--until`)
- Remote repo support (clone on the fly)
