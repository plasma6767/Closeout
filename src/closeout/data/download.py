"""Fetch the two raw inputs the shot dataset pipeline needs for one game.

Neither fetch is cached to disk -- the tracking archive decompresses to
~100MB per game, and across the whole season that adds up to tens of GB for
data that's only needed transiently to build a much smaller shot dataset.
Once build_shot_dataset() has pulled out what it needs (including a second,
pre-shot frame per shot -- see matching.py), there's nothing left worth
keeping raw.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import py7zr
import requests
from nba_api.stats.endpoints import playbyplayv3


def download_tracking_events(game_id: str, tracking_url: str) -> list[dict]:
    """Download and extract a game's tracking events. Nothing is left on disk afterward."""
    response = requests.get(tracking_url, timeout=60)
    response.raise_for_status()

    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / f"{game_id}.7z"
        archive_path.write_bytes(response.content)

        with py7zr.SevenZipFile(archive_path, mode="r") as archive:
            archive.extractall(path=tmp_dir)

        json_paths = list(Path(tmp_dir).glob("*.json"))
        if not json_paths:
            # happens for a handful of games in the mirror whose archive is
            # a valid but empty 7z file -- nothing to extract, not our bug
            raise ValueError(f"tracking archive for {game_id} contains no JSON file (source archive is empty)")
        return json.loads(json_paths[0].read_text())["events"]


def fetch_playbyplay_rows(game_id: str) -> list[dict]:
    """Fetch a game's play-by-play rows from the NBA's PlayByPlayV3 endpoint."""
    return playbyplayv3.PlayByPlayV3(game_id=game_id).get_data_frames()[0].to_dict("records")
