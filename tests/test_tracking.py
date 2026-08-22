from closeout.data.tracking import build_quarter_timelines


def _moment(quarter, timestamp, game_clock):
    """Build a fake moment with just the fields build_quarter_timelines cares about."""
    return [quarter, timestamp, game_clock, 24.0, None, []]


def test_dedupes_overlapping_moments_across_events():
    # event_b's first frame is the same real-world moment as event_a's last
    # frame (same timestamp) -- this is the pre-roll overlap.
    event_a = {"moments": [_moment(1, 1000, 700.0), _moment(1, 1040, 699.0)]}
    event_b = {"moments": [_moment(1, 1040, 699.0), _moment(1, 1080, 698.0)]}

    timelines = build_quarter_timelines([event_a, event_b])

    timestamps = [moment[1] for moment in timelines[1]]
    assert timestamps == [1000, 1040, 1080]


def test_separates_moments_by_quarter():
    event = {"moments": [_moment(1, 1000, 5.0), _moment(2, 2000, 700.0)]}

    timelines = build_quarter_timelines([event])

    assert set(timelines.keys()) == {1, 2}
    assert timelines[1][0][1] == 1000
    assert timelines[2][0][1] == 2000


def test_orders_moments_by_timestamp_even_if_input_is_out_of_order():
    event = {
        "moments": [
            _moment(1, 3000, 690.0),
            _moment(1, 1000, 700.0),
            _moment(1, 2000, 695.0),
        ]
    }

    timelines = build_quarter_timelines([event])

    assert [moment[1] for moment in timelines[1]] == [1000, 2000, 3000]
