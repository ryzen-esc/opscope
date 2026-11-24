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


def test_habit_ring_holds_every_cast_counted_in_the_spot(monkeypatch):
    """Members are within 4 m of one cast (the densest), so some sit over 4 m from the spot's mean: the ring the
    Utility page draws (r_m) must reach them, without changing k, n or the centre."""
    import numpy as np

    import opscope.analytics.utility as U
    from opscope import present
    # one wide spot: the densest cast at 0, three at +3.5 m, one at -3.8 m (all within 4 m of the first cast);
    # and one tight spot 50 m away
    wide = [(0, 0), (350, 0), (350, 10), (350, -10), (-380, 0)]
    tight = [(5000, 0), (5010, 0), (5000, 10)]
    rows = [{"game_id": "g", "round_num": r, "round_key": f"g-{r}", "map": "testmap", "player_id": "p1",
             "player_name": "P1", "agent": "cypher", "ability": "trapwire", "util_class": "trap", "x": x, "y": y}
            for r, (x, y) in enumerate(wide + tight, 1)]
    rep = U.UtilityReport(scope=U.UtilityScope(team_id="t"), rounds=pd.DataFrame(), casts=pd.DataFrame(rows),
                          agent_rounds=pd.DataFrame())
    monkeypatch.setattr(U.UtilityReport, "agent_rounds_by_map", lambda self, m: {("p1", "cypher"): 10})
    monkeypatch.setattr(U, "nearest_callout", lambda m, x, y: ["Somewhere"] * len(x))
    monkeypatch.setattr(present, "_view", lambda m, x, y: (np.asarray(x, float), np.asarray(y, float)))
    spots = sorted(present._habits(rep, "testmap"), key=lambda h: -h["k"])
    assert [(h["k"], h["n"]) for h in spots] == [(5, 10), (3, 10)]
    mean_x = sum(x for x, _ in wide) / len(wide)
    assert spots[0]["at"] == [mean_x, 0.0]                      # centre unchanged: the members' mean
    reach_m = max(np.hypot(x - mean_x, y) for x, y in wide) / 100
    assert reach_m > 4                                          # the case the fixed 4 m ring missed
    assert spots[0]["r_m"] >= reach_m and spots[0]["r_m"] - reach_m < 0.1
    assert spots[1]["r_m"] == 4.0                               # a tight spot keeps the 4 m ring
