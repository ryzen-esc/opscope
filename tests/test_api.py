"""The JSON API: setup guidance without a cache, input checks, and (where the cache exists) every endpoint."""
import pytest
from starlette.testclient import TestClient

from opscope.api import _clean, create_app


BASE = "http://127.0.0.1"  # the app only answers its own host names (TestClient's default is "testserver")


@pytest.fixture
def client():
    return TestClient(create_app(), base_url=BASE)


def test_missing_cache_returns_setup_steps(tmp_path, monkeypatch, client):
    monkeypatch.setenv("OPSCOPE_CACHE", str(tmp_path))  # empty folder: no cache built yet
    from opscope.load import load
    load.cache_clear()
    try:
        r = client.get("/api/meta")
        assert r.status_code == 503
        body = r.json()
        assert body["error"] == "setup"
        assert any("opscope.ingest.build" in s for s in body["setup"])
    finally:
        load.cache_clear()


def test_clean_makes_numpy_and_nan_json_safe():
    import numpy as np
    import pandas as pd
    out = _clean({"a": np.int64(3), "b": np.float32(0.5), "c": float("nan"), "d": [np.bool_(True), pd.NA], 1: None})
    assert out == {"a": 3, "b": 0.5, "c": None, "d": [True, None], "1": None}


def test_static_front_end_is_served(tmp_path):
    (tmp_path / "index.html").write_text("<p>hi</p>")
    r = TestClient(create_app(tmp_path), base_url=BASE).get("/")
    assert r.status_code == 200 and "hi" in r.text
    assert r.headers["cache-control"] == "no-cache"  # browsers recheck the app's files, so updates show up


def test_foreign_host_is_refused(tmp_path):
    """DNS rebinding: a page whose hostname points at 127.0.0.1 must not be able to read the API or the front end."""
    (tmp_path / "index.html").write_text("<p>hi</p>")
    app = create_app(tmp_path)
    for base in ("http://127.0.0.1:8000", "http://localhost:8123", "http://127.0.0.1"):
        assert TestClient(app, base_url=base).get("/").status_code == 200
    bad = TestClient(app, base_url="http://attacker.example:8000")
    for path in ("/api/meta", "/api/report?team=79", "/api/operator?team=79&maps=haven", "/", "/index.html"):
        r = bad.get(path)
        assert r.status_code == 400, path
        assert "hi" not in r.text and "teams" not in r.text
    assert TestClient(app).get("/api/meta").status_code == 400  # TestClient's default "testserver" host too


# ---- against the real local cache (skipped where it hasn't been built) --------------------------------

@pytest.fixture
def real(client):
    from opscope.ingest.build import cache_dir
    if not (cache_dir() / "games.parquet").exists():
        pytest.skip("no local cache (build it with python -m opscope.ingest.build)")
    from opscope.load import load
    load.cache_clear()
    return client


def test_bad_input_is_rejected(real):
    assert real.get("/api/report?team=nope").status_code == 404
    assert real.get("/api/operator?team=79&weapon=knife").status_code == 400
    assert real.get("/api/operator?team=79&side=middle").status_code == 400
    assert real.get("/api/utility?team=79&classes=bombs").status_code == 400
    assert real.get("/api/map/atlantis").status_code == 404


