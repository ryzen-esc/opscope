"""Tests for same-tier/season comparisons and roster detection (synthetic tables only)."""
import pandas as pd

from opscope.analytics import roster
from opscope.analytics.operator import Scope, _filter_rounds, league_scope
from opscope.load import cohort_label


def test_cohort_labels():
    assert cohort_label(["vct-2025"]) == "VCT 2025"
    assert cohort_label(["gc-2026", "gc-2025"]) == "Game Changers 2025–2026"
    assert cohort_label([]) == "league"


def test_league_is_other_teams_in_the_same_tier_and_season():
    tr = pd.DataFrame({
        "team_id": ["A", "B", "C", "D"], "side": "defender", "map": "lotus", "opp_id": "x",
        "patch": "10.0", "event": "e", "cohort": ["vct-2025", "vct-2025", "gc-2026", "gc-2025"]})
    team = _filter_rounds(tr, Scope(team_id="A"))
    lg = league_scope(Scope(team_id="A"), team)
    assert lg.cohorts == ("vct-2025",) and lg.team_id == ""
    assert sorted(_filter_rounds(tr, lg)["team_id"]) == ["A", "B"]   # callers then drop the team itself


def fake_loadouts():
    rows = []
    def event(name, date, players, rounds=10):
        for r in range(rounds):
            for p in players:
                rows.append({"team_id": "T", "event": name, "started_at": date, "game_id": f"{name}-g",
                             "round_num": r, "player_id": p, "player_name": p.upper()})
    event("Kickoff", "2025-02-01", ["a", "b", "c", "d", "e"])
    event("Stage 1", "2025-04-01", ["a", "b", "c", "d", "f"])
    event("Stage 2", "2025-08-01", ["a", "b", "c", "g", "f"])
    rows.append({"team_id": "T", "event": "Stage 2", "started_at": "2025-08-01", "game_id": "Stage 2-g",
                 "round_num": 0, "player_id": "sub", "player_name": "SUB"})   # one-round substitute
    return pd.DataFrame(rows)


def test_rosters_by_event_latest_roster_and_departures(monkeypatch):
    class D:
        loadouts = fake_loadouts()
    monkeypatch.setattr(roster, "load", lambda: D)
    roster.team_rosters.cache_clear()
    latest = roster.latest_roster("T")
    assert latest.event == "Stage 2" and latest.player_ids == frozenset("abcgf")   # the sub isn't a regular
    assert roster.last_event_with("T", "d") == "Stage 1"
    assert roster.last_event_with("T", "e") == "Kickoff"
    assert roster.lineups_in("T", ["Kickoff", "Stage 1", "Stage 2"]) == 3
    assert roster.lineups_in("T", ["Stage 2"]) == 1
    roster.team_rosters.cache_clear()


def test_build_report_merges_runs_instead_of_overwriting():
    from opscope.ingest.build import merge_report
    first = merge_report({}, [{"series_id": "a", "events": 10, "rollback_applied": 2},
                              {"series_id": "b", "events": 5}], [], {"rounds": 3}, 1.0)
    again = merge_report(first, [{"series_id": "b", "events": 6}], [], {"rounds": 3}, 0.5)   # rebuild one series
    assert again["built_series"] == 2
    assert again["totals"]["events"] == 16 and again["totals"]["rollback_applied"] == 2
    failed = merge_report(again, [], [{"series_id": "c", "error": "x"}], {"rounds": 3}, 0.1)
    assert failed["built_series"] == 2 and [f["series_id"] for f in failed["failures"]] == ["c"]


def test_season_weighted_rate_compares_each_season_with_itself():
    from opscope.analytics.operator import season_weighted_rate
    from opscope.load import peer_group
    # team: 30 rounds in 2025, 10 in 2026. Other teams: 10% in 2025, 50% in 2026 (four teams each, 20 rounds)
    team = pd.DataFrame({"cohort": ["gc-2025"] * 30 + ["gc-2026"] * 10})
    rows = []
    for cohort, hits in (("gc-2025", 2), ("gc-2026", 10)):
        for t in "abcd":
            rows += [{"cohort": cohort, "team_id": f"{cohort}-{t}", "has": i < hits} for i in range(20)]
    rate, method = season_weighted_rate(team, pd.DataFrame(rows), "has")
    assert method == "typical team" and abs(rate - (30 * 0.10 + 10 * 0.50) / 40) < 1e-9
    assert peer_group(["gc-2025", "gc-2026"]) == "same-season Game Changers"
    assert peer_group(["vct-2025"]) == "VCT 2025"
