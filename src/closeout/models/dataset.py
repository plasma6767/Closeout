"""Load the shot-quality feature dataset for modeling and split it into train/test sets.

Kept separate from features/build_features.py, which only computes and
writes per-game feature files -- this module is purely about assembling
those already-written files into one table a model can train on.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd

DEFAULT_FEATURES_DIR = Path("data/features")

# The engineered features the full model trains on -- see
# features/shot_features.py:compute_shot_features for how each is derived.
FEATURE_COLUMNS = [
    "shot_distance_ft",
    "shot_angle_deg",
    "closest_defender_dist_ft",
    "closest_defender_angle_deg",
    "second_defender_dist_ft",
    "second_defender_angle_deg",
    "shooter_speed_ftps",
    "closest_defender_closing_speed_ftps",
    "catch_and_shoot",
]

TARGET_COLUMN = "made"


def load_features(features_dir: Path = DEFAULT_FEATURES_DIR) -> pd.DataFrame:
    """Load every game's feature file in features_dir into one table, one row per shot."""
    rows = []
    for path in sorted(Path(features_dir).glob("*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text().splitlines())
    return pd.DataFrame(rows)


def split_by_game(df: pd.DataFrame, test_size: float = 0.2, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split shots into train/test by game_id, not by individual shot.

    Splitting shot-by-shot would let shots from the same game land on both
    sides of the split -- every shot in a game shares the same personnel,
    pace, and matchups, so that would leak information a model wouldn't
    actually have about a truly unseen game. Grouping by game_id keeps a
    whole game on one side or the other.
    """
    game_ids = sorted(df["game_id"].unique())
    rng = random.Random(seed)
    rng.shuffle(game_ids)

    n_test = round(len(game_ids) * test_size)
    test_games = set(game_ids[:n_test])

    is_test = df["game_id"].isin(test_games)
    train_df = df[~is_test].reset_index(drop=True)
    test_df = df[is_test].reset_index(drop=True)
    return train_df, test_df
