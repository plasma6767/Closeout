from closeout.data.tracking import build_quarter_timelines, find_frame_for_clock, find_release_frame


def _moment(quarter, timestamp, game_clock, positions=None):
    """Build a fake moment with just the fields build_quarter_timelines cares about."""
    return [quarter, timestamp, game_clock, 24.0, None, positions or []]


def _positions(ball_xy, shooter_id, shooter_xy):
    return [[-1, -1, *ball_xy, 6.0], [1610612744, shooter_id, *shooter_xy]]


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


def test_find_frame_for_clock_returns_exact_match():
    timeline = [_moment(1, 1000, 700.0), _moment(1, 1040, 699.0), _moment(1, 1080, 698.0)]

    frame = find_frame_for_clock(timeline, 699.0)

    assert frame[1] == 1040


def test_find_frame_for_clock_returns_closest_when_no_exact_match():
    timeline = [_moment(1, 1000, 700.0), _moment(1, 1040, 699.0), _moment(1, 1080, 698.0)]

    # 698.4 is closer to 698.0 than to 699.0
    frame = find_frame_for_clock(timeline, 698.4)

    assert frame[1] == 1080


def test_find_frame_for_clock_returns_none_when_tracking_starts_late():
    # Tracking coverage starts at 680.93s remaining, like the sample game in
    # PLAN.md -- a shot at 700s remaining happened before tracking picks up.
    timeline = [_moment(1, 1000, 680.93), _moment(1, 1040, 679.0)]

    frame = find_frame_for_clock(timeline, 700.0)

    assert frame is None


def test_find_frame_for_clock_returns_none_for_empty_timeline():
    assert find_frame_for_clock([], 700.0) is None


def test_find_release_frame_returns_last_close_approach():
    shooter_id = 201939
    timeline = [
        # a dribble touch, well before the real release
        _moment(1, 1000, 693.0, _positions((10.0, 10.0), shooter_id, (10.5, 10.0))),  # dist 0.5
        _moment(1, 1010, 692.5, _positions((15.0, 10.0), shooter_id, (10.5, 10.0))),  # dist 4.5, ball bounced away
        # the true release -- last time the ball is close to the shooter
        _moment(1, 1020, 692.0, _positions((10.3, 10.0), shooter_id, (10.4, 10.0))),  # dist 0.1
        _moment(1, 1030, 691.5, _positions((14.0, 10.0), shooter_id, (10.4, 10.0))),  # dist 3.6, in flight
        # the play-by-play's recorded clock -- ball already near the rim, far from the shooter
        _moment(1, 1040, 690.0, _positions((5.0, 25.0), shooter_id, (10.4, 10.0))),
    ]

    frame = find_release_frame(timeline, shooter_id, event_clock=690.0)

    assert frame[1] == 1020


def test_find_release_frame_returns_none_when_never_close():
    shooter_id = 201939
    timeline = [
        _moment(1, 1000, 692.0, _positions((10.0, 10.0), shooter_id, (30.0, 10.0))),
        _moment(1, 1010, 691.0, _positions((12.0, 10.0), shooter_id, (30.0, 10.0))),
    ]

    assert find_release_frame(timeline, shooter_id, event_clock=690.0) is None


def test_find_release_frame_ignores_frames_outside_the_search_window():
    shooter_id = 201939
    timeline = [
        # close approach, but 6 seconds before event_clock -- outside the default 5s window
        _moment(1, 1000, 696.0, _positions((10.0, 10.0), shooter_id, (10.2, 10.0))),
        _moment(1, 1010, 690.0, _positions((5.0, 25.0), shooter_id, (30.0, 10.0))),
    ]

    assert find_release_frame(timeline, shooter_id, event_clock=690.0) is None


def test_find_release_frame_skips_frames_missing_ball_or_shooter():
    shooter_id = 201939
    timeline = [
        _moment(1, 1000, 691.0, [[1610612744, shooter_id, 10.0, 10.0]]),  # no ball entry
        _moment(1, 1010, 690.5, _positions((10.0, 10.0), shooter_id, (10.2, 10.0))),  # dist 0.2
    ]

    frame = find_release_frame(timeline, shooter_id, event_clock=690.0)

    assert frame[1] == 1010


def test_find_release_frame_returns_none_for_empty_timeline():
    assert find_release_frame([], 201939, event_clock=690.0) is None
