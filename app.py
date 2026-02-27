"""archeologit — interactive Streamlit dashboard."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="archeologit",
    page_icon="🏺",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_data
def load_report(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


_COMMIT_TYPE_RE = re.compile(
    r"^(feat|fix|chore|refactor|test|docs|ci|perf|build|style|revert)\b",
    re.IGNORECASE,
)

def commit_type(message: str) -> str:
    m = _COMMIT_TYPE_RE.match(message.strip())
    return m.group(1).lower() if m else "other"


COMMIT_TYPE_COLORS: dict[str, str] = {
    "feat":     "#2ecc71",
    "fix":      "#e74c3c",
    "refactor": "#3498db",
    "chore":    "#95a5a6",
    "test":     "#9b59b6",
    "docs":     "#f39c12",
    "ci":       "#1abc9c",
    "perf":     "#e67e22",
    "build":    "#7f8c8d",
    "style":    "#bdc3c7",
    "revert":   "#c0392b",
    "other":    "#95a5a6",
}


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Sidebar — load report
# ---------------------------------------------------------------------------
st.sidebar.title("🏺 archeologit")
st.sidebar.markdown("Git repository evolution explorer")

default_report = Path(__file__).parent / "report.json"
report_path = st.sidebar.text_input("Report file", value=str(default_report))

try:
    report = load_report(report_path)
except FileNotFoundError:
    st.error(f"Report not found: `{report_path}`\n\nRun `python main.py all` to generate it.")
    st.stop()

repo_name = Path(report.get("repo", report_path)).name
branch = report.get("branch", "main")

st.sidebar.markdown(f"**Repo:** `{repo_name}`  **Branch:** `{branch}`")
st.sidebar.divider()

# ---------------------------------------------------------------------------
# Build base DataFrames (unfiltered) so we can derive the slider bounds
# ---------------------------------------------------------------------------

df_commits = pd.DataFrame(report.get("commit_log", []))
df_merges  = pd.DataFrame(report.get("merges", []))
df_folders = pd.DataFrame(report.get("folder_changes", []))
df_diff    = pd.DataFrame(report.get("diff_stats", {}).get("per_commit", []))
df_loc     = pd.DataFrame(report.get("loc_over_time", []))

for df, col in [
    (df_commits, "committed_at"),
    (df_merges,  "merged_at"),
    (df_folders, "committed_at"),
    (df_diff,    "committed_at"),
    (df_loc,     "committed_at"),
]:
    if not df.empty and col in df.columns:
        df[col] = pd.to_datetime(df[col], utc=True)

# Derive global date bounds from commits
if df_commits.empty:
    st.error("No commit data in report.")
    st.stop()

df_commits = df_commits.sort_values("committed_at")
global_min = df_commits["committed_at"].min().to_pydatetime().date()
global_max = df_commits["committed_at"].max().to_pydatetime().date()

# ---------------------------------------------------------------------------
# Sidebar — date range slider
# ---------------------------------------------------------------------------
st.sidebar.markdown("**Date range**")
date_range = st.sidebar.slider(
    "Select range",
    min_value=global_min,
    max_value=global_max,
    value=(global_min, global_max),
    format="YYYY-MM-DD",
    label_visibility="collapsed",
)
start_date, end_date = date_range

# ---------------------------------------------------------------------------
# Sidebar — exclude authors
# ---------------------------------------------------------------------------
all_authors = sorted({a["author_name"] for a in report.get("authors", [{}])[0].get("authors", [])})
excluded = st.sidebar.multiselect("Exclude authors", options=all_authors, default=[])

st.sidebar.divider()
st.sidebar.caption(f"Data window: {start_date} → {end_date}")

# ---------------------------------------------------------------------------
# Apply global filters
# ---------------------------------------------------------------------------
def _date_mask(df: pd.DataFrame, col: str) -> pd.Series:
    s = pd.Timestamp(start_date, tz="UTC")
    e = pd.Timestamp(end_date,   tz="UTC") + pd.Timedelta(days=1)
    return (df[col] >= s) & (df[col] < e)

def _author_mask(df: pd.DataFrame, col: str = "author_name") -> pd.Series:
    if not excluded or col not in df.columns:
        return pd.Series(True, index=df.index)
    return ~df[col].isin(excluded)

commits  = df_commits[_date_mask(df_commits, "committed_at") & _author_mask(df_commits)].copy() if not df_commits.empty else df_commits
merges   = df_merges[ _date_mask(df_merges,  "merged_at")]  .copy() if not df_merges.empty  else df_merges
folders  = df_folders[_date_mask(df_folders, "committed_at")].copy() if not df_folders.empty else df_folders
diffs    = df_diff[   _date_mask(df_diff,    "committed_at")].copy() if not df_diff.empty    else df_diff
loc      = df_loc[    _date_mask(df_loc,     "committed_at")].copy() if not df_loc.empty     else df_loc

# Enrich commits with diff stats
if not commits.empty and not diffs.empty:
    commits = commits.merge(
        diffs[["sha", "insertions", "deletions", "files_changed"]].rename(columns={"sha": "short_sha"}),
        on="short_sha", how="left",
    )
    commits["lines_changed"] = commits["insertions"].fillna(0) + commits["deletions"].fillna(0)
    commits["commit_type"] = commits["message"].apply(commit_type)

# ---------------------------------------------------------------------------
# Page title
# ---------------------------------------------------------------------------
st.title(f"Repository evolution — {repo_name}")
st.caption(f"Branch: `{branch}`  ·  Showing {start_date} → {end_date}  ·  {len(commits):,} commits")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview",
    "⚡ Activity",
    "👥 Contributors",
    "📁 Codebase",
    "🗂 PR Explorer",
    "🔀 PRs & Merges",
])

# ============================================================
# TAB 1 — OVERVIEW
# ============================================================
with tab1:
    # --- Metric cards ---
    unique_contributors = commits["author_name"].nunique() if not commits.empty else 0
    net_loc_start = loc["cumulative_loc"].iloc[0] if not loc.empty else 0
    net_loc_end   = loc["cumulative_loc"].iloc[-1] if not loc.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Commits", f"{len(commits):,}")
    c2.metric("PRs merged", f"{len(merges):,}")
    c3.metric("Contributors", f"{unique_contributors:,}")
    c4.metric("Net LOC", f"{net_loc_end:,}", delta=f"{net_loc_end - net_loc_start:+,}")

    st.divider()

    # --- LOC over time with merge markers ---
    st.subheader("Lines of code over time")

    if loc.empty:
        st.info("No LOC data for this range.")
    else:
        loc_sorted = loc.sort_values("committed_at")

        smooth = st.toggle("Smooth curve (rolling average)", value=False, key="loc_smooth")
        if smooth:
            win = st.slider("Rolling window (commits)", 5, 100, 20, 5, key="loc_win")
            loc_sorted["plot_loc"] = loc_sorted["cumulative_loc"].rolling(win, min_periods=1).mean()
        else:
            loc_sorted["plot_loc"] = loc_sorted["cumulative_loc"]

        show_merges = st.toggle("Show PR merge markers", value=True, key="loc_merges")

        fig_loc = go.Figure()
        fig_loc.add_trace(go.Scatter(
            x=loc_sorted["committed_at"],
            y=loc_sorted["plot_loc"],
            mode="lines",
            name="Cumulative LOC",
            line=dict(width=2),
            hovertemplate=(
                "<b>%{x|%Y-%m-%d}</b><br>"
                "LOC: %{y:,.0f}<br>"
                "SHA: %{customdata}<extra></extra>"
            ),
            customdata=loc_sorted["sha"],
        ))

        if show_merges and not merges.empty:
            # Overlay merge events as scatter markers on the LOC line
            merge_locs = pd.merge_asof(
                merges.sort_values("merged_at"),
                loc_sorted[["committed_at", "plot_loc"]].rename(columns={"committed_at": "merged_at"}),
                on="merged_at",
                direction="nearest",
            )
            # Build hover label: "PR #NNN — first line of message (clipped to 60 chars)"
            pr_number_str = (
                "PR #" + merge_locs["pr_number"].astype("Int64").astype(str)
                if "pr_number" in merge_locs.columns
                else merge_locs["merged_branch"]
            )
            pr_title = (
                merge_locs["message"]
                .str.split("\n").str[0]          # first line only
                .str.replace(r"\s*\(#\d+\)\s*$", "", regex=True)  # strip trailing (#NNN)
                .str.strip()
                .str[:60]
            )
            pr_labels = pr_number_str + " — " + pr_title

            fig_loc.add_trace(go.Scatter(
                x=merge_locs["merged_at"],
                y=merge_locs["plot_loc"],
                mode="markers",
                name="PR merged",
                marker=dict(symbol="triangle-up", size=9, color="orange"),
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d}</b><br>"
                    "%{customdata}<extra></extra>"
                ),
                customdata=pr_labels,
            ))

        fig_loc.update_layout(
            xaxis_title="Date",
            yaxis_title="Lines of code (net)",
            hovermode="x unified",
            height=460,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig_loc.update_yaxes(tickformat=",")
        st.plotly_chart(fig_loc, use_container_width=True)


# ============================================================
# TAB 2 — ACTIVITY
# ============================================================
with tab2:
    if commits.empty:
        st.info("No commits in selected range.")
    else:
        period_choice = st.radio("Group by", ["Week", "Month"], horizontal=True, key="act_period")
        freq = "W" if period_choice == "Week" else "ME"
        freq_label = "week" if period_choice == "Week" else "month"

        commits_ts = commits.set_index("committed_at")

        # --- Commit velocity ---
        st.subheader("Commit velocity")
        velocity = commits_ts.resample(freq).size().reset_index(name="count")
        velocity.columns = ["period", "count"]
        fig_vel = px.bar(
            velocity, x="period", y="count",
            labels={"period": "Date", "count": f"Commits per {freq_label}"},
        )
        fig_vel.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_vel, use_container_width=True)

        # --- Lines added vs removed ---
        st.subheader("Lines added vs removed")
        if "insertions" in commits.columns:
            diff_ts = commits_ts[["insertions", "deletions"]].fillna(0)
            ins_agg  = diff_ts["insertions"].resample(freq).sum().reset_index()
            dels_agg = diff_ts["deletions"].resample(freq).sum().reset_index()
            ins_agg.columns  = ["period", "value"]
            dels_agg.columns = ["period", "value"]

            fig_diff = go.Figure()
            fig_diff.add_trace(go.Bar(
                x=ins_agg["period"], y=ins_agg["value"],
                name="Insertions", marker_color="mediumseagreen",
                hovertemplate="%{x|%Y-%m-%d}<br>+%{y:,}<extra></extra>",
            ))
            fig_diff.add_trace(go.Bar(
                x=dels_agg["period"], y=-dels_agg["value"],
                name="Deletions", marker_color="salmon",
                hovertemplate="%{x|%Y-%m-%d}<br>-%{y:,}<extra></extra>",
            ))
            fig_diff.update_layout(
                barmode="relative",
                height=320,
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis_title="Lines",
                xaxis_title="Date",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            fig_diff.update_yaxes(tickformat=",")
            st.plotly_chart(fig_diff, use_container_width=True)
        else:
            st.info("Diff stats not available for this range.")

        col_scatter, col_donut = st.columns([3, 2])

        # --- Commit size scatter ---
        with col_scatter:
            st.subheader("Commit size")
            if "lines_changed" in commits.columns:
                log_scale = st.toggle("Log scale (y-axis)", value=False, key="scatter_log")
                scatter_df = commits[["committed_at", "lines_changed", "author_name", "short_sha", "message"]].copy()
                scatter_df["message_short"] = scatter_df["message"].str.split("\n").str[0].str[:80]
                fig_sc = px.scatter(
                    scatter_df,
                    x="committed_at",
                    y="lines_changed",
                    color="author_name",
                    log_y=log_scale,
                    hover_data={"committed_at": True, "lines_changed": True,
                                "short_sha": True, "message_short": True, "author_name": True},
                    labels={"committed_at": "Date", "lines_changed": "Lines changed",
                            "author_name": "Author", "message_short": "Message"},
                )
                fig_sc.update_traces(marker=dict(size=5, opacity=0.7))
                fig_sc.update_layout(
                    height=360,
                    margin=dict(l=0, r=0, t=10, b=0),
                    showlegend=False,
                    yaxis_title="Lines changed (log)" if log_scale else "Lines changed",
                )
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("Diff stats not available.")

        # --- Commit type donut ---
        with col_donut:
            st.subheader("Commit types")
            if "commit_type" in commits.columns:
                type_counts = commits["commit_type"].value_counts().reset_index()
                type_counts.columns = ["type", "count"]
                fig_donut = px.pie(
                    type_counts, names="type", values="count",
                    hole=0.45,
                    color="type",
                    color_discrete_map=COMMIT_TYPE_COLORS,
                )
                fig_donut.update_traces(textposition="inside", textinfo="percent+label")
                fig_donut.update_layout(
                    height=360,
                    margin=dict(l=0, r=0, t=10, b=30),
                    showlegend=True,
                    legend=dict(orientation="v"),
                )
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("Commit type data not available.")


# ============================================================
# TAB 3 — CONTRIBUTORS
# ============================================================
with tab3:
    if commits.empty:
        st.info("No commits in selected range.")
    else:
        # Build per-author aggregates from filtered commits
        if "insertions" in commits.columns:
            author_agg = (
                commits.groupby("author_name")
                .agg(
                    commit_count=("short_sha", "count"),
                    lines_added=("insertions", "sum"),
                    lines_removed=("deletions", "sum"),
                )
                .assign(net_lines=lambda d: d["lines_added"] - d["lines_removed"])
                .reset_index()
            )
        else:
            author_agg = (
                commits.groupby("author_name")
                .agg(commit_count=("short_sha", "count"))
                .reset_index()
                .assign(lines_added=0, lines_removed=0, net_lines=0)
            )

        # --- Leaderboard ---
        st.subheader("Contributor leaderboard")
        col_lb, col_metric = st.columns([3, 1])
        with col_metric:
            top_n   = st.slider("Top N authors", 5, 30, 10, key="lb_n")
            lb_sort = st.radio("Rank by", ["commit_count", "lines_added", "net_lines"],
                               format_func=lambda x: {"commit_count": "Commits",
                                                       "lines_added": "Lines added",
                                                       "net_lines": "Net lines"}[x],
                               key="lb_sort")

        top_authors = author_agg.nlargest(top_n, lb_sort).sort_values(lb_sort)
        with col_lb:
            fig_lb = px.bar(
                top_authors,
                x=lb_sort,
                y="author_name",
                orientation="h",
                labels={"author_name": "", lb_sort: lb_sort.replace("_", " ").title()},
                text=lb_sort,
            )
            fig_lb.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig_lb.update_layout(
                height=max(280, top_n * 28),
                margin=dict(l=0, r=60, t=10, b=0),
                yaxis=dict(tickfont=dict(size=12)),
            )
            st.plotly_chart(fig_lb, use_container_width=True)

        st.divider()

        col_monthly, col_stack = st.columns(2)

        # --- Active contributors per month ---
        with col_monthly:
            st.subheader("Active contributors per month")
            monthly_active = (
                commits.set_index("committed_at")
                .resample("ME")["author_name"]
                .nunique()
                .reset_index()
            )
            monthly_active.columns = ["month", "unique_authors"]
            fig_active = px.line(
                monthly_active, x="month", y="unique_authors",
                markers=True,
                labels={"month": "Month", "unique_authors": "Unique contributors"},
            )
            fig_active.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_active, use_container_width=True)

        # --- Per-author stacked area ---
        with col_stack:
            st.subheader("Commits per author over time")
            top_author_names = author_agg.nlargest(8, "commit_count")["author_name"].tolist()
            commits_top = commits[commits["author_name"].isin(top_author_names)].copy()

            if not commits_top.empty:
                monthly_by_author = (
                    commits_top.set_index("committed_at")
                    .groupby([pd.Grouper(freq="ME"), "author_name"])
                    .size()
                    .reset_index(name="count")
                )
                monthly_by_author.columns = ["month", "author_name", "count"]
                fig_stack = px.area(
                    monthly_by_author,
                    x="month", y="count", color="author_name",
                    labels={"month": "Month", "count": "Commits", "author_name": "Author"},
                )
                fig_stack.update_layout(
                    height=300,
                    margin=dict(l=0, r=0, t=10, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.4),
                )
                st.plotly_chart(fig_stack, use_container_width=True)
            else:
                st.info("Not enough data.")


# ============================================================
# TAB 4 — CODEBASE
# ============================================================
with tab4:
    if folders.empty:
        st.info("No folder change data in selected range.")
    else:
        # Change type filter
        change_types_available = sorted(folders["change_type"].unique().tolist())
        selected_types = st.multiselect(
            "Change types", options=change_types_available,
            default=change_types_available, key="folder_types",
        )
        folders_f = folders[folders["change_type"].isin(selected_types)] if selected_types else folders

        col_bar, col_heat = st.columns([1, 2])

        # --- Top directories by churn ---
        with col_bar:
            st.subheader("Top directories by churn")
            top_dirs_n = st.slider("Top N directories", 5, 30, 15, key="dirs_n")
            dir_counts = (
                folders_f.groupby("directory")
                .size()
                .reset_index(name="events")
                .nlargest(top_dirs_n, "events")
                .sort_values("events")
            )
            fig_dirs = px.bar(
                dir_counts, x="events", y="directory", orientation="h",
                labels={"directory": "", "events": "Change events"},
                text="events",
            )
            fig_dirs.update_traces(textposition="outside")
            fig_dirs.update_layout(
                height=max(300, top_dirs_n * 28),
                margin=dict(l=0, r=40, t=10, b=0),
                yaxis=dict(tickfont=dict(size=11)),
            )
            st.plotly_chart(fig_dirs, use_container_width=True)

        # --- Directory × month heatmap ---
        with col_heat:
            st.subheader("Directory activity heatmap")
            heat_dirs_n = st.slider("Directories in heatmap", 5, 25, 15, key="heat_n")

            top_dir_names = (
                folders_f.groupby("directory").size()
                .nlargest(heat_dirs_n).index.tolist()
            )
            folders_heat = folders_f[folders_f["directory"].isin(top_dir_names)].copy()
            folders_heat["month"] = folders_heat["committed_at"].dt.to_period("M").astype(str)

            heat_pivot = (
                folders_heat.groupby(["directory", "month"])
                .size()
                .reset_index(name="events")
                .pivot(index="directory", columns="month", values="events")
                .fillna(0)
            )
            fig_heat = px.imshow(
                heat_pivot,
                aspect="auto",
                color_continuous_scale="Blues",
                labels=dict(x="Month", y="Directory", color="Events"),
            )
            fig_heat.update_layout(
                height=max(300, heat_dirs_n * 24),
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis=dict(tickangle=-45),
                coloraxis_showscale=True,
            )
            st.plotly_chart(fig_heat, use_container_width=True)


# ============================================================
# TAB 5 — PR EXPLORER
# ============================================================
with tab5:
    if merges.empty or folders.empty:
        st.info("Need both merge events and folder change data to use this tab.")
    else:
        # Build PR list for the slider: merges sorted chronologically, title clipped
        pr_list = (
            merges.sort_values("merged_at")
            .assign(
                pr_title=lambda d: (
                    "PR #" + d["pr_number"].astype("Int64").astype(str) + "  —  "
                    + d["message"].str.split("\n").str[0]
                      .str.replace(r"\s*\(#\d+\)\s*$", "", regex=True)
                      .str.strip()
                      .str[:60]
                )
            )
            .reset_index(drop=True)
        )

        if pr_list.empty:
            st.info("No PRs in the selected date range.")
        else:
            # ── PR selector ──────────────────────────────────────────
            pr_titles = pr_list["pr_title"].tolist()
            selected_title = st.select_slider(
                "Browse PRs (oldest → newest)",
                options=pr_titles,
                value=pr_titles[-1],
                key="pr_explorer_slider",
            )
            selected_pr = pr_list[pr_list["pr_title"] == selected_title].iloc[0]
            selected_sha = selected_pr["merge_commit_sha"]

            # ── Enrich with diff stats and author ────────────────────
            pr_diff = diffs[diffs["sha"] == selected_sha]
            pr_ins   = int(pr_diff["insertions"].sum()) if not pr_diff.empty else None
            pr_dels  = int(pr_diff["deletions"].sum())  if not pr_diff.empty else None
            pr_files = int(pr_diff["files_changed"].sum()) if not pr_diff.empty else None

            pr_author_row = commits[commits["short_sha"] == selected_sha]
            pr_author = pr_author_row["author_name"].iloc[0] if not pr_author_row.empty else "—"

            pr_type = commit_type(selected_pr["message"])
            type_color = COMMIT_TYPE_COLORS.get(pr_type, "#95a5a6")

            # ── Metadata row: 6 chips ─────────────────────────────────
            mc1, mc2, mc3, mc4, mc5, mc6 = st.columns([1, 1, 1, 1, 1, 1])
            mc1.markdown(
                f"<div style='padding-top:6px'>"
                f"<span style='font-size:11px;color:#888'>Type</span><br>"
                f"<span style='color:{type_color};font-weight:bold;font-size:2rem'>{pr_type}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            mc2.metric("PR", selected_pr["merged_branch"])
            mc3.metric("Merged", pd.Timestamp(selected_pr["merged_at"]).strftime("%Y-%m-%d"))
            mc4.metric("Author", pr_author)
            if pr_ins is not None:
                mc5.markdown(
                    f"<div style='padding-top:6px'>"
                    f"<span style='font-size:11px;color:#888'>Lines changed</span><br>"
                    f"<span style='color:#2ecc71;font-weight:bold;font-size:2rem'>+{pr_ins:,}</span>"
                    f"&nbsp;&nbsp;"
                    f"<span style='color:#e74c3c;font-weight:bold;font-size:2rem'>−{pr_dels:,}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                mc6.metric("Files changed", f"{pr_files:,}" if pr_files else "—")
            else:
                mc5.metric("Lines +", "—")
                mc6.metric("Files", "—")

            # ── Full PR message ───────────────────────────────────────
            raw_msg = selected_pr["message"].strip()
            lines = raw_msg.split("\n")
            title_line = lines[0]
            body_lines = lines[1:] if len(lines) > 1 else []
            body_text  = "\n".join(body_lines).strip()

            st.divider()

            # ── Per-PR folder changes ─────────────────────────────────
            pr_dirs = folders[folders["sha"] == selected_sha].copy()

            col_sun, col_table, col_msg = st.columns([3, 2, 2])

            with col_sun:
                st.subheader("Directories touched")
                if pr_dirs.empty:
                    st.info("No folder-level changes recorded for this PR.")
                else:
                    # Build sunburst: split each path into parts and build
                    # parent/label/value/color lists for Plotly
                    _color_map = {
                        "added":    "#2ecc71",
                        "modified": "#3498db",
                        "removed":  "#e74c3c",
                        "renamed":  "#f39c12",
                    }

                    # Count events per (directory, change_type)
                    dir_counts = (
                        pr_dirs.groupby(["directory", "change_type"])
                        .size()
                        .reset_index(name="count")
                    )

                    # Determine dominant change_type per directory for colouring
                    dominant = (
                        dir_counts.sort_values("count", ascending=False)
                        .groupby("directory")
                        .first()
                        .reset_index()[["directory", "change_type"]]
                    )

                    # Build sunburst node lists
                    # Each path like "a/b/c" gives nodes: "a", "a/b", "a/b/c"
                    # with parent "", "a", "a/b" respectively
                    all_nodes: dict[str, dict] = {}  # path → {parent, count, change_type}

                    for _, row in dir_counts.iterrows():
                        parts = row["directory"].split("/")
                        for depth in range(1, len(parts) + 1):
                            node  = "/".join(parts[:depth])
                            parent = "/".join(parts[:depth - 1]) if depth > 1 else ""
                            if node not in all_nodes:
                                all_nodes[node] = {"parent": parent, "count": 0, "change_type": "modified"}
                            all_nodes[node]["count"] += row["count"]

                    # Overwrite change_type with dominant for leaf nodes
                    for _, row in dominant.iterrows():
                        if row["directory"] in all_nodes:
                            all_nodes[row["directory"]]["change_type"] = row["change_type"]

                    # Parent nodes inherit dominant child change_type
                    for node, info in all_nodes.items():
                        if not any(v["parent"] == node for v in all_nodes.values()):
                            continue  # leaf — already set
                        child_types = [
                            v["change_type"] for k, v in all_nodes.items()
                            if v["parent"] == node
                        ]
                        if child_types:
                            for ct in ("added", "removed", "renamed", "modified"):
                                if ct in child_types:
                                    all_nodes[node]["change_type"] = ct
                                    break

                    labels  = [n.split("/")[-1] or n for n in all_nodes]
                    parents = [v["parent"] for v in all_nodes.values()]
                    values  = [v["count"]  for v in all_nodes.values()]
                    colors  = [_color_map.get(v["change_type"], "#95a5a6") for v in all_nodes.values()]
                    full_paths = list(all_nodes.keys())

                    fig_sun = go.Figure(go.Sunburst(
                        labels=labels,
                        parents=parents,
                        values=values,
                        ids=full_paths,
                        marker=dict(colors=colors),
                        hovertemplate=(
                            "<b>%{id}</b><br>"
                            "Events: %{value}<extra></extra>"
                        ),
                        branchvalues="total",
                        maxdepth=4,
                    ))
                    fig_sun.update_layout(
                        height=440,
                        margin=dict(l=0, r=0, t=10, b=10),
                    )

                    # Legend
                    leg_cols = st.columns(4)
                    for i, (ct, col_hex) in enumerate(_color_map.items()):
                        leg_cols[i].markdown(
                            f"<span style='color:{col_hex}'>■</span> {ct.capitalize()}",
                            unsafe_allow_html=True,
                        )

                    st.plotly_chart(fig_sun, use_container_width=True)

            with col_table:
                st.subheader("Change summary")
                summary = (
                    pr_dirs.groupby(["directory", "change_type"])
                    .size()
                    .reset_index(name="events")
                    .sort_values(["change_type", "events"], ascending=[True, False])
                )
                summary.columns = ["Directory", "Change type", "Events"]
                def _style_type(val: str) -> str:
                    c = {"added": "#2ecc71", "modified": "#3498db",
                         "removed": "#e74c3c", "renamed": "#f39c12"}.get(val, "")
                    return f"color: {c}; font-weight: bold" if c else ""

                st.dataframe(
                    summary.style.applymap(_style_type, subset=["Change type"]),
                    use_container_width=True,
                    hide_index=True,
                    height=420,
                )

            with col_msg:
                st.subheader("📝 PR description")
                st.markdown(f"**{title_line}**")
                if body_text:
                    st.markdown(body_text)

            st.divider()

            # ── Directory debut timeline ──────────────────────────────
            st.subheader("Directory debut timeline — when each folder first appeared")
            st.caption(
                "Each marker is the PR where a directory was first seen with an 'added' event. "
                "Sorted by first appearance."
            )

            # Find first "added" event per directory across ALL folder data (not just date-filtered)
            # so we always show the true birth even if it's outside the current window
            all_folders = pd.DataFrame(report.get("folder_changes", []))
            all_folders["committed_at"] = pd.to_datetime(all_folders["committed_at"], utc=True)
            all_merges_full = pd.DataFrame(report.get("merges", []))
            all_merges_full["merged_at"] = pd.to_datetime(all_merges_full["merged_at"], utc=True)

            first_added = (
                all_folders[all_folders["change_type"] == "added"]
                .sort_values("committed_at")
                .groupby("directory")
                .first()
                .reset_index()[["directory", "sha", "committed_at"]]
            )

            # Attach PR info via SHA match
            first_added = first_added.merge(
                all_merges_full[["merge_commit_sha", "merged_branch", "pr_number", "message"]]
                    .rename(columns={"merge_commit_sha": "sha"}),
                on="sha",
                how="left",
            )
            first_added["pr_label"] = (
                "PR #" + first_added["pr_number"].astype("Int64").astype(str)
            ).where(first_added["pr_number"].notna(), first_added["sha"])

            first_added = first_added.sort_values("committed_at").reset_index(drop=True)
            first_added["rank"] = range(len(first_added))
            first_added["dir_short"] = first_added["directory"].apply(
                lambda d: d if len(d) <= 35 else "…/" + d.split("/")[-1]
            )
            first_added["hover_msg"] = (
                first_added["message"]
                .fillna("")
                .str.split("\n").str[0]
                .str[:70]
            )

            # Limit to top-level depth control
            max_depth = st.slider(
                "Max directory depth shown", min_value=1, max_value=5, value=2,
                key="debut_depth",
                help="1 = top-level folders only, 2 = two levels deep, etc.",
            )
            first_added_f = first_added[
                first_added["directory"].str.count("/") < max_depth
            ]

            if first_added_f.empty:
                st.info("No 'added' events found for this depth setting.")
            else:
                fig_debut = go.Figure()
                fig_debut.add_trace(go.Scatter(
                    x=first_added_f["committed_at"],
                    y=first_added_f["rank"],
                    mode="markers+text",
                    marker=dict(size=10, color="#2ecc71", symbol="circle"),
                    text=first_added_f["dir_short"],
                    textposition="middle right",
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "First seen: %{x|%Y-%m-%d}<br>"
                        "Via: %{customdata[1]}<br>"
                        "%{customdata[2]}<extra></extra>"
                    ),
                    customdata=first_added_f[["directory", "pr_label", "hover_msg"]].values,
                ))
                fig_debut.update_layout(
                    height=max(350, len(first_added_f) * 22),
                    xaxis_title="Date",
                    yaxis=dict(visible=False),
                    margin=dict(l=0, r=220, t=10, b=0),
                    showlegend=False,
                )
                st.plotly_chart(fig_debut, use_container_width=True)


# ============================================================
# TAB 6 — PRs & MERGES
# ============================================================
with tab6:
    if merges.empty:
        st.info("No merge events in selected range.")
    else:
        col_freq, col_style = st.columns([3, 1])

        with col_style:
            st.subheader("Merge style")
            if "merge_style" in merges.columns:
                style_counts = merges["merge_style"].value_counts().reset_index()
                style_counts.columns = ["style", "count"]
                fig_style = px.pie(
                    style_counts, names="style", values="count", hole=0.45,
                )
                fig_style.update_traces(textposition="inside", textinfo="percent+label")
                fig_style.update_layout(
                    height=260,
                    margin=dict(l=0, r=0, t=10, b=10),
                    showlegend=False,
                )
                st.plotly_chart(fig_style, use_container_width=True)

        with col_freq:
            st.subheader("PRs merged over time")
            pr_period = st.radio("Group by", ["Week", "Month"], horizontal=True, key="pr_period")
            pr_freq = "W" if pr_period == "Week" else "ME"
            pr_freq_label = "week" if pr_period == "Week" else "month"

            pr_velocity = (
                merges.set_index("merged_at")
                .resample(pr_freq)
                .size()
                .reset_index(name="count")
            )
            pr_velocity.columns = ["period", "count"]
            fig_pr = px.bar(
                pr_velocity, x="period", y="count",
                labels={"period": "Date", "count": f"PRs per {pr_freq_label}"},
            )
            fig_pr.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_pr, use_container_width=True)

        st.divider()

        # --- PR size scatter ---
        st.subheader("PR size (lines changed)")
        if not diffs.empty and "sha" in merges.columns:
            pr_size = merges.merge(
                diffs[["sha", "insertions", "deletions", "files_changed"]],
                left_on="merge_commit_sha",
                right_on="sha",
                how="left",
            )
            pr_size["lines_changed"] = pr_size["insertions"].fillna(0) + pr_size["deletions"].fillna(0)
            pr_size["message_short"] = pr_size["message"].str.split("\n").str[0].str[:80]
            pr_size_valid = pr_size[pr_size["lines_changed"] > 0].copy()

            if not pr_size_valid.empty:
                fig_pr_sc = px.scatter(
                    pr_size_valid,
                    x="merged_at",
                    y="lines_changed",
                    size="lines_changed",
                    hover_data={
                        "merged_at": True,
                        "lines_changed": True,
                        "merge_commit_sha": True,
                        "message_short": True,
                    },
                    size_max=40,
                    labels={
                        "merged_at": "Date",
                        "lines_changed": "Lines changed",
                        "message_short": "PR",
                    },
                )
                fig_pr_sc.update_layout(
                    height=360,
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig_pr_sc, use_container_width=True)
            else:
                st.info("Could not match diff stats to merge commits for this range.")
        else:
            st.info("Diff stats not available to size PRs.")

        # --- PR table ---
        st.subheader("Merged PRs")
        pr_table_cols = [c for c in ["merge_commit_sha", "merged_at", "merged_branch", "merge_style", "message"]
                         if c in merges.columns]
        pr_display = merges[pr_table_cols].copy()
        pr_display["merged_at"] = pr_display["merged_at"].dt.strftime("%Y-%m-%d")
        pr_display["message"] = pr_display["message"].str.split("\n").str[0].str[:100]
        pr_display.columns = [c.replace("_", " ").title() for c in pr_display.columns]
        st.dataframe(pr_display, use_container_width=True, hide_index=True)
