"""The pinned list of 2015-16 games that have tracking data available.

The join from NBA game_id to tracking-file download URL (matching the full
2015-16 league schedule against the file listing in the
linouk23/NBA-Player-Movements GitHub mirror, by date + home/away teams) was
done once and pinned as a static resource here, rather than re-derived from
two live APIs on every run -- the 2015-16 season is over and its game IDs
never change, so re-joining on every run would only add two more places the
batch job could fail, for no benefit.

One file in the mirror (`01.23.2016.UTA.at.WAS.7z`) doesn't correspond to
any real game in the official schedule and is excluded here.
"""

from __future__ import annotations

import json
from importlib import resources


def load_available_games() -> list[dict]:
    """Return the pinned games: one dict per game with game_id and tracking_url."""
    games_file = resources.files("closeout.data.resources").joinpath("season_2015_16_games.json")
    return json.loads(games_file.read_text())
