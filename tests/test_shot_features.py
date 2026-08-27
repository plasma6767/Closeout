import json
from pathlib import Path

import pytest

from closeout.features.shot_features import (
    BASKET_X_FAR,
    BASKET_X_NEAR,
    _catch_and_shoot,
    _closest_defender_closing_speed_ftps,
    _defender_angle_deg,
    _defenders_by_distance,
    _half_id,
    _prior_dt,
    _shooter_speed_ftps,
    _shot_distance_and_angle,
    add_shot_features,
    compute_shot_features,
    infer_basket_sides,
)

REAL_SAMPLE_ROW = json.loads(
    Path(__file__).parent.parent.joinpath("data/processed/0021500001.jsonl").read_text().splitlines()[0]
)


# -- _half_id -----------------------------------------------------------


@pytest.mark.parametrize("quarter,expected", [(1, 1), (2, 1), (3, 2), (4, 2), (5, 5), (6, 6)])
def test_half_id_groups_regulation_quarters_by_half_and_ot_periods_alone(quarter, expected):
    assert _half_id(quarter) == expected


# -- infer_basket_sides ---------------------------------------------------


def _shot_row(team, quarter, ball_x, ball_y=25.0):
    return {"team": team, "quarter": quarter, "ball_x": ball_x, "ball_y": ball_y}


def test_infer_basket_sides_picks_the_basket_most_shots_cluster_near():
    rows = [_shot_row("ATL", 1, 6.0) for _ in range(20)] + [_shot_row("ATL", 1, 89.0)]

    sides = infer_basket_sides(rows)

    assert sides[("ATL", 1)] == BASKET_X_NEAR


def test_infer_basket_sides_does_not_let_a_heave_flip_the_team_half_vote():
    # 19 normal shots near the near basket, one full-court heave released
    # right next to the *far* basket (i.e. release point near their own
    # hoop before a 90-foot heave at the other one) -- the heave must not
    # flip the team's inferred direction for the half.
    rows = [_shot_row("ATL", 1, 6.0) for _ in range(19)] + [_shot_row("ATL", 1, BASKET_X_FAR - 1.0)]

    sides = infer_basket_sides(rows)

    assert sides[("ATL", 1)] == BASKET_X_NEAR


def test_infer_basket_sides_switches_direction_between_halves():
    rows = [_shot_row("ATL", 1, 6.0)] * 5 + [_shot_row("ATL", 3, 89.0)] * 5

    sides = infer_basket_sides(rows)

    assert sides[("ATL", 1)] == BASKET_X_NEAR
    assert sides[("ATL", 2)] == BASKET_X_FAR


def test_infer_basket_sides_tracks_teams_independently():
    rows = [_shot_row("ATL", 1, 6.0)] * 5 + [_shot_row("DET", 1, 89.0)] * 5

    sides = infer_basket_sides(rows)

    assert sides[("ATL", 1)] == BASKET_X_NEAR
    assert sides[("DET", 1)] == BASKET_X_FAR


# -- _shot_distance_and_angle -----------------------------------------------


def test_shot_distance_and_angle_uses_a_3_4_5_triangle():
    # basket at (5.25, 25); ball 3 ft further out and 4 ft off-center -> a
    # clean 3-4-5 right triangle, distance 5, angle atan2(4, 3)
    distance, angle = _shot_distance_and_angle(ball_x=8.25, ball_y=29.0, basket_x=5.25)

    assert distance == pytest.approx(5.0)
    assert angle == pytest.approx(53.130102, abs=1e-4)


def test_shot_distance_and_angle_is_zero_angle_for_a_straight_on_shot():
    distance, angle = _shot_distance_and_angle(ball_x=15.25, ball_y=25.0, basket_x=5.25)

    assert distance == pytest.approx(10.0)
    assert angle == pytest.approx(0.0)


def test_shot_distance_and_angle_is_ninety_for_a_shot_on_the_baseline():
    distance, angle = _shot_distance_and_angle(ball_x=5.25, ball_y=45.0, basket_x=5.25)

    assert distance == pytest.approx(20.0)
    assert angle == pytest.approx(90.0)


# -- _defender_angle_deg -----------------------------------------------


def test_defender_angle_is_zero_when_defender_is_directly_between_shooter_and_basket():
    # shooter at (10, 25), basket at (5.25, 25), defender at (7, 25) -- on the line
    angle = _defender_angle_deg(10.0, 25.0, 5.25, 7.0, 25.0)
    assert angle == pytest.approx(0.0, abs=1e-6)


def test_defender_angle_is_180_when_defender_is_directly_behind_the_shooter():
    angle = _defender_angle_deg(10.0, 25.0, 5.25, 13.0, 25.0)
    assert angle == pytest.approx(180.0, abs=1e-6)


def test_defender_angle_is_90_when_defender_is_perpendicular_to_the_shot_line():
    angle = _defender_angle_deg(10.0, 25.0, 5.25, 10.0, 29.0)
    assert angle == pytest.approx(90.0, abs=1e-6)


