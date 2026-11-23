"""Tests for insight ranking and bomb-site detection (synthetic numbers only)."""
import numpy as np

from opscope import zones
from opscope.analytics.insights import surprise
from opscope.zones import assign_site, kmeans


def test_surprise_is_zero_when_the_team_interval_overlaps_the_league():
    assert surprise(5, 20, 0.25) == 0          # 25% vs 25%: nothing to report
    assert surprise(3, 8, 0.20) == 0           # 38% on 8 rounds: interval too wide to call


def test_surprise_grows_with_gap_and_sample():
    small = surprise(12, 24, 0.20)             # 50% on 24 rounds vs 20%
    large = surprise(60, 120, 0.20)            # same 50% on 120 rounds
    assert 0 < small < large                   # more rounds, more confidence
    assert surprise(2, 134, 0.16) > 0          # "rarely" counts too (C9 Op on Lotus)


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
