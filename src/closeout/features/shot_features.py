"""Derive shot-quality features from matched shot rows.

Each row (see data/dataset.py) already has the shooter's identity, make/
miss, and the ball + all ten players' positions at the release frame and a
frame ~1 second earlier. This module turns those raw positions into actual
model inputs: shot distance/angle from the basket, closest and second-
closest defender distance/angle, shooter and closest-defender closing
speed, and a catch-and-shoot proxy from the play-by-play shot type.
"""

from __future__ import annotations

import math

# Standard NBA court dimensions in feet: 94 long x 50 wide, rim centers
# 5.25 ft from each baseline, at mid-width.
COURT_LENGTH_FT = 94.0
COURT_WIDTH_FT = 50.0
BASKET_X_NEAR = 5.25
BASKET_X_FAR = COURT_LENGTH_FT - BASKET_X_NEAR
BASKET_Y = COURT_WIDTH_FT / 2

# subType value (see data/playbyplay.py) stats.nba.com uses for a plain jump
# shot with no other qualifier (Pullup/Step Back/Turnaround/Driving/...).
# Combined with an assist, this is the closest proxy available for a
# catch-and-shoot jumper without real touch-time/dribble-count data.
CATCH_AND_SHOOT_SHOT_TYPE = "Jump Shot"


def _half_id(quarter: int) -> int:
    """Group quarters into the two directions teams shoot in during regulation.

    Teams switch baskets at halftime, not every quarter, so Q1+Q2 share a
    direction and Q3+Q4 share the other. Overtime periods are each kept in
    their own group rather than guessed at -- infer_basket_sides() works
    out the real direction per group from actual shot positions, so a
    smaller group just means fewer votes, not a wrong one.
    """
    if quarter <= 2:
        return 1
    if quarter <= 4:
        return 2
    return quarter


def infer_basket_sides(rows: list[dict]) -> dict[tuple[str, int], float]:
    """Work out which basket (x-coordinate) each team is attacking, per half.

    Picking the nearer basket to an individual shot's own release position
    is wrong for a full-court heave: the shooter is standing near their
    *own* basket when the ball leaves their hand, so "nearest basket to the
    ball" would score a 90-foot heave as a point-blank shot. Instead, this
    looks at every shot a team took in a half and votes on the basket
    nearest each one -- normal shots vastly outnumber heaves/outliers, so
    the majority reflects the team's real attacking direction, and outliers
    then inherit that direction rather than getting a vote of their own.

    Returns {(team, half_id): basket_x} for every (team, half) in `rows`.
    """
    votes: dict[tuple[str, int], dict[float, int]] = {}
    for row in rows:
        key = (row["team"], _half_id(row["quarter"]))
        near_dist = abs(row["ball_x"] - BASKET_X_NEAR)
        far_dist = abs(row["ball_x"] - BASKET_X_FAR)
        nearest_basket = BASKET_X_NEAR if near_dist <= far_dist else BASKET_X_FAR
        counts = votes.setdefault(key, {BASKET_X_NEAR: 0, BASKET_X_FAR: 0})
        counts[nearest_basket] += 1

    return {key: max(counts, key=counts.get) for key, counts in votes.items()}


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def _find_player(players: list[dict], player_id: int) -> dict | None:
    return next((p for p in players if p["player_id"] == player_id), None)


def _shooter_entry(row: dict) -> dict:
    """The shooter's own position entry from `row["players"]`.

    This must exist: find_release_frame() (tracking.py) only ever selects a
    frame where the shooter was found within 1.5 ft of the ball, so the
    shooter is guaranteed to be one of the tracked players at that frame.
    A missing entry here means that invariant broke upstream -- worth
    raising loudly, not papering over.
    """
    shooter = _find_player(row["players"], row["shooter_id"])
    if shooter is None:
        raise ValueError(f"shooter {row['shooter_id']} not found in players for event_id {row.get('event_id')}")
    return shooter


def _shot_distance_and_angle(ball_x: float, ball_y: float, basket_x: float) -> tuple[float, float]:
    """Distance in feet and angle in degrees from the basket the shot was attacking.

    Angle is measured from straight-on (0 deg, directly in front of the
    rim) to the baseline (90 deg, a corner shot) -- how far around the rim
    the shot came from, not a compass direction.
    """
    dx = abs(ball_x - basket_x)
    dy = abs(ball_y - BASKET_Y)
    return math.hypot(dx, dy), math.degrees(math.atan2(dy, dx))


def _defender_angle_deg(shooter_x, shooter_y, basket_x, defender_x, defender_y) -> float:
    """Angle (0-180 deg) between the shooter-to-basket line and the shooter-to-defender line.

    0 deg: the defender is standing directly on the line between the
    shooter and the rim -- the tightest possible contest geometry, even if
    their raw distance isn't the smallest. 180 deg: the defender is
    directly behind the shooter, not between them and the basket at all.
    """
    to_basket = (basket_x - shooter_x, BASKET_Y - shooter_y)
    to_defender = (defender_x - shooter_x, defender_y - shooter_y)
    basket_norm = math.hypot(*to_basket)
    defender_norm = math.hypot(*to_defender)
    if basket_norm == 0 or defender_norm == 0:
        # shooter standing exactly on the rim, or a defender exactly on top
        # of the shooter -- degenerate, not seen in real data
        return 0.0
    cos_angle = (to_basket[0] * to_defender[0] + to_basket[1] * to_defender[1]) / (basket_norm * defender_norm)
    cos_angle = max(-1.0, min(1.0, cos_angle))  # clamp float drift outside [-1, 1]
    return math.degrees(math.acos(cos_angle))


