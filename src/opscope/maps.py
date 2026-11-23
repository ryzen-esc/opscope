"""Map geometry derived from the data itself: playable-area backdrop and spawn centres.

No Riot art is used. The backdrop is a density image of every recorded player position on a map,
so walls and off-map areas show up as empty space.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd

from opscope.load import load

BIN_CM = 100  # 1 m backdrop pixels


@dataclass(frozen=True)
class Backdrop:
    map: str
    x0: float
    y0: float
    bin: float
    z: np.ndarray  # shape (ny, nx), log-scaled density in [0, 1]


@cache
def bounds(map_name: str) -> tuple[float, float, float, float]:
    g = load().games
    row = g[g["map"] == map_name].iloc[0]
    return float(row.min_x), float(row.min_y), float(row.max_x), float(row.max_y)


def _all_positions(map_name: str) -> tuple[np.ndarray, np.ndarray]:
    d = load()
    casts = d.casts.loc[d.casts["map"] == map_name, ["x", "y"]]
    eng = d.engagements.loc[d.engagements["map"] == map_name, ["ax", "ay"]].set_axis(["x", "y"], axis=1)
    snaps = d.snapshots.loc[(d.snapshots["map"] == map_name) & d.snapshots["alive"].fillna(False), ["x", "y"]]
    pts = pd.concat([casts, eng, snaps], ignore_index=True).dropna()
    return pts["x"].to_numpy(float), pts["y"].to_numpy(float)


@cache
def backdrop(map_name: str) -> Backdrop:
    x0, y0, x1, y1 = bounds(map_name)
    xs, ys = _all_positions(map_name)
    nx, ny = int((x1 - x0) // BIN_CM) + 1, int((y1 - y0) // BIN_CM) + 1
    h, _, _ = np.histogram2d(ys, xs, bins=[ny, nx], range=[[y0, y0 + ny * BIN_CM], [x0, x0 + nx * BIN_CM]])
    z = np.log1p(h)
    z = z / z.max() if z.max() > 0 else z
    return Backdrop(map_name, x0, y0, BIN_CM, z)


@cache
def spawns(map_name: str) -> dict[str, tuple[float, float]]:
    """Median freeze-start position per side: {'attacker': (x, y), 'defender': (x, y)}."""
    s = load().snapshots
    s = s[(s["map"] == map_name) & (s["moment"] == "fs")].dropna(subset=["x", "y"])
    med = s.groupby("side")[["x", "y"]].median()
    return {side: (float(r.x), float(r.y)) for side, r in med.iterrows()}


def aggression(map_name: str, x: np.ndarray | pd.Series, y: np.ndarray | pd.Series) -> np.ndarray:
    """0 = at defender spawn, 1 = at attacker spawn: d_def / (d_def + d_atk).

    Works on 3-site maps where a single spawn-to-spawn axis would not.
    """
    sp = spawns(map_name)
    (dx, dy), (ax, ay) = sp["defender"], sp["attacker"]
    x, y = np.asarray(x, float), np.asarray(y, float)
    d_def = np.hypot(x - dx, y - dy)
    d_atk = np.hypot(x - ax, y - ay)
    return d_def / (d_def + d_atk)