def test_every_endpoint_answers_with_the_documented_figures(real):
    meta = real.get("/api/meta").json()
    assert any(t["id"] == "79" for t in meta["teams"])
    assert real.get("/api/team/79/filters").json()["maps"]

    g = real.get("/api/map/haven").json()
    assert g["rings"] and len(g["sites"]) == 3 and set(g["spawns"]) == {"attacker", "defender"}
    assert g["spawns"]["attacker"][1] > g["spawns"]["defender"][1]  # turned so attackers start at the bottom

    rep = real.get("/api/report?team=79").json()
    assert rep["self_scout"] and rep["plan"] and rep["insights"]
    for ins in rep["insights"]:  # every finding carries its evidence
        assert ins["n"] >= ins["k"] >= 0 and ins["lo"] <= ins["rate"] <= ins["hi"]
    haven = next(i for i in rep["insights"] if i["category"] == "Operator" and i["map"] == "haven"
                 and i["side"] == "defender")
    assert (haven["k"], haven["n"], round(haven["base"], 2)) == (30, 80, 0.19)  # quoted in README/CLAUDE.md
    lotus_plants = next(p for p in rep["plants"] if p["map"] == "lotus")
    assert lotus_plants["peers"].startswith("typical") and all(s["base"] is not None for s in lotus_plants["sites"])

    op = real.get("/api/operator?team=79&weapon=operator&side=defender").json()
    assert op["maps"]["haven"]["gun_rounds"] == 30
    assert "93 of 96" in op["glance"][0]
    lotus = next(m for m in op["by_map"] if m["map"] == "lotus")
    assert (lotus["k"], lotus["n"]) == (2, 134)
    pos = op["maps"]["haven"]["positions"][0]
    assert {"at", "t", "round", "player", "area", "via", "what"} <= set(pos)
    assert all(p["what"] for p in op["maps"]["haven"]["positions"])  # every dot says what happened
    assert all(k["victim"] for k in op["maps"]["haven"]["kills"])
    info = op["rounds"][pos["round"]]  # every dot can say which round it came from
    assert info["map"] == "haven" and info["opponent"] and info["date"] and info["round_num"] >= 1

    ut = real.get("/api/utility?team=79&side=defender&classes=trap").json()
    lot = ut["maps"]["lotus"]
    assert lot["casts"] and lot["habits"] and lot["who"]
    assert any(c["phase"] == "buy" and c["t"] <= 0 for c in lot["casts"])  # pre-round setups play before 0:00
    assert ut["rounds"][lot["casts"][0]["round"]]["opponent"] and "area" in lot["casts"][0]
    assert len(lot["players"]) >= 5  # the whole roster, including players with no traps


def test_every_finding_is_clear_of_the_typical_team(real):
    # 0 of n vs a typical 0% used to slip through as a "Rarely buy" finding (Wilson rounding at k = 0)
    for team in ("79", "96", "97"):
        for ins in real.get(f"/api/report?team={team}").json()["insights"]:
            assert ins["base"] < ins["lo"] or ins["base"] > ins["hi"], (team, ins["k"], ins["n"], ins["base"])


def test_every_plan_item_links_its_own_finding(real):
    # Findings can share map, side, category, k and n (Operator and Odin both 0 of 44, two abilities of one
    # player); the plan carries the exact position so the PLAN tag and advice land on the right card.
    key = lambda x: (x["map"], x["side"], x["category"], x["k"], x["n"])  # the old, non-unique match
    collisions = 0
    for team in ("79", "96", "97", "1611"):  # 1611: plans 1 and 2 share that key
        rep = real.get(f"/api/report?team={team}").json()
        for p in rep["plan"]:
            assert 0 <= p["index"] < len(rep["insights"]), (team, p["headline"])
            assert rep["insights"][p["index"]] == p["evidence"], (team, p["headline"])
            first = next(i for i, x in enumerate(rep["insights"]) if key(x) == key(p["evidence"]))
            collisions += first != p["index"]
        assert len({p["index"] for p in rep["plan"]}) == len(rep["plan"])
    assert collisions  # the teams above include a case the old key got wrong


def test_operator_counts_distinct_gun_rounds(real):
    # NRG has rounds with two Operator holders: per-map counts and "Survived" must count each round once,
    # so the HUD, the < 8 note and the "seen" panel agree with the rate-by-map rows and the headline k.
    op = real.get("/api/operator?team=97&weapon=operator&side=defender").json()
    for row in op["by_map"]:
        assert op["maps"][row["map"]]["gun_rounds"] == row["k"], row["map"]
    assert op["kept"]["n"] == op["rate"]["k"] and op["kept"]["k"] <= op["kept"]["n"]


