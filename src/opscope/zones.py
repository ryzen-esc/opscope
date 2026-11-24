"""Map zones: bomb sites (found from where the spike is planted) and named callouts.

Plants cluster tightly (3–7 m) around each site, so k-means on planter positions finds the sites. The data
can't tell "A" from "B", so `sites.yaml` stores each site's centre and a human-editable name.
Regenerate the centres with `uv run python -m opscope.zones --init` (keeps names already set, matched by position).

The YAML holds only aggregate centre coordinates (no match data), so it is safe to commit.

Callouts ("A Main", "Mid Courtyard", ...) come from the community API at valorant-api.com (/v1/maps), whose
coordinates are the same x/y as GRID's. `uv run python -m opscope.zones --callouts` refreshes `callouts.yaml`.
A position is labelled with its nearest callout point, which approximates the callout's area.
"""
from __future__ import annotations

import argparse
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

SITES_FILE = Path(__file__).with_name("sites.yaml")
SITE_COUNT = {"haven": 3, "lotus": 3}  # every other map has two sites
CALLOUTS_FILE = Path(__file__).with_name("callouts.yaml")
CALLOUTS_URL = "https://valorant-api.com/v1/maps"
MAX_CALLOUT_DIST_CM = 2500  # farther than 25 m from every callout point: leave unnamed


def kmeans(points: np.ndarray, k: int, seeds: int = 8, iters: int = 60) -> np.ndarray:
    """Plain k-means (best of several seeds). Returns centres sorted by x then y for stable ordering."""
    best, best_inertia = None, np.inf
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        centres = points[rng.choice(len(points), k, replace=False)]
        for _ in range(iters):
            labels = ((points[:, None, :] - centres[None]) ** 2).sum(-1).argmin(1)
            new = np.array([points[labels == j].mean(0) if (labels == j).any() else centres[j] for j in range(k)])
            if np.allclose(new, centres):
                break
            centres = new
        inertia = ((points - centres[labels]) ** 2).sum()
        if inertia < best_inertia:
            best, best_inertia = centres, inertia
    order = np.lexsort((best[:, 1], best[:, 0]))
    return best[order]


def plant_positions() -> pd.DataFrame:
    """Planter position at the moment of each plant (from the plant snapshot)."""
    from opscope.load import load
    d = load()
    s = d.snapshots[d.snapshots["moment"] == "plant"]
    r = d.rounds[["game_id", "round_num", "planter_id", "atk_team_id"]]
    p = s.merge(r, on=["game_id", "round_num"])
    p = p[p["player_id"] == p["planter_id"]].dropna(subset=["x", "y"])
    return p[["game_id", "round_num", "map", "atk_team_id", "x", "y"]].reset_index(drop=True)


@cache
def sites() -> dict[str, list[dict]]:
    """{map: [{"name": ..., "x": ..., "y": ...}, ...]} from the YAML file."""
    if not SITES_FILE.exists():
        return {}
    return yaml.safe_load(SITES_FILE.read_text()) or {}


def assign_site(map_name: str, x: np.ndarray | pd.Series, y: np.ndarray | pd.Series) -> np.ndarray:
    """Nearest site name for each point (None if the map has no sites configured)."""
    s = sites().get(map_name)
    x, y = np.asarray(x, float), np.asarray(y, float)
    if not s:
        return np.full(len(x), None, dtype=object)
    cx = np.array([v["x"] for v in s])
    cy = np.array([v["y"] for v in s])
    names = np.array([v["name"] for v in s], dtype=object)
    d = (x[:, None] - cx[None]) ** 2 + (y[:, None] - cy[None]) ** 2
    return names[d.argmin(1)]


@cache
def callouts() -> dict[str, list[dict]]:
    """{map: [{"name": "A Main", "x": ..., "y": ...}, ...]} from callouts.yaml."""
    if not CALLOUTS_FILE.exists():
        return {}
    return yaml.safe_load(CALLOUTS_FILE.read_text()) or {}


def callout_name(super_region: str, region: str) -> str:
    """'A' + 'Main' -> 'A Main'; 'Attacker Side' + 'Spawn' -> 'Attacker Spawn'; 'Mid' + 'Top' -> 'Mid Top'."""
    prefix = super_region.replace(" Side", "").strip()
    return f"{prefix} {region}".strip()


SITE_RADIUS_CM = 800  # plants spread 3–7 m around a site centre


