"""Shot-quality dashboard: pick a player, see their shot chart (colored by
the model's expected FG%) next to where they rank league-wide on
actual-vs-expected FG%.

Run with: streamlit run app/dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# The package isn't pip-installed -- other entry points in this repo rely on
# PYTHONPATH=src being set (see pytest.ini), but `streamlit run` doesn't read
# that, so this makes the app runnable on its own.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib.pyplot as plt
import streamlit as st

from closeout.analysis.shot_quality import CURRY_PLAYER_ID, load_predictions, player_rank, summarize_by_player
from closeout.viz.shot_chart import add_normalized_coords, plot_shot_chart

MIN_SHOTS = 200


@st.cache_data
def load_normalized_predictions():
    return add_normalized_coords(load_predictions())


st.set_page_config(page_title="Closeout", layout="wide")
st.title("Closeout: shot quality vs. shot making")
st.caption(
    "2015-16 season, through Jan 22 (the tracking mirror's cutoff) -- "
    "shots colored by the model's expected FG%, an x marks a miss."
)

df = load_normalized_predictions()
summary = summarize_by_player(df, min_shots=MIN_SHOTS)

# Disambiguate same-last-name players (e.g. Stephen & Seth Curry) only where
# it actually matters, rather than cluttering every row with a player id.
name_counts = summary["shooter_name"].value_counts()
summary["label"] = summary.apply(
    lambda r: f"{r.shooter_name} (#{r.shooter_id})" if name_counts[r.shooter_name] > 1 else r.shooter_name,
    axis=1,
)

default_index = int(summary.index[summary["shooter_id"] == CURRY_PLAYER_ID][0])
label = st.selectbox("Player", summary["label"], index=default_index)
selected = summary[summary["label"] == label].iloc[0]

col1, col2 = st.columns([3, 2])

with col1:
    player_shots = df[df["shooter_id"] == selected["shooter_id"]]
    ax = plot_shot_chart(player_shots, title=f"{selected['shooter_name']} -- {int(selected['n_shots'])} shots")
    st.pyplot(ax.figure)
    plt.close(ax.figure)

with col2:
    rank = player_rank(summary, selected["shooter_id"])
    st.metric(
        f"{selected['shooter_name']}: actual FG%",
        f"{selected['actual_fg_pct']:.1%}",
        f"{selected['diff'] * 100:+.1f} pts vs. {selected['expected_fg_pct']:.1%} expected",
    )
    st.caption(f"League rank: #{rank} of {len(summary)} players with {MIN_SHOTS}+ shots")

    st.subheader("League leaderboard")
    display = summary[["shooter_name", "n_shots", "actual_fg_pct", "expected_fg_pct", "diff"]].copy()
    display["actual_fg_pct"] = (display["actual_fg_pct"] * 100).round(1)
    display["expected_fg_pct"] = (display["expected_fg_pct"] * 100).round(1)
    display["diff"] = (display["diff"] * 100).round(1)
    display.columns = ["Player", "Shots", "Actual FG%", "Expected FG%", "Diff (pts)"]
    st.dataframe(display, hide_index=True, height=500)
