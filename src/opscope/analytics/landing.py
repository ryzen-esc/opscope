"""Estimated landing spots for thrown damaging utility.

GRID records where a player stood when casting, not where the utility landed. For abilities that deal damage
(mollies, nanoswarm, shock darts, ...), the players they hurt were standing in the area, which gives a ground
truth:

1. Pair each cast with the damage that same player later did with that ability in the round
   (each damage event goes to the most recent earlier cast). The victims' median position is the "landing".
2. Utility lands along the aim (median sideways miss ~2–3 m), so the model is one number per ability and
   aim-pitch bin: how far along the aim it lands (median), falling back to the ability's overall median.
3. Validate on held-out series against the naive answer (the cast position).

Only abilities that pass validation get estimates. Smokes, alarmbots, cameras and the like deal no damage,
so there's nothing to check them against, and they stay as cast spots.
"""
from __future__ import annotations

import json
from functools import cache

import numpy as np
import pandas as pd

from opscope.ingest.build import cache_dir
from opscope.load import load

DAMAGING = ["nanoswarm", "snake-bite", "hot-hands", "incendiary", "mosh-pit", "paint-shells", "frag-ment",
            "aftershock", "shock-bolt", "trapwire", "razorvine", "blaze"]
LINGERING = {"nanoswarm", "trapwire", "razorvine"}  # may hurt someone long after being placed
PITCH_EDGES = np.arange(-45, 50, 5)  # degrees
MIN_BIN = 15
MODEL_VERSION = 1


def _unit_aim(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    vx, vy, vz = (df[c].to_numpy(float) for c in ("view_x", "view_y", "view_z"))
    h = np.hypot(vx, vy)
    h[h == 0] = np.nan
    pitch = np.degrees(np.arcsin(np.clip(vz, -1, 1)))
    return vx / h, vy / h, pitch


def ground_truth() -> pd.DataFrame:
    """One row per cast that later dealt damage: cast position, aim, and the victims' median position."""
    d = load()
    e = d.engagements
    dmg = e[(e["kind"] == "dmg") & (e["phase"] == "live") & e["weapon"].isin(DAMAGING)].dropna(subset=["tx", "ty"])
    c = d.casts[d.casts["ability"].isin(DAMAGING) & (d.casts["pos_source"] == "supplement")]
    c = c.dropna(subset=["view_x", "view_y", "view_z", "t"])
    keys = ["game_id", "round_num", "player_id", "ability"]
    da = dmg[["game_id", "round_num", "actor_id", "weapon", "t", "tx", "ty"]].rename(
        columns={"actor_id": "player_id", "weapon": "ability", "t": "dt"})
    m = da.merge(c[keys + ["series_id", "event_id", "t", "x", "y", "view_x", "view_y", "view_z"]], on=keys)
    m = m[m["dt"] >= m["t"]]
    m = m.sort_values("t").groupby(keys + ["dt", "tx", "ty"]).tail(1)   # most recent earlier cast
    window = np.where(m["ability"].isin(LINGERING), 60.0, 12.0)
    m = m[(m["dt"] - m["t"]) <= window]
    g = m.groupby("event_id").agg(
        series_id=("series_id", "first"), ability=("ability", "first"), x=("x", "first"), y=("y", "first"),
        view_x=("view_x", "first"), view_y=("view_y", "first"), view_z=("view_z", "first"),
        tx=("tx", "median"), ty=("ty", "median"), hits=("tx", "size")).reset_index()
    ux, uy, pitch = _unit_aim(g)
    g["pitch"] = pitch
    g["along"] = (g["tx"] - g["x"]) * ux + (g["ty"] - g["y"]) * uy
    return g.dropna(subset=["along", "pitch"])


def fit(pairs: pd.DataFrame) -> dict:
    """{ability: {"all": median distance, "bins": {bin index: median distance}}} (distances in cm)."""
    model = {}
    for ability, g in pairs.groupby("ability"):
        overall = float(g["along"].median())
        b = np.digitize(g["pitch"], PITCH_EDGES)
        stats = g.groupby(b)["along"].agg(["median", "size"])
        model[ability] = {"all": overall,
                          "bins": {int(k): float(v) if n >= MIN_BIN else overall
                                   for k, (v, n) in zip(stats.index, stats.to_numpy())}}
    return model


def predict(model: dict, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Estimated landing x, y (NaN for abilities the model doesn't cover)."""
    ux, uy, pitch = _unit_aim(df)
    bins = np.digitize(np.nan_to_num(pitch), PITCH_EDGES)
    dist = np.full(len(df), np.nan)
    for i, (ability, b) in enumerate(zip(df["ability"], bins)):
        m = model.get(ability)
        if m:
            dist[i] = m["bins"].get(str(b), m["bins"].get(b, m["all"]))
    return df["x"].to_numpy(float) + ux * dist, df["y"].to_numpy(float) + uy * dist


def validate(pairs: pd.DataFrame, test_share: float = 0.2, seed: int = 0) -> dict:
    """Held-out-series errors (metres) for the cast position, a fixed distance, and the pitch model."""
    rng = np.random.default_rng(seed)
    series = pairs["series_id"].unique()
    test = set(rng.choice(series, max(1, int(len(series) * test_share)), replace=False))
    train, held = pairs[~pairs["series_id"].isin(test)], pairs[pairs["series_id"].isin(test)]
    model = fit(train)
    const = {a: {"all": v["all"], "bins": {}} for a, v in model.items()}
    out = {"test_casts": len(held), "test_series": len(test), "abilities": {}}
    errs = {}
    for name, m in (("cast", None), ("fixed", const), ("model", model)):
        if m is None:
            px, py = held["x"].to_numpy(float), held["y"].to_numpy(float)
        else:
            px, py = predict(m, held)
        errs[name] = np.hypot(px - held["tx"], py - held["ty"]) / 100
    for name, e in errs.items():
        out[f"median_{name}_m"] = round(float(np.nanmedian(e)), 1)
    for ability, idx in held.groupby("ability").groups.items():
        out["abilities"][ability] = {n: round(float(np.nanmedian(errs[n].loc[idx])), 1) for n in errs} | {"n": len(idx)}
    return out


@cache
def landing_model() -> dict:
    """Fitted on all pairs (after validation), cached on disk with its validation numbers."""
    path = cache_dir() / "baselines" / f"landing_model_v{MODEL_VERSION}.json"
    if path.exists():
        return json.loads(path.read_text())
    pairs = ground_truth()
    report = validate(pairs)
    keep = {a for a, v in report["abilities"].items() if v["model"] < v["cast"]}  # only abilities it improves
    model = {a: v for a, v in fit(pairs).items() if a in keep}
    out = {"model": model, "validation": report, "pairs": len(pairs)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def add_landings(casts: pd.DataFrame) -> pd.DataFrame:
    """Add land_x / land_y (estimated) to a casts frame; NaN where no validated model exists."""
    if casts.empty:
        return casts.assign(land_x=pd.Series(dtype=float), land_y=pd.Series(dtype=float))
    model = landing_model()["model"]
    ok = casts["ability"].isin(list(model)) & casts[["view_x", "view_y", "view_z"]].notna().all(axis=1)
    lx = np.full(len(casts), np.nan)
    ly = np.full(len(casts), np.nan)
    if ok.any():
        px, py = predict(model, casts[ok])
        lx[ok.to_numpy()] = px
        ly[ok.to_numpy()] = py
    return casts.assign(land_x=lx, land_y=ly)
