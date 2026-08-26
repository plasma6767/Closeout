"""Tie play-by-play shots to their tracking frames."""

from __future__ import annotations

from closeout.data.tracking import (
    MOMENT_GAME_CLOCK,
    build_quarter_timelines,
    find_frame_for_clock,
    find_release_frame,
)

# How long before the release to also grab a frame for, so features like
# closing speed can be computed later without needing the raw tracking data
# again. Game clock counts down, so "1 second earlier" means a larger clock
# value.
PRE_SHOT_WINDOW_SECONDS = 1.0


def match_shots_to_frames(events: list[dict], shots: list[dict]) -> list[dict]:
    """Attach tracking frames to each shot: the actual release frame, and a prior frame.

    `shots` is the output of parse_shot_events(). Each returned dict is the
    original shot with two keys added: "frame" (the frame where the ball
    left the shooter's hand -- see find_release_frame) and "prior_frame"
    (the frame from about PRE_SHOT_WINDOW_SECONDS before *that*, for later
    velocity-based features). Both are anchored off the detected release,
    not the play-by-play's recorded clock, since that clock can be seconds
    after the shot actually left the shooter's hand.

    Either frame can be None -- "frame" when the ball and shooter are never
    close in the search window (a tracking gap, or a release further back
    than the window reaches), "prior_frame" when coverage doesn't reach far
    enough before the release. Whether to keep or drop unmatched shots is
    left to whatever builds the final dataset.
    """
    timelines = build_quarter_timelines(events)

    matched = []
    for shot in shots:
        timeline = timelines.get(shot["quarter"], [])
        frame = find_release_frame(timeline, shot["shooter_id"], shot["game_clock"])
        if frame is not None:
            release_clock = frame[MOMENT_GAME_CLOCK]
            prior_frame = find_frame_for_clock(timeline, release_clock + PRE_SHOT_WINDOW_SECONDS)
        else:
            prior_frame = None
        matched.append({**shot, "frame": frame, "prior_frame": prior_frame})

    return matched
