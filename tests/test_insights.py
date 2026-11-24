"""Tests for insight ranking and bomb-site detection (synthetic numbers only)."""
import numpy as np

from opscope import zones
from opscope.analytics.insights import surprise
from opscope.analytics.stats import wilson
from opscope.zones import assign_site, kmeans


def test_surprise_is_zero_when_the_team_interval_overlaps_the_league():
    assert surprise(5, 20, 0.25) == 0          # 25% vs 25%: nothing to report
    assert surprise(3, 8, 0.20) == 0           # 38% on 8 rounds: interval too wide to call


def test_surprise_grows_with_gap_and_sample():
    small = surprise(12, 24, 0.20)             # 50% on 24 rounds vs 20%
    large = surprise(60, 120, 0.20)            # same 50% on 120 rounds
    assert 0 < small < large                   # more rounds, more confidence
    assert surprise(2, 134, 0.16) > 0          # "rarely" counts too (C9 Op on Lotus)


def test_wilson_is_exact_at_the_edges():
    for n in (1, 8, 31, 44, 47, 77, 94, 135):  # 44 and 135 used to give a lower bound of ~1e-18
        assert wilson(0, n)[0] == 0.0 and wilson(n, n)[1] == 1.0
        assert 0.0 < wilson(0, n)[1] < 1.0 and 0.0 < wilson(n, n)[0] < 1.0
    assert wilson(0, 0) == (0.0, 0.0)


def test_never_doing_what_the_typical_team_never_does_is_not_a_finding():
    for n in (44, 47, 94, 135):
        assert surprise(0, n, 0.0) == 0          # 0 of n vs a typical 0%: no gap
        assert surprise(n, n, 1.0) == 0          # always vs always: no gap
    assert surprise(0, 44, 0.20) > 0             # 0 of 44 vs a typical 20% is still "rarely"


def test_kmeans_finds_separated_sites_in_stable_order():
    rng = np.random.default_rng(0)
    a = rng.normal([-5000, 0], 300, size=(60, 2))
    b = rng.normal([5000, 0], 300, size=(40, 2))
    centres = kmeans(np.vstack([b, a]), 2)
    assert centres[0][0] < 0 < centres[1][0]   # sorted by x regardless of input order
    assert np.allclose(centres[0], [-5000, 0], atol=200)


def test_assign_site_uses_nearest_named_centre(monkeypatch):
    fake = {"testmap": [{"name": "A", "x": 0, "y": 0}, {"name": "B", "x": 1000, "y": 0}]}
    monkeypatch.setattr(zones, "sites", lambda: fake)
    assert list(assign_site("testmap", [100, 900], [0, 50])) == ["A", "B"]
    assert list(assign_site("unknown", [0], [0])) == [None]


def test_typical_rate_resists_one_extreme_team():
    from opscope.analytics.stats import typical_rate
    # five teams around 10%, one team at 90% with lots of rounds
    k = [2, 2, 2, 3, 2, 90]
    n = [20, 20, 20, 20, 20, 100]
    rate, method = typical_rate(k, n)
    pooled = sum(k) / sum(n)
    assert method == "typical team" and abs(rate - 0.10) < 0.01
    assert pooled > 0.4                                # pooling lets one team dominate


def test_typical_rate_falls_back_when_too_few_teams_qualify():
    from opscope.analytics.stats import typical_rate
    rate, method = typical_rate([5, 1, 1], [40, 10, 10])   # only one team has 16+ rounds
    assert method == "all rounds" and abs(rate - 7 / 60) < 1e-9
