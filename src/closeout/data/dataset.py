"""Build the labeled shot dataset: one row per shot, matched to its tracking frame."""

from __future__ import annotations

import json

from closeout.data.matching import match_shots_to_frames
from closeout.data.playbyplay import parse_shot_events

BALL_TEAM_ID = -1


def build_shot_dataset(game_id: str, pbp_rows: list[dict], events: list[dict]) -> list[dict]:
    """Build one row per shot for a game: shooter identity, make/miss, and raw frame positions.

    Shots get dropped here, rather than producing a row with missing data,
    when: there's no matched frame (tracking coverage gaps -- see
    match_shots_to_frames), or the matched frame has no ball entry at all
    (the ball is occasionally untracked/occluded for a given frame in the
    raw data). Defender distance/angle and other derived features are
    computed later, in features/, not here.
    """
    shots = parse_shot_events(pbp_rows)
    matched = match_shots_to_frames(events, shots)
    pbp_by_action_number = {row["actionNumber"]: row for row in pbp_rows}

    rows = []
    for shot in matched:
        if shot["frame"] is None:
            continue

        pbp_row = pbp_by_action_number[shot["event_id"]]
        positions = shot["frame"][5]
        ball = next((p for p in positions if p[0] == BALL_TEAM_ID), None)
        if ball is None:
            continue
        players = [
            {"team_id": p[0], "player_id": p[1], "x": p[2], "y": p[3]}
            for p in positions
            if p[0] != BALL_TEAM_ID
        ]

        rows.append(
            {
                "game_id": game_id,
                "event_id": shot["event_id"],
                "quarter": shot["quarter"],
                "game_clock": shot["game_clock"],
                "shooter_id": pbp_row["personId"],
                "shooter_name": pbp_row["playerName"],
                "team": pbp_row["teamTricode"],
                "made": shot["made"],
                "ball_x": ball[2],
                "ball_y": ball[3],
                "ball_z": ball[4],
                "players": players,
            }
        )

    return rows


def write_shot_dataset(rows: list[dict], path: str) -> None:
    """Write shot rows as JSON Lines, one shot per line."""
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
