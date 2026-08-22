"""Parsing for raw NBA `PlayByPlayV3` rows.

Field names below (actionNumber, period, clock, isFieldGoal, shotResult)
come from nba_api's PlayByPlayV3 dataset headers. The clock field is an
ISO 8601 duration string like "PT11M32.00S", not numeric seconds.
"""

from __future__ import annotations

import re

_CLOCK_PATTERN = re.compile(r"PT(?P<minutes>\d+)M(?P<seconds>[\d.]+)S")


def parse_game_clock(clock: str) -> float:
    """Convert a play-by-play clock string like 'PT11M32.00S' into seconds remaining."""
    match = _CLOCK_PATTERN.fullmatch(clock)
    if not match:
        raise ValueError(f"unrecognized game clock format: {clock!r}")
    return int(match.group("minutes")) * 60 + float(match.group("seconds"))


def parse_shot_events(rows: list[dict]) -> list[dict]:
    """Pull shot attempts out of raw PlayByPlayV3 rows.

    Only rows with isFieldGoal set are shot attempts -- everything else
    (fouls, rebounds, timeouts, substitutions, etc.) is dropped. Each
    returned dict has exactly what find_frame_for_clock() needs
    (event_id, quarter, game_clock) plus the make/miss label.
    """
    shots = []
    for row in rows:
        if not row.get("isFieldGoal"):
            continue
        shots.append(
            {
                "event_id": row["actionNumber"],
                "quarter": row["period"],
                "game_clock": parse_game_clock(row["clock"]),
                "made": row["shotResult"] == "Made",
            }
        )
    return shots
