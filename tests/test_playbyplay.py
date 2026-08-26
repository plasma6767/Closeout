from closeout.data.playbyplay import _is_assisted, parse_game_clock, parse_shot_events


def _row(
    action_number,
    period,
    clock,
    action_type,
    is_field_goal,
    shot_result=None,
    person_id=0,
    sub_type="Jump Shot",
    description="",
):
    return {
        "actionNumber": action_number,
        "period": period,
        "clock": clock,
        "actionType": action_type,
        "isFieldGoal": is_field_goal,
        "shotResult": shot_result,
        "personId": person_id,
        "subType": sub_type,
        "description": description,
    }


def test_parse_game_clock_converts_minutes_and_seconds():
    assert parse_game_clock("PT11M32.00S") == 692.0


def test_parse_game_clock_handles_under_a_minute():
    assert parse_game_clock("PT0M4.50S") == 4.5


def test_parse_game_clock_rejects_unrecognized_format():
    import pytest

    with pytest.raises(ValueError):
        parse_game_clock("11:32")


# Real description strings pulled from a live PlayByPlayV3 response
# (game 0021500001), used verbatim so the assist regex is checked against
# the actual format rather than an invented one.
_ASSISTED_MADE = "Towns 13' Jump Shot (2 PTS) (Wiggins 1 AST)"
_UNASSISTED_MADE = "Rubio 17' Pullup Jump Shot (2 PTS)"
_MISSED = "MISS Horford 20' Jump Shot"
_ASSISTED_DUNK = "Wiggins  Running Dunk (2 PTS) (Garnett 1 AST)"


def test_is_assisted_true_for_a_made_shot_with_trailing_ast():
    assert _is_assisted(_ASSISTED_MADE) is True


def test_is_assisted_true_regardless_of_shot_subtype():
    assert _is_assisted(_ASSISTED_DUNK) is True


def test_is_assisted_false_for_an_unassisted_made_shot():
    assert _is_assisted(_UNASSISTED_MADE) is False


def test_is_assisted_false_for_a_missed_shot():
    assert _is_assisted(_MISSED) is False


def test_parse_shot_events_extracts_only_field_goal_attempts():
    rows = [
        _row(1, 1, "PT11M32.00S", "2pt", True, "Made", person_id=201939, sub_type="Jump Shot", description=_ASSISTED_MADE),
        _row(2, 1, "PT11M20.00S", "foul", False),
        _row(
            3,
            1,
            "PT10M58.00S",
            "3pt",
            True,
            "Missed",
            person_id=201142,
            sub_type="Pullup Jump shot",
            description=_MISSED,
        ),
    ]

    shots = parse_shot_events(rows)

    assert len(shots) == 2
    assert shots[0] == {
        "event_id": 1,
        "quarter": 1,
        "game_clock": 692.0,
        "shooter_id": 201939,
        "made": True,
        "shot_type": "Jump Shot",
        "assisted": True,
    }
    assert shots[1] == {
        "event_id": 3,
        "quarter": 1,
        "game_clock": 658.0,
        "shooter_id": 201142,
        "made": False,
        "shot_type": "Pullup Jump shot",
        "assisted": False,
    }
