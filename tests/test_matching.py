from closeout.data.matching import match_shots_to_frames

SHOOTER_ID = 201939


def _moment(quarter, timestamp, game_clock, positions=None):
    return [quarter, timestamp, game_clock, 24.0, None, positions or []]


def _positions(ball_xy, shooter_xy, shooter_id=SHOOTER_ID):
    return [[-1, -1, *ball_xy, 6.0], [1610612744, shooter_id, *shooter_xy]]


def _shot(event_id, quarter, game_clock, made=True, shooter_id=SHOOTER_ID):
    return {"event_id": event_id, "quarter": quarter, "game_clock": game_clock, "shooter_id": shooter_id, "made": made}


def test_matches_shot_to_the_release_frame_not_the_recorded_clock():
    # the recorded event clock (699.0) lands on a frame where the ball is
    # already far from the shooter -- the real release was a second earlier
    events = [
        {
            "moments": [
                _moment(1, 1000, 700.0, _positions((10.0, 10.0), (10.2, 10.0))),  # release, dist 0.2
                _moment(1, 1040, 699.0, _positions((5.0, 25.0), (10.2, 10.0))),  # recorded clock, ball far away
            ]
        }
    ]
    shots = [_shot(101, 1, 699.0)]

    matched = match_shots_to_frames(events, shots)

    assert len(matched) == 1
    assert matched[0]["event_id"] == 101
    assert matched[0]["frame"][1] == 1000


def test_matches_shot_to_the_last_close_approach_before_the_recorded_clock():
    events = [
        {
            "moments": [
                _moment(1, 1000, 701.0, _positions((10.0, 10.0), (10.5, 10.0))),  # earlier dribble touch, dist 0.5
                _moment(1, 1010, 700.5, _positions((15.0, 10.0), (10.5, 10.0))),  # bounced away
                _moment(1, 1020, 700.0, _positions((10.3, 10.0), (10.4, 10.0))),  # true release, dist 0.1
                _moment(1, 1030, 699.5, _positions((5.0, 25.0), (10.4, 10.0))),  # recorded clock
            ]
        }
    ]
    shots = [_shot(102, 1, 699.5)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"][1] == 1020


def test_returns_none_frame_when_ball_and_shooter_are_never_close():
    events = [{"moments": [_moment(1, 1000, 700.0, _positions((30.0, 10.0), (10.0, 10.0)))]}]
    shots = [_shot(103, 1, 700.0)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"] is None
    assert matched[0]["event_id"] == 103


def test_returns_none_frame_for_quarter_with_no_tracking_at_all():
    events = [{"moments": [_moment(1, 1000, 700.0, _positions((10.0, 10.0), (10.2, 10.0)))]}]
    shots = [_shot(104, 2, 700.0)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"] is None


def test_preserves_shot_order_and_all_shot_fields():
    events = [{"moments": [_moment(1, 1000, 700.0, _positions((10.0, 10.0), (10.2, 10.0)))]}]
    shots = [_shot(105, 1, 700.0, made=False), _shot(106, 1, 700.0, made=True)]

    matched = match_shots_to_frames(events, shots)

    assert [shot["event_id"] for shot in matched] == [105, 106]
    assert matched[0]["made"] is False
    assert matched[1]["made"] is True


def test_also_matches_a_prior_frame_about_one_second_before_the_release():
    # game clock counts down, so "1 second earlier" is a larger clock value
    events = [
        {
            "moments": [
                _moment(1, 1000, 701.0, _positions((10.0, 10.0), (10.2, 10.0))),  # 1s before the release
                _moment(1, 1040, 700.0, _positions((10.5, 10.0), (10.4, 10.0))),  # release
            ]
        }
    ]
    shots = [_shot(107, 1, 700.0)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"][1] == 1040
    assert matched[0]["prior_frame"][1] == 1000


def test_prior_frame_is_none_when_coverage_does_not_reach_far_enough_back():
    events = [{"moments": [_moment(1, 1000, 700.0, _positions((10.0, 10.0), (10.2, 10.0)))]}]
    shots = [_shot(108, 1, 700.0)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"][1] == 1000
    assert matched[0]["prior_frame"] is None


def test_prior_frame_is_none_when_there_is_no_release_frame_to_anchor_it_to():
    events = [{"moments": [_moment(1, 1000, 700.0, _positions((30.0, 10.0), (10.0, 10.0)))]}]
    shots = [_shot(109, 1, 700.0)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"] is None
    assert matched[0]["prior_frame"] is None
