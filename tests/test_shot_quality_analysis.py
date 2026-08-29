import json

import pandas as pd
import pytest

from closeout.analysis.shot_quality import load_predictions, player_rank, summarize_by_player


def _row(shooter_id, shooter_name, made, expected_fg_pct):
    return {
        "shooter_id": shooter_id,
        "shooter_name": shooter_name,
        "made": made,
        "expected_fg_pct": expected_fg_pct,
    }


def test_load_predictions_reads_every_game_file(tmp_path):
    (tmp_path / "0021500001.jsonl").write_text(json.dumps(_row(1, "A", True, 0.5)) + "\n")
    (tmp_path / "0021500002.jsonl").write_text(
        "\n".join(json.dumps(_row(2, "B", False, 0.4)) for _ in range(2)) + "\n"
    )

    df = load_predictions(tmp_path)

    assert len(df) == 3
    assert set(df["shooter_id"]) == {1, 2}


def test_summarize_by_player_computes_actual_expected_and_diff():
    df = pd.DataFrame(
        [
            _row(1, "Curry", True, 0.4),
            _row(1, "Curry", True, 0.4),
            _row(1, "Curry", False, 0.4),
            _row(1, "Curry", True, 0.4),
        ]
    )

    summary = summarize_by_player(df)

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["n_shots"] == 4
    assert row["actual_fg_pct"] == 0.75
    assert row["expected_fg_pct"] == 0.4
    assert row["diff"] == pytest.approx(0.35)


def test_summarize_by_player_groups_by_id_not_name():
    # Stephen and Seth Curry both share the last name "Curry" -- grouping by
    # name alone would wrongly merge their shots into one row.
    df = pd.DataFrame(
        [
            _row(201939, "Curry", True, 0.3),
            _row(201939, "Curry", True, 0.3),
            _row(203552, "Curry", False, 0.5),
        ]
    )

    summary = summarize_by_player(df)

    assert len(summary) == 2
    assert set(summary["shooter_id"]) == {201939, 203552}
    stephen = summary[summary["shooter_id"] == 201939].iloc[0]
    assert stephen["n_shots"] == 2
    assert stephen["actual_fg_pct"] == 1.0


def test_summarize_by_player_min_shots_filters_low_volume_players():
    df = pd.DataFrame(
        [
            _row(1, "A", True, 0.5),
            _row(2, "B", True, 0.5),
            _row(2, "B", False, 0.5),
        ]
    )

    summary = summarize_by_player(df, min_shots=2)

    assert list(summary["shooter_id"]) == [2]


def test_summarize_by_player_sorts_best_diff_first():
    df = pd.DataFrame(
        [
            _row(1, "Low", True, 0.9),  # diff = 0.1
            _row(2, "High", True, 0.1),  # diff = 0.9
        ]
    )

    summary = summarize_by_player(df)

    assert list(summary["shooter_id"]) == [2, 1]


def test_player_rank_is_one_indexed():
    df = pd.DataFrame(
        [
            _row(1, "First", True, 0.1),
            _row(2, "Second", True, 0.5),
            _row(3, "Third", False, 0.9),
        ]
    )
    summary = summarize_by_player(df)

    assert player_rank(summary, 1) == 1
    assert player_rank(summary, 3) == 3
