# archeologit

Analyse how a git repository has evolved over time. Extracts high-level metrics from git history — commits, PR merges, contributor activity, folder structure changes, and lines-of-code growth — and visualises them in an interactive Streamlit dashboard.

## Features

- **Commit log** — full history for any branch with author, date, message, and changed paths
- **Merge detection** — finds PRs merged into main, supporting both classic merge commits and squash/rebase workflows (GitHub `(#NNN)` style)
- **Author stats** — per-branch contributor breakdown: commit count, lines added, lines removed
- **Folder structure evolution** — which directories appeared, changed, or were removed over time
- **Diff stats** — per-commit insertions/deletions/files-changed with aggregated totals
- **LOC over time** — cumulative net lines-of-code approximation across the repo's history
- **Streamlit dashboard** — interactive multi-tab visualisation of all the above

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (or pip)

## Setup

```bash
git clone <this repo>
cd archeologit
uv sync
```

## Workflow

### 1 — Generate a report

Run all analysers against a repo and write a `report.json`. This is the main data-collection step and can take a minute on large repos.

```bash
# Basic — analyse the repo at the given path
uv run python main.py all --repo /path/to/your/repo --output report.json

# Exclude bot/automation accounts
uv run python main.py all \
  --repo /path/to/your/repo \
  --exclude-author dependabot \
  --exclude-author ailyoperations \
  --output report.json

# Increase folder-structure depth (default is 4)
uv run python main.py all \
  --repo /path/to/your/repo \
  --folder-depth 5 \
  --output report.json

# Limit history to the last 500 commits (faster, good for a quick look)
uv run python main.py all \
  --repo /path/to/your/repo \
  --max 500 \
  --output report.json
```

> **Tip:** run `uv run python main.py --help` or append `--help` to any subcommand to see all available flags.

### 2 — Launch the dashboard

```bash
uv run streamlit run app.py
```

Pick the `report.json` file in the sidebar and explore.

---

## CLI reference

All commands share a common set of flags:

```
uv run python main.py [OPTIONS] <command>
```

### Options

| Flag | Description |
|------|-------------|
| `--repo PATH` | Path to the git repo to analyse |
| `--branch NAME` | Branch to analyse (default: repo's default branch) |
| `--max N` | Cap the number of commits walked (useful for large repos) |
| `--exclude-author NAME` | Exclude commits by this author; repeatable |
| `--folder-depth N` | Directory depth for folder-structure analysis (default: 4) |
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
uv run python main.py folders --folder-depth 4 --max 200
```

#### `diffstats` — insertions / deletions per commit

```bash
uv run python main.py diffstats
uv run python main.py diffstats --max 50 --json
```

#### `loc` — lines-of-code over time

```bash
uv run python main.py loc
uv run python main.py loc --max 500
```

#### `all` — run everything and write a report

```bash
uv run python main.py all
uv run python main.py all --repo /path/to/any/repo --output my_report.json
uv run python main.py all --exclude-author ailyoperations --exclude-author dependabot
```

### Run individual analysers directly

```bash
uv run python -m archeologit.repo
uv run python -m archeologit.analyzers.commit_log . main 20
uv run python -m archeologit.analyzers.merges . main
uv run python -m archeologit.analyzers.authors . main
uv run python -m archeologit.analyzers.folders . main 2 50
uv run python -m archeologit.analyzers.diff_stats . main 30
uv run python -m archeologit.analyzers.loc . main 100 5
```

---

## Dashboard

Load a `report.json` in the sidebar. A global **date range slider** and **exclude authors** multiselect apply filters across all tabs.

### 📊 Overview
- Key metric cards: total commits, contributors, PRs merged, net LOC
- **LOC over time** line chart with vertical markers at every PR merge (hover shows PR title)

### ⚡ Activity
- **Commit velocity** — commits per month bar chart
- **Lines added vs removed** — stacked bar chart
- **Commit size** scatter plot (log/linear y-axis toggle)
- **Commit types** donut chart (feat, fix, refactor, chore, …)

### 👥 Contributors
- **Leaderboard** — ranked by lines added, commits, or net LOC
- **Active contributors per month** — unique authors over time
- **Commits per author** — stacked area chart per contributor

### 📁 Codebase
- **Top directories by churn** — horizontal bar chart, filterable by change type (added/modified/deleted)
- **Directory activity heatmap** — directory × month grid coloured by commit count

### 🗂 PR Explorer
Step through every merged PR with a slider:
- Metadata chips: branch type badge (feat/fix/refactor/…), PR number, merge date, main author, lines changed (green/red), files changed
- **Sunburst chart** — directories touched by the PR, coloured by change type, up to 4 levels deep
- **Change summary table** — files added, modified, deleted
- Full PR description as markdown
- **Directory debut timeline** — scatter plot of when each directory first appeared in the repo

### 🔀 PRs & Merges
- PRs merged over time
- PR size scatter plot (lines changed)
- **Merge style** donut (classic merge vs squash)
- Merged PRs table

### 🫧 Cast of Characters
Beeswarm bubble chart of every contributor:
- **X axis** — first commit date (timeline)
- **Bubble size** — lines added, power-scaled (exponent 0.35) so small contributors are visibly smaller without disappearing
- **Bubble colour** — dominant commit type
- **Labels** — first name / handle printed inside each bubble
- Hover shows name, commits, lines added/removed
- **Contributor details** table below the chart

---

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
    "aggregate": { "total_insertions": 0, "total_deletions": 0, "..." },
    "per_commit": [ ... ]
  },
  "loc_over_time": [ ... ]
}
```

## Project layout

```
archeologit/
├── __init__.py
├── models.py              # Shared dataclasses (CommitInfo, MergeEvent, …)
├── repo.py                # Repo open + branch helpers
└── analyzers/
    ├── commit_log.py
    ├── merges.py
    ├── authors.py
    ├── folders.py
    ├── diff_stats.py
    └── loc.py
main.py                    # CLI entrypoint
app.py                     # Streamlit dashboard
```
