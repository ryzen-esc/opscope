"""Tests for habit-spot clustering (synthetic positions only)."""
import pandas as pd

from opscope.analytics.utility import repeat_spots


def casts(points):
    """points: list of (game, round, x, y)."""
    return pd.DataFrame(points, columns=["game_id", "round_num", "x", "y"])


def test_finds_the_habitual_spot_and_counts_rounds_not_casts():
    pts = [("g", r, 1000 + r * 10, 2000) for r in range(1, 9)]   # 8 rounds within 1 m of each other
    pts += [("g", 1, 1005, 2005)]                                  # a second cast in round 1, same spot
    pts += [("g", 9, 8000, 8000)]                                  # one-off elsewhere
    spots = repeat_spots(casts(pts))
    assert len(spots) == 1                                         # the one-off is below min_rounds
    assert spots[0]["rounds"] == 8 and spots[0]["casts"] == 9
    assert abs(spots[0]["x"] - 1040) < 50 and abs(spots[0]["y"] - 2000) < 50


def test_separates_two_spots_and_orders_by_size():
    a = [("g", r, 0, 0) for r in range(1, 6)]                      # 5 rounds at A
    b = [("g", r, 5000, 0) for r in range(6, 9)]                   # 3 rounds at B, 50 m away
    spots = repeat_spots(casts(a + b))
    assert [s["rounds"] for s in spots] == [5, 3]


def test_points_just_outside_the_radius_are_not_merged():
    pts = [("g", 1, 0, 0), ("g", 2, 0, 0), ("g", 3, 450, 0), ("g", 4, 450, 0)]
    spots = repeat_spots(casts(pts), radius=400)
    assert sorted(s["rounds"] for s in spots) == [2, 2]


def test_empty_input():
    assert repeat_spots(casts([])) == []