def _defenders_by_distance(row: dict, shooter: dict, basket_x: float) -> list[tuple[float, float, int]]:
    """(distance to the ball, angle off the shot line, player_id) for each defender, closest first."""
    ball_x, ball_y = row["ball_x"], row["ball_y"]
    defenders = [p for p in row["players"] if p["team_id"] != shooter["team_id"]]
    entries = [
        (
            _distance(ball_x, ball_y, d["x"], d["y"]),
            _defender_angle_deg(shooter["x"], shooter["y"], basket_x, d["x"], d["y"]),
            d["player_id"],
        )
        for d in defenders
    ]
    entries.sort(key=lambda entry: entry[0])
    return entries


def _prior_dt(row: dict) -> float | None:
    """Seconds between the prior frame and the release, or None if there's no usable prior frame.

    Game clock counts down, so the prior frame's clock should be larger
    than the release's. A non-positive gap means the "prior" frame isn't
    actually earlier (e.g. matching snapped to the release frame itself),
    which makes any velocity computed from it meaningless.
    """
    if "prior_game_clock" not in row:
        return None
    dt = row["prior_game_clock"] - row["game_clock"]
    return dt if dt > 0 else None


def _shooter_speed_ftps(row: dict, shooter: dict) -> float | None:
    """Feet/second the shooter moved between the prior frame and release."""
    dt = _prior_dt(row)
    if dt is None:
        return None
    prior_shooter = _find_player(row["prior_players"], row["shooter_id"])
    if prior_shooter is None:
        return None
    return _distance(shooter["x"], shooter["y"], prior_shooter["x"], prior_shooter["y"]) / dt


def _closest_defender_closing_speed_ftps(
    row: dict, closest_defender_id: int, closest_defender_dist_ft: float
) -> float | None:
    """Feet/second the closest-at-release defender closed the gap to the ball.

    Positive means the defender got tighter between the two frames;
    negative means they lost ground (beaten off the dribble, fell back on
    a switch, etc). Tracks the *same* player who ends up closest at
    release, not whoever was closest a second earlier.
    """
    dt = _prior_dt(row)
    if dt is None:
        return None
    prior_defender = _find_player(row["prior_players"], closest_defender_id)
    if prior_defender is None:
        return None
    prior_dist = _distance(row["prior_ball_x"], row["prior_ball_y"], prior_defender["x"], prior_defender["y"])
    return (prior_dist - closest_defender_dist_ft) / dt


def _catch_and_shoot(row: dict) -> bool | None:
    """Best-effort catch-and-shoot proxy: an assisted, unqualified jump shot.

    Not the NBA's own catch-and-shoot stat, which also requires <=1 dribble
    and <2s of touch time -- data this project doesn't have. Returns None
    if the row hasn't been backfilled with shot_type/assisted yet (see
    data/backfill.py).
    """
    if "shot_type" not in row or "assisted" not in row:
        return None
    return row["assisted"] and row["shot_type"] == CATCH_AND_SHOOT_SHOT_TYPE


def compute_shot_features(row: dict, basket_x: float) -> dict:
    """Compute every shot-quality feature for one matched shot row.

    `basket_x` is the basket this shot was actually attacking, from
    infer_basket_sides() -- never derive it from this single shot's own
    position (breaks on end-of-quarter heaves; see infer_basket_sides).
    """
    shooter = _shooter_entry(row)
    shot_distance_ft, shot_angle_deg = _shot_distance_and_angle(row["ball_x"], row["ball_y"], basket_x)

    defenders = _defenders_by_distance(row, shooter, basket_x)
    if defenders:
        closest_dist, closest_angle, closest_id = defenders[0]
        closing_speed = _closest_defender_closing_speed_ftps(row, closest_id, closest_dist)
    else:
        # a handful of real frames have fewer than 10 players tracked
        # (occlusion) -- treat as missing rather than failing the whole shot
        closest_dist = closest_angle = closing_speed = None
    second_dist, second_angle = (defenders[1][0], defenders[1][1]) if len(defenders) > 1 else (None, None)

    return {
        "shot_distance_ft": shot_distance_ft,
        "shot_angle_deg": shot_angle_deg,
        "closest_defender_dist_ft": closest_dist,
        "closest_defender_angle_deg": closest_angle,
        "second_defender_dist_ft": second_dist,
        "second_defender_angle_deg": second_angle,
        "shooter_speed_ftps": _shooter_speed_ftps(row, shooter),
        "closest_defender_closing_speed_ftps": closing_speed,
        "catch_and_shoot": _catch_and_shoot(row),
    }


def add_shot_features(rows: list[dict]) -> list[dict]:
    """Add shot-quality features to every shot row from one game.

    Must be called with all of one game's shots together, not a subset:
    infer_basket_sides() needs a team's full set of shots in a half to vote
    correctly. A small subset risks letting a handful of unusual shots (or
    even a single heave) dominate the vote for a team that took few shots
    in that slice.
    """
    basket_sides = infer_basket_sides(rows)
    return [
        {**row, **compute_shot_features(row, basket_sides[(row["team"], _half_id(row["quarter"]))])} for row in rows
    ]
