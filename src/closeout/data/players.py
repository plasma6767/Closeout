"""Look up a player's full name for display -- play-by-play only records
last names (see analysis/shot_quality.py), which is confusing anywhere two
players share one (Stephen and Seth Curry both played in 2015-16). nba_api
ships a static, offline player index that has full names, keyed by the same
player_id already used throughout this project.
"""

from __future__ import annotations

from nba_api.stats.static import players as nba_static_players


def full_name_for(shooter_id: int, fallback: str) -> str:
    """The player's full name (e.g. "Stephen Curry"), or `fallback` if the id isn't in the static index."""
    player = nba_static_players.find_player_by_id(int(shooter_id))
    return player["full_name"] if player else fallback