# -- _defenders_by_distance -----------------------------------------------


def test_defenders_by_distance_excludes_teammates_and_sorts_closest_first():
    row = {
        "ball_x": 0.0,
        "ball_y": 0.0,
        "players": [
            {"team_id": 1, "player_id": 900, "x": 0.0, "y": 0.0},  # shooter, team 1
            {"team_id": 1, "player_id": 901, "x": 1.0, "y": 0.0},  # teammate, must be excluded
            {"team_id": 2, "player_id": 902, "x": 10.0, "y": 0.0},  # far defender
            {"team_id": 2, "player_id": 903, "x": 3.0, "y": 0.0},  # closest defender
        ],
    }
    shooter = row["players"][0]

    entries = _defenders_by_distance(row, shooter, basket_x=5.25)

    assert [player_id for _, _, player_id in entries] == [903, 902]
    assert entries[0][0] == pytest.approx(3.0)
    assert entries[1][0] == pytest.approx(10.0)


def test_defenders_by_distance_is_empty_when_no_opposing_players_are_tracked():
    row = {"ball_x": 0.0, "ball_y": 0.0, "players": [{"team_id": 1, "player_id": 900, "x": 0.0, "y": 0.0}]}
    shooter = row["players"][0]

    assert _defenders_by_distance(row, shooter, basket_x=5.25) == []


# -- _prior_dt / speed helpers -----------------------------------------------


def test_prior_dt_is_none_without_a_prior_frame():
    assert _prior_dt({"game_clock": 700.0}) is None


def test_prior_dt_is_none_when_the_gap_is_not_positive():
    # game clock counts down, so a "prior" clock <= the release clock is bogus
    assert _prior_dt({"game_clock": 700.0, "prior_game_clock": 700.0}) is None
    assert _prior_dt({"game_clock": 700.0, "prior_game_clock": 699.0}) is None


def test_prior_dt_computes_the_positive_gap():
    assert _prior_dt({"game_clock": 700.0, "prior_game_clock": 701.5}) == pytest.approx(1.5)


def test_shooter_speed_ftps_divides_distance_moved_by_dt():
    row = {
        "game_clock": 700.0,
        "prior_game_clock": 701.5,
        "shooter_id": 900,
        "prior_players": [{"player_id": 900, "x": 3.0, "y": 4.0}],
    }
    shooter = {"player_id": 900, "x": 0.0, "y": 0.0}  # moved 5 ft (3-4-5) over 1.5s

    assert _shooter_speed_ftps(row, shooter) == pytest.approx(5.0 / 1.5)


def test_shooter_speed_ftps_is_none_when_shooter_missing_from_prior_frame():
    row = {
        "game_clock": 700.0,
        "prior_game_clock": 701.0,
        "shooter_id": 900,
        "prior_players": [{"player_id": 999, "x": 0.0, "y": 0.0}],
    }
    shooter = {"player_id": 900, "x": 0.0, "y": 0.0}

    assert _shooter_speed_ftps(row, shooter) is None


def test_closest_defender_closing_speed_is_positive_when_the_gap_shrinks():
    row = {
        "game_clock": 700.0,
        "prior_game_clock": 702.0,
        "prior_ball_x": 0.0,
        "prior_ball_y": 0.0,
        "prior_players": [{"player_id": 500, "x": 10.0, "y": 0.0}],  # 10 ft away a prior
    }
    # closest_defender_dist_ft = 4.0 now, was 10.0 -> closed 6 ft over 2s
    assert _closest_defender_closing_speed_ftps(row, 500, 4.0) == pytest.approx(3.0)


def test_closest_defender_closing_speed_is_negative_when_the_gap_widens():
    row = {
        "game_clock": 700.0,
        "prior_game_clock": 702.0,
        "prior_ball_x": 0.0,
        "prior_ball_y": 0.0,
        "prior_players": [{"player_id": 500, "x": 4.0, "y": 0.0}],  # 4 ft away a prior
    }
    # closest_defender_dist_ft = 10.0 now, was 4.0 -> lost 6 ft over 2s
    assert _closest_defender_closing_speed_ftps(row, 500, 10.0) == pytest.approx(-3.0)


def test_closest_defender_closing_speed_is_none_without_a_prior_frame():
    assert _closest_defender_closing_speed_ftps({"game_clock": 700.0}, 500, 4.0) is None


# -- _catch_and_shoot -----------------------------------------------


def test_catch_and_shoot_is_none_when_not_backfilled():
    assert _catch_and_shoot({"made": True}) is None


def test_catch_and_shoot_is_true_for_an_assisted_plain_jump_shot():
    assert _catch_and_shoot({"shot_type": "Jump Shot", "assisted": True}) is True


def test_catch_and_shoot_is_false_for_an_unassisted_jump_shot():
    assert _catch_and_shoot({"shot_type": "Jump Shot", "assisted": False}) is False


