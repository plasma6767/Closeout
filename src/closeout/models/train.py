"""Train and evaluate the shot-quality models, then score expected FG% for every shot.

Compares a logistic-regression baseline (shot distance only) against an
xgboost model using every engineered feature, on games neither model
trained on -- see dataset.py:split_by_game for why the split is by game,
not by shot. Whichever model has the lower held-out log-loss gets refit on
the full dataset and used to score expected_fg_pct per shot, written to
data/predictions/ -- the input the Curry actual-vs-expected analysis
(roadmap item 4) needs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import xgboost as xgb
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

from closeout.models.dataset import (
    DEFAULT_FEATURES_DIR,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    load_features,
    split_by_game,
)

DEFAULT_PREDICTIONS_DIR = Path("data/predictions")

BASELINE_COLUMNS = ["shot_distance_ft"]


def prepare_features(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Feature columns as float dtypes, preserving NaN for missing values (xgboost handles NaN natively)."""
    return df[columns].astype(float)


def train_baseline(train_df: pd.DataFrame) -> LogisticRegression:
    model = LogisticRegression()
    model.fit(prepare_features(train_df, BASELINE_COLUMNS), train_df[TARGET_COLUMN])
    return model


def train_full_model(train_df: pd.DataFrame) -> xgb.XGBClassifier:
    model = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, eval_metric="logloss")
    model.fit(prepare_features(train_df, FEATURE_COLUMNS), train_df[TARGET_COLUMN])
    return model


def evaluate(model, test_df: pd.DataFrame, columns: list[str]) -> dict:
    """AUC, log-loss, and a 10-bucket calibration table for a fitted model on held-out shots.

    Calibration buckets are by quantile (equal shot counts per bucket)
    rather than equal probability width -- most shots cluster in a narrow
    probability range, so equal-width buckets would leave several buckets
    almost empty and unreliable.
    """
    X_test = prepare_features(test_df, columns)
    y_test = test_df[TARGET_COLUMN]
    predicted = model.predict_proba(X_test)[:, 1]

    actual_rate, predicted_rate = calibration_curve(y_test, predicted, n_bins=10, strategy="quantile")
    return {
        "auc": roc_auc_score(y_test, predicted),
        "log_loss": log_loss(y_test, predicted),
        "calibration": list(zip(predicted_rate, actual_rate)),
    }


def score_expected_fg_pct(model, df: pd.DataFrame, columns: list[str]) -> pd.Series:
    X = prepare_features(df, columns)
    return pd.Series(model.predict_proba(X)[:, 1], index=df.index)


def write_predictions(
    df: pd.DataFrame,
    features_dir: Path = DEFAULT_FEATURES_DIR,
    predictions_dir: Path = DEFAULT_PREDICTIONS_DIR,
) -> None:
    """Write expected_fg_pct back out per game, alongside the original feature rows.

    Reads each game's rows fresh from its features file rather than
    round-tripping through the DataFrame, so every value written stays a
    plain JSON-native type instead of a numpy scalar (which json.dumps
    can't always serialize).
    """
    predictions_dir = Path(predictions_dir)
    predictions_dir.mkdir(parents=True, exist_ok=True)
    expected = dict(zip(zip(df["game_id"], df["event_id"]), df["expected_fg_pct"]))

    for path in sorted(Path(features_dir).glob("*.jsonl")):
        game_id = path.stem
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row["expected_fg_pct"] = float(expected[(row["game_id"], row["event_id"])])
        with (predictions_dir / f"{game_id}.jsonl").open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")


def run_training(
    features_dir: Path = DEFAULT_FEATURES_DIR,
    predictions_dir: Path = DEFAULT_PREDICTIONS_DIR,
    seed: int = 42,
) -> dict:
    df = load_features(features_dir)
    train_df, test_df = split_by_game(df, seed=seed)

    baseline = train_baseline(train_df)
    full_model = train_full_model(train_df)

    baseline_metrics = evaluate(baseline, test_df, BASELINE_COLUMNS)
    full_metrics = evaluate(full_model, test_df, FEATURE_COLUMNS)

    if full_metrics["log_loss"] <= baseline_metrics["log_loss"]:
        winner, winner_columns = "full", FEATURE_COLUMNS
        final_model = train_full_model(df)
    else:
        winner, winner_columns = "baseline", BASELINE_COLUMNS
        final_model = train_baseline(df)

    df["expected_fg_pct"] = score_expected_fg_pct(final_model, df, winner_columns)
    write_predictions(df, features_dir, predictions_dir)

    return {"baseline": baseline_metrics, "full": full_metrics, "winner": winner, "n_shots": len(df)}


def _print_summary(results: dict) -> None:
    print(f"{results['n_shots']} shots, winner: {results['winner']}")
    for name in ("baseline", "full"):
        m = results[name]
        print(f"  {name}: AUC={m['auc']:.4f}  log_loss={m['log_loss']:.4f}")
    print(f"  calibration ({results['winner']}, predicted vs. actual make rate by decile):")
    for predicted_rate, actual_rate in results[results["winner"]]["calibration"]:
        print(f"    predicted {predicted_rate:.2f}  actual {actual_rate:.2f}")


if __name__ == "__main__":
    _print_summary(run_training())
