"""Tie play-by-play shots to their tracking frames."""

from __future__ import annotations

from closeout.data.tracking import build_quarter_timelines, find_frame_for_clock


def match_shots_to_frames(events: list[dict], shots: list[dict]) -> list[dict]:
    """Attach a tracking frame to each shot, matching on quarter + game clock.

    `shots` is the output of parse_shot_events(). Each returned dict is the
    original shot with a "frame" key added -- the matched frame, or None if
    tracking coverage doesn't reach that shot's game clock (e.g. it happened
    before tracking picked up for the quarter). Whether to keep or drop
    unmatched shots is left to whatever builds the final dataset.
    """
    timelines = build_quarter_timelines(events)

    matched = []
    for shot in shots:
        timeline = timelines.get(shot["quarter"], [])
        frame = find_frame_for_clock(timeline, shot["game_clock"])
        matched.append({**shot, "frame": frame})

    return matched
