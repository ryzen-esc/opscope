"""The JSON API: setup guidance without a cache, input checks, and (where the cache exists) every endpoint."""
import pytest
from starlette.testclient import TestClient

from opscope.api import _clean, create_app


@pytest.fixture
def client():
    return TestClient(create_app())


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
    r = TestClient(create_app(tmp_path)).get("/")
    assert r.status_code == 200 and "hi" in r.text
    assert r.headers["cache-control"] == "no-cache"  # browsers recheck the app's files, so updates show up


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

    ut = real.get("/api/utility?team=79&side=defender&classes=trap").json()
    lot = ut["maps"]["lotus"]
    assert lot["casts"] and lot["habits"] and lot["who"]
    assert any(c["phase"] == "buy" and c["t"] <= 0 for c in lot["casts"])  # pre-round setups play before 0:00
