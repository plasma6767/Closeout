"""Tie play-by-play shots to their tracking frames."""

from __future__ import annotations

from closeout.data.tracking import build_quarter_timelines, find_frame_for_clock

# How long before the shot to also grab a frame for, so features like
# closing speed can be computed later without needing the raw tracking data
# again. Game clock counts down, so "1 second earlier" means a larger clock
# value.
PRE_SHOT_WINDOW_SECONDS = 1.0


def match_shots_to_frames(events: list[dict], shots: list[dict]) -> list[dict]:
    """Attach tracking frames to each shot, matching on quarter + game clock.

    `shots` is the output of parse_shot_events(). Each returned dict is the
    original shot with two keys added: "frame" (the matched frame at the
    shot itself) and "prior_frame" (the frame from about
    PRE_SHOT_WINDOW_SECONDS earlier, for later velocity-based features).
    Either can be None if tracking coverage doesn't reach that far back
    (e.g. the shot happened right as tracking picked up for the quarter).
    Whether to keep or drop unmatched shots is left to whatever builds the
    final dataset.
    """
    timelines = build_quarter_timelines(events)

    matched = []
    for shot in shots:
        timeline = timelines.get(shot["quarter"], [])
        frame = find_frame_for_clock(timeline, shot["game_clock"])
        prior_frame = find_frame_for_clock(timeline, shot["game_clock"] + PRE_SHOT_WINDOW_SECONDS)
        matched.append({**shot, "frame": frame, "prior_frame": prior_frame})

    return matched
