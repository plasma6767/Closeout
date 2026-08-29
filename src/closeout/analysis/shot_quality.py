"""Actual-vs-expected FG% by player, from the scored predictions -- the input
the Curry write-up (roadmap item 4) needs.

Kept separate from models/dataset.py: that module loads *features* for
training, this one loads *predictions* (features plus expected_fg_pct) for
analysis, after a model already exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DEFAULT_PREDICTIONS_DIR = Path("data/predictions")

CURRY_PLAYER_ID = 201939


def load_predictions(predictions_dir: Path = DEFAULT_PREDICTIONS_DIR) -> pd.DataFrame:
    """Load every game's scored predictions file into one table, one row per shot."""
    rows = []
    for path in sorted(Path(predictions_dir).glob("*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text().splitlines())
    return pd.DataFrame(rows)


def summarize_by_player(df: pd.DataFrame, min_shots: int = 0) -> pd.DataFrame:
    """Actual vs. expected FG% per player, ranked by actual-minus-expected (best first).

    Groups by shooter_id, not shooter_name -- play-by-play only records last
    names, and some last names aren't unique (Stephen and Seth Curry both
    played in 2015-16), so grouping by name would silently merge different
    players' shots together.
    """
    grouped = df.groupby("shooter_id").agg(
        shooter_name=("shooter_name", "first"),
        n_shots=("made", "size"),
        actual_fg_pct=("made", "mean"),
        expected_fg_pct=("expected_fg_pct", "mean"),
    )
    grouped["diff"] = grouped["actual_fg_pct"] - grouped["expected_fg_pct"]
    grouped = grouped[grouped["n_shots"] >= min_shots]
    return grouped.sort_values("diff", ascending=False).reset_index()


def player_rank(summary: pd.DataFrame, player_id: int) -> int:
    """1-indexed rank of a player within a summary table already sorted best-diff-first."""
    matches = summary.index[summary["shooter_id"] == player_id]
    if len(matches) == 0:
        raise ValueError(f"player_id {player_id} not found in summary")
    return int(matches[0]) + 1


def _print_report(df: pd.DataFrame, player_id: int = CURRY_PLAYER_ID, player_label: str = "Stephen Curry", min_shots: int = 200) -> None:
    summary = summarize_by_player(df, min_shots=min_shots)
    row = summary[summary["shooter_id"] == player_id].iloc[0]
    rank = player_rank(summary, player_id)
    diff_pts = row["diff"] * 100

    print(player_label)
    print(
        f"  {int(row['n_shots'])} shots: {row['actual_fg_pct']:.1%} actual FG%  "
        f"vs.  {row['expected_fg_pct']:.1%} expected FG%  ({diff_pts:+.1f} pts)"
    )
    print(f"  League rank: #{rank} of {len(summary)} players with {min_shots}+ shots")
    print()
    print("Top 10 by actual-minus-expected FG%:")
    for i, r in enumerate(summary.head(10).itertuples(), start=1):
        print(f"  {i:2d}. {r.shooter_name:12s} {int(r.n_shots):4d} shots   {r.diff * 100:+.1f} pts")


if __name__ == "__main__":
    _print_report(load_predictions())
