"""Draw a shot chart: a half-court diagram with shots plotted on it, colored
by the model's expected FG% for each shot.

Every shot's raw position (`ball_x`, `ball_y`) is a point on the full 94x50 ft
court, but the two baskets sit at opposite ends -- a shot chart needs every
shot projected onto one common half-court, the way real shot charts do.
`add_normalized_coords()` handles that; `draw_half_court()` and
`plot_shot_chart()` handle the drawing.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Arc, Circle, Rectangle

from closeout.features.shot_features import BASKET_X_NEAR, BASKET_Y, _half_id, infer_basket_sides

# Dark chart surface + a single accent hue for the court chrome. Shots use a
# *different* hue (below) so color keeps doing one job at a time: blue always
# means "court," orange always means "expected FG%" -- mixing the two into
# one hue would make shots hard to pick out against the court lines.
SURFACE_COLOR = "#1a1a19"
COURT_LINE_COLOR = "#3987e5"
TEXT_COLOR = "#ffffff"

# Low = dim/near-surface (low expected FG%), high = bright (high expected
# FG%) -- monotonic in lightness so "more filled in" always reads as "more
# likely to go in," regardless of which end of the scale you're looking at.
EXPECTED_FG_CMAP = LinearSegmentedColormap.from_list("expected_fg_pct", ["#7a4a1e", "#ffb347"])


def add_normalized_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Project every shot onto one canonical half-court: hoop at the top.

    Must be called on the *whole* predictions table, one game at a time
    internally -- infer_basket_sides() needs a team's full set of shots in a
    half to vote on which basket they were attacking (see
    features/shot_features.py). Calling this on a single player's shots
    would re-run that vote on too few shots per half, risking exactly the
    kind of flip infer_basket_sides is designed to resist for a whole team.

    Adds `norm_x` (left-right offset from the hoop's centerline, positive
    and negative both meaningful) and `norm_y` (distance from the hoop,
    always <= 0, more negative = further from the basket).

    The two baskets sit at opposite ends of the court, so "attacking the far
    basket" is a 180-degree turn from "attacking the near basket" -- both
    offsets flip sign together for far-basket shots, a rotation (not a
    mirror), so a shot's real left/right relative to its own basket is
    preserved rather than reflected.
    """
    norm_x = []
    norm_y = []
    for _, game_df in df.groupby("game_id"):
        basket_sides = infer_basket_sides(game_df[["team", "quarter", "ball_x"]].to_dict("records"))
        for row in game_df.itertuples():
            basket_x = basket_sides[(row.team, _half_id(row.quarter))]
            direction = 1 if basket_x == BASKET_X_NEAR else -1
            norm_x.append(direction * (row.ball_y - BASKET_Y))
            norm_y.append(-abs(row.ball_x - basket_x))

    result = df.copy()
    result["norm_x"] = norm_x
    result["norm_y"] = norm_y
    return result


def draw_half_court(ax: Axes) -> Axes:
    """Draw a half-court diagram, hoop at the top, matching add_normalized_coords()'s frame."""
    ax.set_facecolor(SURFACE_COLOR)
    c = COURT_LINE_COLOR

    ax.plot([-25, 25], [0, 0], color=c, linewidth=2)  # baseline
    ax.plot([-25, -25], [0, -47], color=c, linewidth=2)  # left sideline
    ax.plot([25, 25], [0, -47], color=c, linewidth=2)  # right sideline
    ax.plot([-25, 25], [-47, -47], color=c, linewidth=2)  # half-court line
    ax.add_patch(Arc((0, -47), 12, 12, theta1=0, theta2=180, color=c))  # center circle

    ax.plot([-3, 3], [-4, -4], color=c, linewidth=2)  # backboard
    ax.add_patch(Circle((0, -5.25), 0.75, fill=False, color=c))  # rim
    # restricted area: closed/curved side faces away from the baseline
    # (toward the 3pt line), so it bulges downward in this hoop-at-top frame.
    ax.add_patch(Arc((0, -5.25), 8, 8, theta1=-180, theta2=0, color=c))

    ax.add_patch(Rectangle((-8, -19), 16, 19, fill=False, color=c))  # paint / key
    ax.add_patch(Arc((0, -19), 12, 12, theta1=-180, theta2=0, color=c))  # ft circle, outside the key
    ax.add_patch(Arc((0, -19), 12, 12, theta1=0, theta2=180, color=c, linestyle="dashed"))  # inside the key

    corner_x = 22
    ax.plot([corner_x, corner_x], [0, -14], color=c, linewidth=1.5)
    ax.plot([-corner_x, -corner_x], [0, -14], color=c, linewidth=1.5)
    ax.add_patch(Arc((0, -5.25), 2 * 23.75, 2 * 23.75, theta1=-158, theta2=-22, color=c, linewidth=1.5))

    ax.set_xlim(-26, 26)
    ax.set_ylim(-49, 2)
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


def plot_shot_chart(df: pd.DataFrame, ax: Axes | None = None, title: str | None = None) -> Axes:
    """Plot shots on a half-court, colored by expected_fg_pct, makes vs. misses as different markers.

    `df` must already have `norm_x`/`norm_y` (see add_normalized_coords) --
    plotting is per-player, but normalizing needs the whole dataset, so the
    two steps are deliberately kept separate rather than folded together
    here.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(6.4, 6.8))
        ax.figure.patch.set_facecolor(SURFACE_COLOR)

    draw_half_court(ax)

    makes = df[df["made"]]
    misses = df[~df["made"]]
    if len(makes):
        ax.scatter(
            makes["norm_x"], makes["norm_y"], c=makes["expected_fg_pct"], cmap=EXPECTED_FG_CMAP,
            vmin=0, vmax=1, s=45, marker="o", edgecolors=COURT_LINE_COLOR, linewidths=0.5,
        )
    if len(misses):
        ax.scatter(
            misses["norm_x"], misses["norm_y"], c=misses["expected_fg_pct"], cmap=EXPECTED_FG_CMAP,
            vmin=0, vmax=1, s=45, marker="x",
        )

    if title:
        ax.set_title(title, color=TEXT_COLOR)
    return ax
