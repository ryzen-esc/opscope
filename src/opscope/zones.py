"""Bomb sites per map, found from where the spike is planted.

Plants cluster tightly (3–7 m) around each site, so k-means on planter positions finds the sites. The data
can't tell "A" from "B", so `sites.yaml` stores each site's centre and a human-editable name.
Regenerate the centres with `uv run python -m opscope.zones --init` (keeps names already set, matched by position).

The YAML holds only aggregate centre coordinates (no match data), so it is safe to commit.
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
    args = ap.parse_args()
    if args.init:
        data = init_sites()
        SITES_FILE.parent.mkdir(exist_ok=True)
        header = ("# Bomb-site centres per map (aggregate of planter positions; no match data).\n"
                  "# Rename 'Site N' to the real callout (A/B/C). Positions are in game units (cm).\n")
        SITES_FILE.write_text(header + yaml.safe_dump(data, sort_keys=True))
        sites.cache_clear()
        print(f"Wrote {SITES_FILE} ({sum(len(v) for v in data.values())} sites on {len(data)} maps)")


if __name__ == "__main__":
    main()
