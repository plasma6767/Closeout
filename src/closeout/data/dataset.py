"""Build the labeled shot dataset: one row per shot, matched to its tracking frame."""

from __future__ import annotations

import json

from closeout.data.matching import match_shots_to_frames
from closeout.data.playbyplay import parse_shot_events
from closeout.data.tracking import BALL_TEAM_ID, MOMENT_GAME_CLOCK


def _positions_from_frame(frame: list) -> tuple[list, list] | None:
    """Split a frame's positions into (ball, players), or None if the ball wasn't tracked."""
    positions = frame[5]
    ball = next((p for p in positions if p[0] == BALL_TEAM_ID), None)
    if ball is None:
        return None
    players = [
        {"team_id": p[0], "player_id": p[1], "x": p[2], "y": p[3]}
        for p in positions
        if p[0] != BALL_TEAM_ID
    ]
    return ball, players


def _prior_frame_fields(prior_frame: list | None) -> dict:
    """Prior-frame ball/player positions for later speed features, or {} if unavailable."""
    if prior_frame is None:
        return {}
    split = _positions_from_frame(prior_frame)
    if split is None:
        return {}
    ball, players = split
    return {
        "prior_game_clock": prior_frame[MOMENT_GAME_CLOCK],
        "prior_ball_x": ball[2],
        "prior_ball_y": ball[3],
        "prior_ball_z": ball[4],
        "prior_players": players,
    }


def build_shot_dataset(game_id: str, pbp_rows: list[dict], events: list[dict]) -> list[dict]:
    """Build one row per shot for a game: shooter identity, make/miss, and release-frame positions.

    Shots get dropped here, rather than producing a row with missing data,
    when: there's no matched release frame (tracking coverage gaps, or a
    release the search window in match_shots_to_frames doesn't reach -- see
    find_release_frame), or the matched frame has no ball entry at all (the
    ball is occasionally untracked/occluded for a given frame in the raw
    data). Each row also carries positions from about a second before the
    release (prior_* fields, absent if that frame isn't available) so
    features like closing speed can be computed later without needing the
    raw tracking data again. Defender distance/angle and other derived
    features are computed later, in features/, not here.
    """
    shots = parse_shot_events(pbp_rows)
    matched = match_shots_to_frames(events, shots)
    pbp_by_action_number = {row["actionNumber"]: row for row in pbp_rows}

    rows = []
    for shot in matched:
        if shot["frame"] is None:
            continue

        split = _positions_from_frame(shot["frame"])
        if split is None:
            continue
        ball, players = split

        pbp_row = pbp_by_action_number[shot["event_id"]]
        row = {
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
        row.update(_prior_frame_fields(shot["prior_frame"]))

        rows.append(row)

    return rows


def write_shot_dataset(rows: list[dict], path: str) -> None:
    """Write shot rows as JSON Lines, one shot per line."""
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