def test_zero_gun_sentence_uses_the_right_article(real):
    op = real.get("/api/operator?team=79&weapon=operator&side=attacker&opponents=1079").json()
    assert op["rate"]["k"] == 0
    assert "never had an Operator" in op["glance"][0]


def test_rounds_carry_their_full_start_time(real):
    # "Round k of n here" counts oldest first; with only the date, two games on one map on the same UTC day
    # were ordered by game id. The full start time sorts them (ISO UTC strings sort as text).
    ut = real.get("/api/utility?team=1079&side=defender").json()
    rounds = [r for r in ut["rounds"] if r["map"] == "split"]
    assert rounds and all(r["started"] and r["started"][:10] == r["date"] for r in rounds)
    by_day = {}
    for r in rounds:
        by_day.setdefault(r["date"], set()).add((r["started"], r["game"]))
    assert any(len(g) > 1 for g in by_day.values())  # the case that used to fall back to the game id
    assert all(len({s for s, _ in g}) == len(g) for g in by_day.values())  # and the start time tells them apart


def test_one_dot_per_moment(real):
    # GRID logs some kills 1 ms after their damage (9.499 dmg, 9.500 kill): both show as 0:09.5, so they are one
    # moment, not two stacked dots ("hit X for 150" and "killed X" with no damage).
    op = real.get("/api/operator?team=79&weapon=operator&side=defender").json()
    for name, m in op["maps"].items():
        keys = [(p["round"], p["t"], p["player"]) for p in m["positions"]]
        assert len(keys) == len(set(keys)), name


def test_early_setup_is_sent_per_map(real):
    # The web app never sends `maps` (the map is a view control), so the early-setup summary has to come per map.
    from opscope.analytics.operator import Scope, operator_report
    op = real.get("/api/operator?team=79&weapon=operator&side=defender").json()
    a = op["maps"]["haven"]["aggression"]
    want = operator_report(Scope(team_id="79", weapon="operator", side="defender", maps=("haven",))).aggression_summary()
    assert a["n"] == want["n"] >= 8 and abs(a["percentile"] - want["percentile"]) < 1e-9
    assert all(m["aggression"] is None for m in op["maps"].values() if m["gun_rounds"] < 8)


def test_filters_that_leave_no_games_return_an_empty_report(real):
    # The dashboard used to read rep.pool before checking rep.empty and crashed, leaving no way to clear the
    # filters. An empty report carries only what the front end needs to say so; the drawer's options still load.
    rep = real.get("/api/report?team=79&patches=0.01").json()
    assert rep["empty"] is True and rep["team"] == "79" and rep["name"] and rep["self_scout"] is True
    assert "pool" not in rep and "insights" not in rep
    tf = real.get("/api/team/79/filters").json()
    assert tf["opponents"] and tf["events"] and tf["patches"]
    assert real.get("/api/operator?team=79&side=defender&patches=0.01").json()["empty"] is True
    assert real.get("/api/utility?team=79&side=defender&patches=0.01").json()["empty"] is True


def test_base_label_names_a_pooled_comparison():
    # The card and evidence bar said "typical team" even when the rate was pooled over all other rounds
    from opscope.present import base_label
    assert base_label("typical VCT 2025 team") == "typical team"
    assert base_label("typical Game Changers 2026 player") == "typical player"
    assert base_label("all other Game Changers 2026 rounds") == "all other rounds"
    assert base_label("all other VCT 2025 plants") == "all other plants"
    assert base_label("other teams") == "other teams"


def test_every_finding_says_what_its_comparison_is(real):
    pooled = 0
    for team in ("79", "3429"):
        for ins in real.get(f"/api/report?team={team}").json()["insights"]:
            pooled += ins["peers"].startswith("all other")
            assert ins["base_label"].split()[0] == ins["peers"].split()[0], (team, ins["peers"], ins["base_label"])
    assert pooled  # Cloud9 GC has at least one pooled comparison (Operator on attack on Summit)
