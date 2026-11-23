"""Tests for callout naming and lookup (synthetic callouts only)."""
from opscope import zones
from opscope.zones import MAX_CALLOUT_DIST_CM, callout_name, nearest_callout


def test_callout_name_formatting():
    assert callout_name("A", "Main") == "A Main"
    assert callout_name("Mid", "Courtyard") == "Mid Courtyard"
    assert callout_name("Attacker Side", "Spawn") == "Attacker Spawn"
    assert callout_name("Defender Side", "Link") == "Defender Link"


def test_nearest_callout_and_distance_cutoff(monkeypatch):
    fake = {"testmap": [{"name": "A Main", "x": 0, "y": 0}, {"name": "B Long", "x": 3000, "y": 0}]}
    monkeypatch.setattr(zones, "callouts", lambda: fake)
    monkeypatch.setattr(zones, "sites", lambda: {})
    got = nearest_callout("testmap", [100, 2900, 0], [0, 0, MAX_CALLOUT_DIST_CM + 1])
    assert list(got) == ["A Main", "B Long", None]   # too far from every callout: unnamed
    assert list(nearest_callout("testmap", 10, 10)) == ["A Main"]   # scalars work
    assert list(nearest_callout("nomap", [0], [0])) == [None]


def test_site_centres_override_a_closer_neighbouring_callout(monkeypatch):
    # The site's own callout point is 12 m away, a neighbouring callout only 9 m: the site still wins.
    monkeypatch.setattr(zones, "callouts", lambda: {"m": [{"name": "B Site", "x": 1200, "y": 0},
                                                          {"name": "B Boat House", "x": -900, "y": 0}]})
    monkeypatch.setattr(zones, "sites", lambda: {"m": [{"name": "B site", "x": 0, "y": 0}]})
    assert list(nearest_callout("m", [0, 500, -2000], [0, 0, 0])) == ["B Site", "B Site", "B Boat House"]


def test_shipped_sites_and_callouts_agree():
    """Two independent sources: the plant-derived site and the nearest callout share the same letter."""
    for map_name, entries in zones.sites().items():
        for s in entries:
            assert nearest_callout(map_name, s["x"], s["y"])[0] == s["name"].replace(" site", " Site")
            raw = min(zones.callouts()[map_name], key=lambda c: (c["x"] - s["x"]) ** 2 + (c["y"] - s["y"]) ** 2)
            assert raw["name"].split()[0] == s["name"].split()[0], (map_name, s["name"], raw["name"])
