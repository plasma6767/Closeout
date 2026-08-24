"""Build the labeled shot dataset for every available Warriors game.

Runs the single-game pipeline (download tracking, fetch play-by-play, match
shots to frames, write JSON Lines) once per game in the pinned schedule.
Each game is isolated in its own try/except -- a bad download or an
unexpected data shape in one game shouldn't stop the rest of the batch, since
the goal is to end up with as much of the season as the source data allows,
not an all-or-nothing run.
"""

from __future__ import annotations

from pathlib import Path

from closeout.data.dataset import build_shot_dataset, write_shot_dataset
from closeout.data.download import download_tracking_events, fetch_playbyplay_rows
from closeout.data.schedule import load_warriors_games

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_PROCESSED_DIR = Path("data/processed")


def run_batch(
    games: list[dict],
    raw_dir: Path = DEFAULT_RAW_DIR,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
) -> list[dict]:
    """Build and write a shot dataset for each game; return one result dict per game."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for game in games:
        game_id = game["game_id"]
        try:
            events = download_tracking_events(game_id, game["tracking_url"], raw_dir)
            pbp_rows = fetch_playbyplay_rows(game_id, raw_dir)
            rows = build_shot_dataset(game_id, pbp_rows, events)
            write_shot_dataset(rows, str(processed_dir / f"{game_id}.jsonl"))
            results.append({"game_id": game_id, "status": "ok", "n_shots": len(rows)})
        except Exception as exc:
            results.append({"game_id": game_id, "status": "error", "error": str(exc)})

    return results


def _print_summary(results: list[dict]) -> None:
    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]
    total_shots = sum(r["n_shots"] for r in ok)
    print(f"{len(ok)}/{len(results)} games processed, {total_shots} shots total")
    for r in errors:
        print(f"  FAILED {r['game_id']}: {r['error']}")


if __name__ == "__main__":
    _print_summary(run_batch(load_warriors_games()))
