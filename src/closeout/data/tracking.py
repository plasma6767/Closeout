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
