"""Parsing for raw NBA `PlayByPlayV3` rows.

Field names below (actionNumber, period, clock, isFieldGoal, shotResult,
subType, description) come from nba_api's PlayByPlayV3 dataset headers. The
clock field is an ISO 8601 duration string like "PT11M32.00S", not numeric
seconds.
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


def _is_assisted(description: str) -> bool:
    """Whether a shot's description records an assist.

    PlayByPlayV3 has no dedicated assist field -- confirmed against real
    responses, it's always None even for assisted makes. The assist only
    shows up in the free-text description, always as the last parenthetical,
    e.g. "Towns 13' Jump Shot (2 PTS) (Wiggins 1 AST)" vs. the unassisted
    "Rubio 17' Pullup Jump Shot (2 PTS)". Missed shots never have an assist.
    """
    return description.rstrip().endswith("AST)")


def shot_rows_by_action_number(rows: list[dict]) -> dict[int, dict]:
    """Map actionNumber -> the real shot-attempt row, restricted to field goals.

    A blocked shot (and, separately, a turnover) generates a second
    play-by-play row at the *same* actionNumber crediting the blocker or
    stealer (isFieldGoal False). A naive {actionNumber: row} dict built
    from every row lets that companion row silently clobber the real
    shot's entry -- confirmed against a real game where a missed, blocked
    Singler layup ended up attributed to Faried (the blocker) because his
    companion "BLOCK" row happened to come later in the list. Filtering to
    isFieldGoal rows before building the dict avoids that collision.
    """
    return {row["actionNumber"]: row for row in rows if row.get("isFieldGoal")}


def parse_shot_events(rows: list[dict]) -> list[dict]:
    """Pull shot attempts out of raw PlayByPlayV3 rows.

    Only rows with isFieldGoal set are shot attempts -- everything else
    (fouls, rebounds, timeouts, substitutions, etc.) is dropped. Each
    returned dict has what find_release_frame() needs (event_id, quarter,
    game_clock, shooter_id), the make/miss label, and the raw shot type
    (subType, e.g. "Pullup Jump shot") plus whether it was assisted --
    both needed for the catch-and-shoot proxy computed in features/.
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
                "shooter_id": row["personId"],
                "made": row["shotResult"] == "Made",
                "shot_type": row["subType"],
                "assisted": _is_assisted(row["description"]),
            }
        )
    return shots
