"""Utilities for working with raw SportVU tracking moments.

Each tracking event is a clip of moments, but consecutive events' moments
overlap (a new event repeats trailing frames from the previous one as
pre-roll). Anything that needs to find a specific frame by game clock has to
work off one deduped, time-ordered timeline per quarter, not the moments of
a single event.
"""

from __future__ import annotations

MOMENT_QUARTER = 0
MOMENT_TIMESTAMP = 1
MOMENT_GAME_CLOCK = 2


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
