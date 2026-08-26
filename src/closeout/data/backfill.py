"""Backfill shot_type/assisted onto shot rows that were written before those fields existed.

The 632 games already processed into data/processed/*.jsonl were built
before parse_shot_events() captured shot_type and assisted. Re-running the
full pipeline would mean re-downloading every game's tracking archive again
just to get two fields that only ever came from play-by-play in the first
place. This re-fetches play-by-play only (fast, no tracking download) and
merges the two fields onto the existing rows by event_id, which every row
already has.
"""

from __future__ import annotations

import json
from pathlib import Path

from closeout.data.download import fetch_playbyplay_rows
from closeout.data.playbyplay import parse_shot_events

DEFAULT_PROCESSED_DIR = Path("data/processed")


def backfill_rows(rows: list[dict], pbp_rows: list[dict]) -> list[dict]:
    """Merge shot_type/assisted from freshly-parsed play-by-play onto existing rows.

    Matches by event_id, which is the same actionNumber both the existing
    rows and a fresh parse_shot_events() call key off of. Raises if a row's
    event_id has no match in the fresh play-by-play -- that would mean the
    game's play-by-play changed shape since it was first ingested, which is
    a real problem worth stopping for, not silently skipping.
    """
    shots_by_event_id = {shot["event_id"]: shot for shot in parse_shot_events(pbp_rows)}

    backfilled = []
    for row in rows:
        shot = shots_by_event_id.get(row["event_id"])
        if shot is None:
            raise ValueError(
                f"no play-by-play shot found for event_id {row['event_id']} "
                f"in game {row.get('game_id')} -- play-by-play may have changed"
            )
        backfilled.append({**row, "shot_type": shot["shot_type"], "assisted": shot["assisted"]})

    return backfilled


def backfill_game(game_id: str) -> list[dict]:
    """Read one game's processed file, backfill it, and return the updated rows (not written)."""
    path = DEFAULT_PROCESSED_DIR / f"{game_id}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    pbp_rows = fetch_playbyplay_rows(game_id)
    return backfill_rows(rows, pbp_rows)


def run_backfill(processed_dir: Path = DEFAULT_PROCESSED_DIR) -> list[dict]:
    """Backfill every already-processed game in place; return one result dict per game."""
    results = []
    for path in sorted(processed_dir.glob("*.jsonl")):
        game_id = path.stem
        rows = [json.loads(line) for line in path.read_text().splitlines()]

        if rows and "shot_type" in rows[0]:
            results.append({"game_id": game_id, "status": "skipped"})
            continue

        try:
            pbp_rows = fetch_playbyplay_rows(game_id)
            backfilled = backfill_rows(rows, pbp_rows)
            with path.open("w") as f:
                for row in backfilled:
                    f.write(json.dumps(row) + "\n")
            results.append({"game_id": game_id, "status": "ok", "n_shots": len(backfilled)})
        except Exception as exc:
            results.append({"game_id": game_id, "status": "error", "error": str(exc)})

    return results


def _print_summary(results: list[dict]) -> None:
    ok = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors = [r for r in results if r["status"] == "error"]
    print(f"{len(ok)} backfilled, {len(skipped)} skipped (already done), {len(errors)} failed")
    for r in errors:
        print(f"  FAILED {r['game_id']}: {r['error']}")


if __name__ == "__main__":
    _print_summary(run_backfill())
