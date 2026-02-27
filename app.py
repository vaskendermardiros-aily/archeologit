"""archeologit — interactive Streamlit dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
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
# Sidebar — report file picker
# ---------------------------------------------------------------------------
st.sidebar.title("🏺 archeologit")
st.sidebar.markdown("Git repository evolution explorer")

default_report = Path(__file__).parent / "report.json"
report_path = st.sidebar.text_input("Report file", value=str(default_report))

@st.cache_data
def load_report(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

try:
    report = load_report(report_path)
except FileNotFoundError:
    st.error(f"Report not found: `{report_path}`\n\nRun `python main.py all` to generate it.")
    st.stop()

repo_name = Path(report.get("repo", report_path)).name
branch = report.get("branch", "main")

st.sidebar.markdown(f"**Repo:** `{repo_name}`")
st.sidebar.markdown(f"**Branch:** `{branch}`")

# ---------------------------------------------------------------------------
# Main title
# ---------------------------------------------------------------------------
st.title(f"Repository evolution — {repo_name}")
st.caption(f"Branch: `{branch}`  ·  Report: `{Path(report_path).name}`")

# ---------------------------------------------------------------------------
# LOC over time
# ---------------------------------------------------------------------------
st.header("Lines of code over time")

loc_data = report.get("loc_over_time", [])
if not loc_data:
    st.warning("No LOC data found in the report.")
else:
    df_loc = pd.DataFrame(loc_data)
    df_loc["committed_at"] = pd.to_datetime(df_loc["committed_at"], utc=True)
    df_loc = df_loc.sort_values("committed_at")

    # Smoothing toggle
    smooth = st.toggle("Smooth curve (rolling average)", value=False)
    if smooth:
        window = st.slider("Rolling window (commits)", min_value=5, max_value=100, value=20, step=5)
        df_loc["plot_loc"] = df_loc["cumulative_loc"].rolling(window, min_periods=1).mean()
    else:
        df_loc["plot_loc"] = df_loc["cumulative_loc"]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df_loc["committed_at"],
            y=df_loc["plot_loc"],
            mode="lines",
            name="Cumulative LOC",
            line=dict(width=2),
            hovertemplate=(
                "<b>%{x|%Y-%m-%d}</b><br>"
                "LOC: %{y:,.0f}<br>"
                "SHA: %{customdata}<extra></extra>"
            ),
            customdata=df_loc["sha"],
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Lines of code (net)",
        hovermode="x unified",
        height=480,
        margin=dict(l=0, r=0, t=20, b=0),
    )
    fig.update_yaxes(tickformat=",")

    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics below the chart
    first = df_loc.iloc[0]
    last = df_loc.iloc[-1]
    delta = int(last["cumulative_loc"] - first["cumulative_loc"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("First commit", first["committed_at"].strftime("%Y-%m-%d"))
    col2.metric("Latest commit", last["committed_at"].strftime("%Y-%m-%d"))
    col3.metric("Current LOC (net)", f"{int(last['cumulative_loc']):,}")
    col4.metric("Net growth", f"+{delta:,}" if delta >= 0 else f"{delta:,}")
