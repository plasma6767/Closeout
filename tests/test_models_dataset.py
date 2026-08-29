import json

import pandas as pd

from closeout.models.dataset import split_by_game, load_features


def _row(game_id, event_id):
    return {"game_id": game_id, "event_id": event_id, "shot_distance_ft": 10.0, "made": True}


def test_load_features_reads_every_game_file(tmp_path):
    (tmp_path / "0021500001.jsonl").write_text(json.dumps(_row("0021500001", 1)) + "\n")
    (tmp_path / "0021500002.jsonl").write_text(
        "\n".join(json.dumps(_row("0021500002", i)) for i in (1, 2)) + "\n"
    )

    df = load_features(tmp_path)

    assert len(df) == 3
    assert set(df["game_id"]) == {"0021500001", "0021500002"}


def test_split_by_game_keeps_each_games_shots_on_one_side():
    rows = []
    for game_id in [f"g{i}" for i in range(10)]:
        rows.extend(_row(game_id, event_id) for event_id in range(5))
    df = pd.DataFrame(rows)

    train_df, test_df = split_by_game(df, test_size=0.2, seed=1)

    train_games = set(train_df["game_id"])
    test_games = set(test_df["game_id"])
    assert train_games.isdisjoint(test_games)
    assert len(train_df) + len(test_df) == len(df)
    assert len(test_games) == 2  # 20% of 10 games


def test_split_by_game_is_deterministic_given_a_seed():
    rows = [_row(f"g{i}", 1) for i in range(20)]
    df = pd.DataFrame(rows)

    train_a, test_a = split_by_game(df, seed=7)
    train_b, test_b = split_by_game(df, seed=7)

    assert list(train_a["game_id"]) == list(train_b["game_id"])
    assert list(test_a["game_id"]) == list(test_b["game_id"])
