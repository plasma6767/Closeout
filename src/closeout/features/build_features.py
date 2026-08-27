"""Compute shot-quality features for every processed game and write them to data/features/.

Kept separate from data/processed/ so features can be recomputed any time
(cheap, no network calls, no tracking data) without touching the raw
ingested dataset. Requires data/processed/ to already be backfilled with
shot_type/assisted (see data/backfill.py) -- catch_and_shoot comes back
None for rows that aren't.
"""

from __future__ import annotations

import json
from pathlib import Path

from closeout.features.shot_features import add_shot_features

DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_FEATURES_DIR = Path("data/features")


def build_game_features(processed_path: Path) -> list[dict]:
    """Read one game's processed shots and add shot-quality features to each."""
    rows = [json.loads(line) for line in processed_path.read_text().splitlines()]
    return add_shot_features(rows)


def run_build_features(
    processed_dir: Path = DEFAULT_PROCESSED_DIR, features_dir: Path = DEFAULT_FEATURES_DIR
) -> list[dict]:
    """Build and write a feature dataset for every game in processed_dir; return one result per game."""
    features_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for processed_path in sorted(processed_dir.glob("*.jsonl")):
        game_id = processed_path.stem
        output_path = features_dir / f"{game_id}.jsonl"
        if output_path.exists():
            results.append({"game_id": game_id, "status": "skipped"})
            continue

        try:
            featured_rows = build_game_features(processed_path)
            with output_path.open("w") as f:
                for row in featured_rows:
                    f.write(json.dumps(row) + "\n")
            results.append({"game_id": game_id, "status": "ok", "n_shots": len(featured_rows)})
        except Exception as exc:
            results.append({"game_id": game_id, "status": "error", "error": str(exc)})

    return results


def _print_summary(results: list[dict]) -> None:
    ok = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors = [r for r in results if r["status"] == "error"]
    total_shots = sum(r["n_shots"] for r in ok)
    print(f"{len(ok)} processed, {len(skipped)} skipped (already done), {len(errors)} failed")
    print(f"{total_shots} shots total")
    for r in errors:
        print(f"  FAILED {r['game_id']}: {r['error']}")


if __name__ == "__main__":
    _print_summary(run_build_features())