def nearest_callout(map_name: str, x, y) -> np.ndarray:
    """Area name for each point, or None if nothing named is within MAX_CALLOUT_DIST_CM.

    A callout is a single point in the middle of an area, so "nearest point" is approximate: on a big site the
    centre can be closer to a neighbouring callout's point. Bomb sites are known precisely (from plants), so
    anything within SITE_RADIUS_CM of a site centre is named after the site; everything else gets the
    nearest callout. The letter (A/B/C/Mid) is reliable; the exact area name is a best guess near borders.
    """
    pts = callouts().get(map_name)
    x, y = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(y, float))
    out = np.full(len(x), None, dtype=object)
    if pts:
        cx = np.array([p["x"] for p in pts])
        cy = np.array([p["y"] for p in pts])
        names = np.array([p["name"] for p in pts], dtype=object)
        d = np.hypot(x[:, None] - cx[None], y[:, None] - cy[None])
        out = names[d.argmin(1)]
        out[d.min(1) > MAX_CALLOUT_DIST_CM] = None
    for s in sites().get(map_name, []):
        on_site = np.hypot(x - s["x"], y - s["y"]) <= SITE_RADIUS_CM
        out[on_site] = s["name"].replace(" site", " Site")
    return out


def fetch_maps(url: str = CALLOUTS_URL) -> list[dict]:
    """The raw /v1/maps list from valorant-api.com."""
    import json
    import urllib.request
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)["data"]


def minimap_transforms(data: list[dict]) -> dict[str, dict]:
    """Per map, the four numbers that place game x/y on the official minimap (u right, v down, both 0..1):
    u = y * x_mult + x_add, v = x * y_mult + y_add. Public metadata only; no map art is used."""
    out = {}
    for m in data:
        if m.get("xMultiplier") and m.get("callouts"):
            out[m["displayName"].lower()] = {"x_mult": m["xMultiplier"], "y_mult": m["yMultiplier"],
                                             "x_add": m["xScalarToAdd"], "y_add": m["yScalarToAdd"]}
    return out


def fetch_callouts(data: list[dict] | None = None) -> dict[str, list[dict]]:
    """Map callouts from the /v1/maps list (only names + x/y are kept)."""
    data = fetch_maps() if data is None else data
    out = {}
    for m in data:
        pts = [{"name": callout_name(c["superRegionName"], c["regionName"]),
                "x": round(float(c["location"]["x"])), "y": round(float(c["location"]["y"]))}
               for c in (m.get("callouts") or [])]
        if pts:
            out[m["displayName"].lower()] = sorted(pts, key=lambda p: p["name"])
    return out


def init_sites(min_plants: int = 20) -> dict:
    """Compute site centres from plants; keep existing names for centres within 15 m of an old one."""
    old = sites()
    out = {}
    for map_name, g in plant_positions().groupby("map"):
        if len(g) < min_plants:
            continue
        k = SITE_COUNT.get(map_name, 2)
        centres = kmeans(g[["x", "y"]].to_numpy(float), k)
        entries = []
        for i, (cx, cy) in enumerate(centres, 1):
            name = f"Site {i}"
            for o in old.get(map_name, []):
                if np.hypot(o["x"] - cx, o["y"] - cy) < 1500:
                    name = o["name"]
            entries.append({"name": name, "x": round(float(cx)), "y": round(float(cy))})
        out[map_name] = entries
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Bomb-site centres per map")
    ap.add_argument("--init", action="store_true", help="(re)compute site centres from the cache and write the YAML")
    ap.add_argument("--callouts", action="store_true",
                    help="download callouts and minimap transforms from valorant-api.com into callouts.yaml / minimaps.yaml")
    args = ap.parse_args()
    if args.callouts:
        raw = fetch_maps()
        from opscope.geometry import MINIMAPS_FILE
        tf = minimap_transforms(raw)
        MINIMAPS_FILE.write_text(
            "# Minimap transform per map, from the community API at valorant-api.com (/v1/maps): public metadata,\n"
            "# no map art. u = y * x_mult + x_add (right), v = x * y_mult + y_add (down), both 0..1.\n"
            "# Regenerate: uv run python -m opscope.zones --callouts\n" + yaml.safe_dump(tf, sort_keys=True))
        print(f"Wrote {MINIMAPS_FILE} ({len(tf)} maps)")
        data = fetch_callouts(raw)
        header = ("# Map callouts (name + x/y in game units), from the community API at valorant-api.com (/v1/maps).\n"
                  "# Same coordinate system as GRID. Regenerate: uv run python -m opscope.zones --callouts\n")
        CALLOUTS_FILE.write_text(header + yaml.safe_dump(data, sort_keys=True))
        callouts.cache_clear()
        print(f"Wrote {CALLOUTS_FILE} ({sum(len(v) for v in data.values())} callouts on {len(data)} maps)")
    if args.init:
        data = init_sites()
        SITES_FILE.parent.mkdir(exist_ok=True)
        header = ("# Bomb-site centres per map (aggregate of planter positions; no match data).\n"
                  "# Names: nearest valorant-api.com Site callout (see sites.yaml header). Positions in cm.\n")
        SITES_FILE.write_text(header + yaml.safe_dump(data, sort_keys=True))
        sites.cache_clear()
        print(f"Wrote {SITES_FILE} ({sum(len(v) for v in data.values())} sites on {len(data)} maps)")


if __name__ == "__main__":
    main()
