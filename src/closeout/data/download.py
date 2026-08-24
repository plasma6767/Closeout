"""Fetch the two raw inputs the shot dataset pipeline needs for one game.

Both fetches cache their result to disk and skip re-fetching when the cache
is already there -- a season's worth of games means ~42 archive downloads
and ~42 stats-endpoint calls, and re-running the batch job (e.g. after a
downstream bug fix) shouldn't have to pay that cost again.
"""

from __future__ import annotations

import json
from pathlib import Path

import py7zr
import requests
from nba_api.stats.endpoints import playbyplayv3


def download_tracking_events(game_id: str, tracking_url: str, raw_dir: Path) -> list[dict]:
    """Download (if not cached), extract, and return a game's tracking events."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / f"{game_id}.7z"

    if not archive_path.exists():
        response = requests.get(tracking_url, timeout=60)
        response.raise_for_status()
        archive_path.write_bytes(response.content)

    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        (json_name,) = archive.getnames()
        json_path = raw_dir / json_name
        if not json_path.exists():
            archive.extractall(path=raw_dir)

    return json.loads(json_path.read_text())["events"]


def fetch_playbyplay_rows(game_id: str, raw_dir: Path) -> list[dict]:
    """Fetch (if not cached) a game's play-by-play rows from PlayByPlayV3."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_path = raw_dir / f"{game_id}_pbp.json"

    if cache_path.exists():
        return json.loads(cache_path.read_text())

    rows = playbyplayv3.PlayByPlayV3(game_id=game_id).get_data_frames()[0].to_dict("records")
    cache_path.write_text(json.dumps(rows))
    return rows
