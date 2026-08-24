import json

from closeout.data.dataset import build_shot_dataset, write_shot_dataset


def _moment(quarter, timestamp, game_clock, positions):
    return [quarter, timestamp, game_clock, 24.0, None, positions]


def _pbp_row(action_number, period, clock, is_field_goal, shot_result=None, person_id=0, player_name="", team=""):
    return {
        "actionNumber": action_number,
        "period": period,
        "clock": clock,
        "isFieldGoal": is_field_goal,
        "shotResult": shot_result,
        "personId": person_id,
        "playerName": player_name,
        "teamTricode": team,
    }


def _positions(ball_xyz, players):
    return [[-1, -1, *ball_xyz]] + [[team_id, player_id, x, y] for team_id, player_id, x, y in players]


def test_builds_one_row_per_matched_shot_with_shooter_and_frame_info():
    events = [
        {
            "moments": [
                _moment(
                    1,
                    1000,
                    690.0,
                    _positions((5.5, 25.0, 9.5), [(1610612744, 201939, 5.0, 24.0)]),
                )
            ]
        }
    ]
    pbp_rows = [
        _pbp_row(
            10,
            1,
            "PT11M30.00S",
            True,
            shot_result="Made",
            person_id=201939,
            player_name="Curry",
            team="GSW",
        )
    ]

    rows = build_shot_dataset("0021500480", pbp_rows, events)

    assert len(rows) == 1
    row = rows[0]
    assert row["game_id"] == "0021500480"
    assert row["event_id"] == 10
    assert row["shooter_id"] == 201939
    assert row["shooter_name"] == "Curry"
    assert row["team"] == "GSW"
    assert row["made"] is True
    assert row["ball_x"] == 5.5
    assert row["ball_y"] == 25.0
    assert row["ball_z"] == 9.5
    assert row["players"] == [{"team_id": 1610612744, "player_id": 201939, "x": 5.0, "y": 24.0}]


def test_includes_prior_frame_positions_when_available():
    events = [
        {
            "moments": [
                _moment(1, 1000, 691.0, _positions((3.0, 20.0, 1.0), [(1610612744, 201939, 4.0, 19.0)])),
                _moment(1, 1040, 690.0, _positions((5.5, 25.0, 9.5), [(1610612744, 201939, 5.0, 24.0)])),
            ]
        }
    ]
    pbp_rows = [_pbp_row(10, 1, "PT11M30.00S", True, shot_result="Made", person_id=201939)]

    rows = build_shot_dataset("0021500480", pbp_rows, events)

    row = rows[0]
    assert row["prior_game_clock"] == 691.0
    assert row["prior_ball_x"] == 3.0
    assert row["prior_ball_y"] == 20.0
    assert row["prior_ball_z"] == 1.0
    assert row["prior_players"] == [{"team_id": 1610612744, "player_id": 201939, "x": 4.0, "y": 19.0}]


def test_omits_prior_frame_fields_when_no_prior_frame_is_available():
    events = [
        {
            "moments": [
                _moment(1, 1000, 690.0, _positions((5.5, 25.0, 9.5), [(1610612744, 201939, 5.0, 24.0)])),
            ]
        }
    ]
    pbp_rows = [_pbp_row(10, 1, "PT11M30.00S", True, shot_result="Made", person_id=201939)]

    rows = build_shot_dataset("0021500480", pbp_rows, events)

    row = rows[0]
    assert "prior_game_clock" not in row
    assert "prior_ball_x" not in row
    assert "prior_players" not in row


def test_drops_shots_with_no_matched_frame():
    # tracking coverage starts at 680s, but this shot happened at 700s
    events = [{"moments": [_moment(1, 1000, 680.0, _positions((0, 0, 0), []))]}]
    pbp_rows = [_pbp_row(10, 1, "PT11M40.00S", True, shot_result="Made")]

    rows = build_shot_dataset("0021500480", pbp_rows, events)

    assert rows == []


def test_drops_shots_whose_frame_has_no_ball_entry():
    # ball is occasionally untracked/occluded for a given frame -- no [-1, -1, ...] entry
    events = [
        {
            "moments": [
                _moment(1, 1000, 690.0, [[1610612744, 201939, 5.0, 24.0]]),
            ]
        }
    ]
    pbp_rows = [_pbp_row(10, 1, "PT11M30.00S", True, shot_result="Made")]

    rows = build_shot_dataset("0021500480", pbp_rows, events)

    assert rows == []


def test_write_shot_dataset_writes_one_json_object_per_line(tmp_path):
    rows = [
        {"event_id": 1, "made": True},
        {"event_id": 2, "made": False},
    ]
    out_path = tmp_path / "shots.jsonl"

    write_shot_dataset(rows, str(out_path))

    lines = out_path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"event_id": 1, "made": True}
    assert json.loads(lines[1]) == {"event_id": 2, "made": False}