def test_catch_and_shoot_is_false_for_an_assisted_pullup():
    # assisted, but the shooter created it off the dribble, not a clean catch
    assert _catch_and_shoot({"shot_type": "Pullup Jump shot", "assisted": True}) is False


# -- compute_shot_features: real production data -----------------------------------------------


def test_compute_shot_features_matches_hand_verified_values_on_a_real_shot():
    # game 0021500001, event 2 -- Horford at the rim, a real shot from the
    # actual processed dataset, not a synthetic fixture. Expected numbers
    # cross-checked independently before being hardcoded here.
    features = compute_shot_features(REAL_SAMPLE_ROW, basket_x=BASKET_X_NEAR)

    assert features["shot_distance_ft"] == pytest.approx(1.214006, abs=1e-5)
    assert features["shot_angle_deg"] == pytest.approx(30.186387, abs=1e-5)
    assert features["closest_defender_dist_ft"] == pytest.approx(1.400335, abs=1e-5)
    assert features["closest_defender_angle_deg"] == pytest.approx(161.62166, abs=1e-4)
    assert features["second_defender_dist_ft"] == pytest.approx(5.945674, abs=1e-5)
    assert features["second_defender_angle_deg"] == pytest.approx(26.578773, abs=1e-4)
    assert features["shooter_speed_ftps"] == pytest.approx(1.414079, abs=1e-5)
    assert features["closest_defender_closing_speed_ftps"] == pytest.approx(-0.299930, abs=1e-5)
    # this row predates the shot_type/assisted backfill
    assert features["catch_and_shoot"] is None


def test_compute_shot_features_leaves_second_defender_none_with_only_one_defender():
    row = {
        "ball_x": 0.0,
        "ball_y": 0.0,
        "shooter_id": 1,
        "players": [
            {"team_id": 1, "player_id": 1, "x": 0.0, "y": 0.0},
            {"team_id": 2, "player_id": 2, "x": 3.0, "y": 0.0},
        ],
    }

    features = compute_shot_features(row, basket_x=BASKET_X_NEAR)

    assert features["closest_defender_dist_ft"] == pytest.approx(3.0)
    assert features["second_defender_dist_ft"] is None
    assert features["second_defender_angle_deg"] is None


def test_compute_shot_features_handles_no_tracked_defenders_without_raising():
    row = {
        "ball_x": 0.0,
        "ball_y": 0.0,
        "shooter_id": 1,
        "players": [{"team_id": 1, "player_id": 1, "x": 0.0, "y": 0.0}],
    }

    features = compute_shot_features(row, basket_x=BASKET_X_NEAR)

    assert features["closest_defender_dist_ft"] is None
    assert features["closest_defender_angle_deg"] is None
    assert features["closest_defender_closing_speed_ftps"] is None


def test_compute_shot_features_raises_if_the_shooter_is_not_among_the_tracked_players():
    row = {"event_id": 42, "ball_x": 0.0, "ball_y": 0.0, "shooter_id": 999, "players": []}

    with pytest.raises(ValueError, match="shooter 999"):
        compute_shot_features(row, basket_x=BASKET_X_NEAR)


# -- add_shot_features -----------------------------------------------


def test_add_shot_features_applies_the_per_team_half_basket_to_every_shot():
    rows = [
        {
            "event_id": 1,
            "team": "ATL",
            "quarter": 1,
            "ball_x": 6.0,
            "ball_y": 25.0,
            "shooter_id": 1,
            "players": [{"team_id": 1, "player_id": 1, "x": 6.0, "y": 25.0}],
        }
    ] * 19 + [
        {
            # a heave released near the far basket, still attacking the near one
            "event_id": 2,
            "team": "ATL",
            "quarter": 1,
            "ball_x": BASKET_X_FAR - 1.0,
            "ball_y": 25.0,
            "shooter_id": 1,
            "players": [{"team_id": 1, "player_id": 1, "x": BASKET_X_FAR - 1.0, "y": 25.0}],
        }
    ]

    featured = add_shot_features(rows)

    heave = next(r for r in featured if r["event_id"] == 2)
    # attacking the near basket despite being released next to the far one
    # -> a long shot, not the point-blank distance a per-shot heuristic
    # would wrongly compute
    assert heave["shot_distance_ft"] == pytest.approx(BASKET_X_FAR - 1.0 - BASKET_X_NEAR)


def test_add_shot_features_preserves_original_row_fields():
    rows = [
        {
            "event_id": 1,
            "team": "ATL",
            "quarter": 1,
            "made": True,
            "ball_x": 6.0,
            "ball_y": 25.0,
            "shooter_id": 1,
            "players": [{"team_id": 1, "player_id": 1, "x": 6.0, "y": 25.0}],
        }
    ]

    featured = add_shot_features(rows)

    assert featured[0]["event_id"] == 1
    assert featured[0]["made"] is True
    assert "shot_distance_ft" in featured[0]
