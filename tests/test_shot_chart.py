import pandas as pd
import pytest

from closeout.features.shot_features import BASKET_X_FAR, BASKET_X_NEAR, BASKET_Y
from closeout.viz.shot_chart import add_normalized_coords, draw_half_court, plot_shot_chart


def _shot(game_id, team, quarter, ball_x, ball_y, made=True, expected_fg_pct=0.5):
    return {
        "game_id": game_id,
        "team": team,
        "quarter": quarter,
        "ball_x": ball_x,
        "ball_y": ball_y,
        "made": made,
        "expected_fg_pct": expected_fg_pct,
    }


def test_add_normalized_coords_near_basket_shot():
    # 20 shots clustered near BASKET_X_NEAR so the team's Q1 vote is unambiguous
    rows = [_shot("g1", "ATL", 1, 6.0, BASKET_Y) for _ in range(19)]
    rows.append(_shot("g1", "ATL", 1, 20.0, BASKET_Y + 5.0))
    df = add_normalized_coords(pd.DataFrame(rows))

    target = df.iloc[-1]
    assert target["norm_x"] == pytest.approx(5.0)
    assert target["norm_y"] == pytest.approx(-(20.0 - BASKET_X_NEAR))


def test_add_normalized_coords_far_basket_shot_is_rotated_not_mirrored():
    # Mirror-image shot at the far basket: same distance from its own hoop
    # and same real-world sideline offset as the near-basket case above.
    rows = [_shot("g2", "MIA", 1, BASKET_X_FAR - 1.0, BASKET_Y) for _ in range(19)]
    far_ball_x = BASKET_X_FAR - (20.0 - BASKET_X_NEAR)
    rows.append(_shot("g2", "MIA", 1, far_ball_x, BASKET_Y + 5.0))
    df = add_normalized_coords(pd.DataFrame(rows))

    target = df.iloc[-1]
    # Same distance from the hoop as the near-basket case...
    assert target["norm_y"] == pytest.approx(-(20.0 - BASKET_X_NEAR))
    # ...but the sideline offset flips sign -- attacking the far basket is a
    # 180-degree turn from attacking the near one, so left/right flips too.
    assert target["norm_x"] == pytest.approx(-5.0)


def test_add_normalized_coords_keeps_games_independent():
    # Two games with opposite basket assignments for the same team/quarter
    # shouldn't bleed into each other's vote.
    rows = [_shot("g1", "ATL", 1, 6.0, BASKET_Y) for _ in range(5)]
    rows += [_shot("g2", "ATL", 1, BASKET_X_FAR - 1.0, BASKET_Y) for _ in range(5)]
    df = add_normalized_coords(pd.DataFrame(rows))

    assert (df[df["game_id"] == "g1"]["norm_y"] < 0).all()
    assert (df[df["game_id"] == "g2"]["norm_y"] < 0).all()
    # both groups are near their own hoop (small |norm_y|), not near the
    # court's other end
    assert df["norm_y"].abs().max() < 5.0


def test_draw_half_court_returns_axes_with_hoop_at_top():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    draw_half_court(ax)

    assert ax.get_ylim()[0] < 0  # court extends downward, away from the hoop
    xlim = ax.get_xlim()
    assert xlim[0] < 0 < xlim[1]  # centered left-right on the hoop
    plt.close(fig)


def test_plot_shot_chart_runs_on_a_normalized_frame():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [_shot("g1", "ATL", 1, 6.0, BASKET_Y, made=True)]
    rows.append(_shot("g1", "ATL", 1, 8.0, BASKET_Y + 2.0, made=False))
    df = add_normalized_coords(pd.DataFrame(rows))

    ax = plot_shot_chart(df, title="test")

    assert len(ax.collections) == 2  # one scatter call for makes, one for misses
    plt.close(ax.figure)
