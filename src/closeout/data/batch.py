"""Build the labeled shot dataset for every available 2015-16 game.

Runs the single-game pipeline (download tracking, fetch play-by-play, match
shots to frames, write JSON Lines) once per game in the pinned schedule.
Each game is isolated in its own try/except -- a bad download or an
unexpected data shape in one game shouldn't stop the rest of the batch. A
game whose output file already exists is skipped, which both avoids
redundant work on a re-run and lets an interrupted batch resume without
redoing already-finished games.
"""

from __future__ import annotations

from pathlib import Path

from closeout.data.dataset import build_shot_dataset, write_shot_dataset
from closeout.data.download import download_tracking_events, fetch_playbyplay_rows
from closeout.data.schedule import load_available_games

DEFAULT_PROCESSED_DIR = Path("data/processed")


def run_batch(games: list[dict], processed_dir: Path = DEFAULT_PROCESSED_DIR) -> list[dict]:
    """Build and write a shot dataset for each game; return one result dict per game."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for game in games:
        game_id = game["game_id"]
        output_path = processed_dir / f"{game_id}.jsonl"
        if output_path.exists():
            results.append({"game_id": game_id, "status": "skipped"})
            continue

        try:
            events = download_tracking_events(game_id, game["tracking_url"])
            pbp_rows = fetch_playbyplay_rows(game_id)
            rows = build_shot_dataset(game_id, pbp_rows, events)
            write_shot_dataset(rows, str(output_path))
            results.append({"game_id": game_id, "status": "ok", "n_shots": len(rows)})
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
    _print_summary(run_batch(load_available_games()))
