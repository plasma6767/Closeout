from closeout.data.matching import match_shots_to_frames


def _moment(quarter, timestamp, game_clock):
    return [quarter, timestamp, game_clock, 24.0, None, []]


def _shot(event_id, quarter, game_clock, made=True):
    return {"event_id": event_id, "quarter": quarter, "game_clock": game_clock, "made": made}


def test_matches_shot_to_exact_frame():
    events = [
        {"moments": [_moment(1, 1000, 700.0), _moment(1, 1040, 699.0)]},
        {"moments": [_moment(1, 1040, 699.0), _moment(1, 1080, 698.0)]},
    ]
    shots = [_shot(101, 1, 699.0)]

    matched = match_shots_to_frames(events, shots)

    assert len(matched) == 1
    assert matched[0]["event_id"] == 101
    assert matched[0]["frame"][1] == 1040


def test_matches_shot_to_closest_available_frame():
    events = [{"moments": [_moment(1, 1000, 700.0), _moment(1, 1080, 698.0)]}]
    shots = [_shot(102, 1, 698.3)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"][1] == 1080


def test_returns_none_frame_when_tracking_coverage_is_late():
    events = [{"moments": [_moment(1, 1000, 680.93)]}]
    shots = [_shot(103, 1, 700.0)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"] is None
    assert matched[0]["event_id"] == 103


def test_returns_none_frame_for_quarter_with_no_tracking_at_all():
    events = [{"moments": [_moment(1, 1000, 700.0)]}]
    shots = [_shot(104, 2, 700.0)]

    matched = match_shots_to_frames(events, shots)

    assert matched[0]["frame"] is None


def test_preserves_shot_order_and_all_shot_fields():
    events = [{"moments": [_moment(1, 1000, 700.0)]}]
    shots = [_shot(105, 1, 700.0, made=False), _shot(106, 1, 700.0, made=True)]

    matched = match_shots_to_frames(events, shots)

    assert [shot["event_id"] for shot in matched] == [105, 106]
    assert matched[0]["made"] is False
    assert matched[1]["made"] is True
