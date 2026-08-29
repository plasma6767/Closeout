import json
import random

import pandas as pd

from closeout.models.dataset import FEATURE_COLUMNS, TARGET_COLUMN, split_by_game
from closeout.models.train import (
    BASELINE_COLUMNS,
    evaluate,
    prepare_features,
    run_training,
    train_baseline,
    train_full_model,
)


def _synthetic_dataset(n_games=30, shots_per_game=20, seed=0) -> pd.DataFrame:
    """Fake but internally consistent shot rows: real shots go in more often when close and open.

    Enough games/shots/signal for LogisticRegression and xgboost to fit
    something non-degenerate, and for both make/miss to show up in every
    split -- not meant to resemble real shot-quality numbers.
    """
    rng = random.Random(seed)
    rows = []
    event_id = 1
    for g in range(n_games):
        game_id = f"002150{g:04d}"
        for _ in range(shots_per_game):
            distance = rng.uniform(0, 30)
            defender_dist = rng.uniform(0, 10)
            make_prob = max(0.05, min(0.95, 0.8 - 0.02 * distance + 0.02 * defender_dist))
            rows.append(
                {
                    "game_id": game_id,
                    "event_id": event_id,
                    "shot_distance_ft": distance,
                    "shot_angle_deg": rng.uniform(0, 90),
                    "closest_defender_dist_ft": defender_dist,
                    "closest_defender_angle_deg": rng.uniform(0, 180),
                    "second_defender_dist_ft": defender_dist + rng.uniform(0, 5),
                    "second_defender_angle_deg": rng.uniform(0, 180),
                    "shooter_speed_ftps": rng.uniform(0, 15),
                    "closest_defender_closing_speed_ftps": rng.uniform(-5, 5),
                    "catch_and_shoot": rng.random() < 0.15,
                    "made": rng.random() < make_prob,
                }
            )
            event_id += 1
    return pd.DataFrame(rows)


def test_train_baseline_predicts_probabilities_in_range():
    df = _synthetic_dataset()
    model = train_baseline(df)

    probs = model.predict_proba(prepare_features(df, BASELINE_COLUMNS))[:, 1]
    assert ((probs >= 0) & (probs <= 1)).all()


def test_train_full_model_predicts_probabilities_in_range():
    df = _synthetic_dataset()
    model = train_full_model(df)

    probs = model.predict_proba(prepare_features(df, FEATURE_COLUMNS))[:, 1]
    assert ((probs >= 0) & (probs <= 1)).all()


def test_evaluate_returns_auc_log_loss_and_calibration():
    df = _synthetic_dataset()
    train_df, test_df = split_by_game(df, seed=1)
    model = train_full_model(train_df)

    metrics = evaluate(model, test_df, FEATURE_COLUMNS)

    assert 0 <= metrics["auc"] <= 1
    assert metrics["log_loss"] > 0
    assert len(metrics["calibration"]) > 0
    for predicted_rate, actual_rate in metrics["calibration"]:
        assert 0 <= predicted_rate <= 1
        assert 0 <= actual_rate <= 1


def test_full_model_beats_or_matches_baseline_on_synthetic_signal():
    # make_prob depends on both distance and defender distance, so the
    # full model (which sees both) should not do meaningfully worse than
    # the distance-only baseline.
    df = _synthetic_dataset(n_games=60, shots_per_game=25, seed=3)
    train_df, test_df = split_by_game(df, seed=3)

    baseline_metrics = evaluate(train_baseline(train_df), test_df, BASELINE_COLUMNS)
    full_metrics = evaluate(train_full_model(train_df), test_df, FEATURE_COLUMNS)

    assert full_metrics["log_loss"] <= baseline_metrics["log_loss"] + 0.05


def test_run_training_writes_expected_fg_pct_for_every_shot(tmp_path):
    features_dir = tmp_path / "features"
    predictions_dir = tmp_path / "predictions"
    features_dir.mkdir()

    df = _synthetic_dataset(n_games=15, shots_per_game=15, seed=2)
    for game_id, game_df in df.groupby("game_id"):
        rows = game_df.drop(columns=[]).to_dict(orient="records")
        with (features_dir / f"{game_id}.jsonl").open("w") as f:
            for row in rows:
                f.write(json.dumps({**row, "made": bool(row["made"])}) + "\n")

    results = run_training(features_dir, predictions_dir, seed=2)

    assert results["winner"] in {"baseline", "full"}
    assert results["n_shots"] == len(df)

    written_files = sorted(predictions_dir.glob("*.jsonl"))
    assert len(written_files) == df["game_id"].nunique()

    n_written = 0
    for path in written_files:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            assert 0.0 <= row["expected_fg_pct"] <= 1.0
            n_written += 1
    assert n_written == len(df)
