from closeout.data.playbyplay import parse_game_clock, parse_shot_events


def _row(action_number, period, clock, action_type, is_field_goal, shot_result=None, person_id=0):
    return {
        "actionNumber": action_number,
        "period": period,
        "clock": clock,
        "actionType": action_type,
        "isFieldGoal": is_field_goal,
        "shotResult": shot_result,
        "personId": person_id,
    }


def test_parse_game_clock_converts_minutes_and_seconds():
    assert parse_game_clock("PT11M32.00S") == 692.0


def test_parse_game_clock_handles_under_a_minute():
    assert parse_game_clock("PT0M4.50S") == 4.5


def test_parse_game_clock_rejects_unrecognized_format():
    import pytest

    with pytest.raises(ValueError):
        parse_game_clock("11:32")


def test_parse_shot_events_extracts_only_field_goal_attempts():
    rows = [
        _row(1, 1, "PT11M32.00S", "2pt", True, "Made", person_id=201939),
        _row(2, 1, "PT11M20.00S", "foul", False),
        _row(3, 1, "PT10M58.00S", "3pt", True, "Missed", person_id=201142),
    ]

    shots = parse_shot_events(rows)

    assert len(shots) == 2
    assert shots[0] == {"event_id": 1, "quarter": 1, "game_clock": 692.0, "shooter_id": 201939, "made": True}
    assert shots[1] == {"event_id": 3, "quarter": 1, "game_clock": 658.0, "shooter_id": 201142, "made": False}
