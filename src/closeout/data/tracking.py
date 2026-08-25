"""Utilities for working with raw SportVU tracking moments.

Each tracking event is a clip of moments, but consecutive events' moments
overlap (a new event repeats trailing frames from the previous one as
pre-roll). Anything that needs to find a specific frame by game clock has to
work off one deduped, time-ordered timeline per quarter, not the moments of
a single event.
"""

from __future__ import annotations

import math

MOMENT_QUARTER = 0
MOMENT_TIMESTAMP = 1
MOMENT_GAME_CLOCK = 2
MOMENT_POSITIONS = 5

BALL_TEAM_ID = -1

# How far back (in game clock seconds) to search for the true release, and
# how close the ball has to be to the shooter to count as "in their hand".
# Tuned against real shots in game 0021500480: a clean jumper separates from
# the shooter almost immediately, while a driving layup's gather can drift
# the ball 1-2 ft from the body before it actually leaves the hand.
RELEASE_SEARCH_WINDOW_SECONDS = 5.0
RELEASE_NEAR_THRESHOLD_FT = 1.5


def build_quarter_timelines(events: list[dict]) -> dict[int, list[list]]:
    """Merge every event's moments into one deduped, time-ordered timeline per quarter.

    Moments are deduped by epoch timestamp (moment[MOMENT_TIMESTAMP]), since
    that's the one value guaranteed to be identical for the same real-world
    frame even when it shows up in multiple events.
    """
    moments_by_quarter: dict[int, dict[int, list]] = {}

    for event in events:
        for moment in event.get("moments", []):
            quarter = moment[MOMENT_QUARTER]
            timestamp = moment[MOMENT_TIMESTAMP]
            moments_by_quarter.setdefault(quarter, {})[timestamp] = moment

    return {
        quarter: [moments[timestamp] for timestamp in sorted(moments)]
        for quarter, moments in moments_by_quarter.items()
    }


def find_frame_for_clock(timeline: list[list], target_clock: float) -> list | None:
    """Find the frame in a quarter's timeline closest to a play-by-play game clock.

    `timeline` must already be one quarter's deduped, time-ordered moments,
    e.g. one value from build_quarter_timelines()'s result.

    Returns None if tracking coverage for the quarter starts after the shot
    already happened -- tracking doesn't always start at the true beginning
    of a quarter, so the earliest frame available can already show a lower
    game clock than the shot we're looking for. That's a real gap, not
    something to paper over with a "closest available" guess.
    """
    if not timeline:
        return None

    if timeline[0][MOMENT_GAME_CLOCK] < target_clock:
        return None

    return min(timeline, key=lambda moment: abs(moment[MOMENT_GAME_CLOCK] - target_clock))


def find_release_frame(
    timeline: list[list],
    shooter_id: int,
    event_clock: float,
    search_window_seconds: float = RELEASE_SEARCH_WINDOW_SECONDS,
    near_threshold_ft: float = RELEASE_NEAR_THRESHOLD_FT,
) -> list | None:
    """Find the frame where the ball actually left the shooter's hand.

    The play-by-play clock recorded for a shot attempt lags the true release
    by anywhere from ~1.5 to 3.5 seconds in practice -- it reflects roughly
    when the shot resolves (ball reaching the rim, a rebound scramble), not
    when it left the shooter's hand. Trusting it directly (as
    find_frame_for_clock does) lands on a frame where the shooter can be 20+
    feet from the ball.

    Instead, this scans backward from event_clock, up to
    search_window_seconds, for the last frame where the ball was within
    near_threshold_ft of the shooter. A dribble (or a driving layup's
    gather, which can drift the ball a foot or two from the body before it's
    actually released) always brings the ball back close to the hand again;
    the true release never does. So the last close approach in the window
    is, by construction, the release -- no need to separately detect a rise
    in the ball's height, which also means this works the same way for a
    flat-arced dunk as it does for a high-arcing jumper.

    Returns None if the ball and shooter are never within near_threshold_ft
    in the window -- a real tracking gap, or a shot whose true release
    happened further back than the window reaches. Callers should drop the
    shot rather than guess.
    """
    window = [
        moment
        for moment in timeline
        if event_clock <= moment[MOMENT_GAME_CLOCK] <= event_clock + search_window_seconds
    ]
    window.sort(key=lambda moment: -moment[MOMENT_GAME_CLOCK])  # chronological order

    release_frame = None
    for moment in window:
        positions = moment[MOMENT_POSITIONS]
        ball = next((p for p in positions if p[0] == BALL_TEAM_ID), None)
        shooter = next((p for p in positions if p[1] == shooter_id), None)
        if ball is None or shooter is None:
            continue
        distance = math.hypot(ball[2] - shooter[2], ball[3] - shooter[3])
        if distance <= near_threshold_ft:
            release_frame = moment

    return release_frame
