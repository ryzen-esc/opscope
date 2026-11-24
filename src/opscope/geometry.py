"""Map geometry in the official minimap frame.

Outlines are traced from the official minimap images (valorant-api.com `displayIcon`), downloaded on first
use into the gitignored data cache: the repo never contains Riot's art or a copy of it. Without network access
the outline falls back to one drawn from the match data (below), so the app still works offline; that
fallback is kept in memory only, so the next run tries the download again.

GRID positions and the official minimap use the same game units but different axes: valorant-api.com
(/v1/maps) gives four numbers per map that place a game position on the minimap,

    u = y * x_mult + x_add   (left -> right, 0..1)
    v = x * y_mult + y_add   (top -> bottom, 0..1)

so game x runs *up* the minimap and game y runs *across* it. Plotting x to the right and y up (as a plain
scatter does) mirrors the map. Every layer we draw goes through `to_minimap`, so the maps read the way
players know them.

The floor plan comes from the precise positions only: ability casts from the supplement (sub-metre), plus the
round-start, buy-end and plant snapshots. Shot and hit positions are left out: they are ±1–4 m and blur the
walls. Positions are binned on a 50 cm grid laid along the minimap axes, smoothed, closed to fill gaps, traced
into rings, simplified, and straightened: walls within a few degrees of a 45° step are snapped to it, the way
a hand-drawn minimap looks. Checked against the official minimaps by eye (never copied or traced).
"""
from __future__ import annotations

import json
from collections import deque
from functools import cache
from pathlib import Path

import numpy as np
import yaml

MINIMAPS_FILE = Path(__file__).with_name("minimaps.yaml")
SCALE = 1000          # outputs are in minimap units: 0..1000 on both axes
BIN_CM = 50           # floor grid resolution
CLOSE_CELLS = 2       # closing radius (cells): fills gaps up to ~2 m between recorded positions
MIN_HITS = 1          # positions per cell to count as floor
BLUR_CELLS = 1.2      # smooths the 50 cm staircase before tracing...
BLUR_THRESHOLD = 0.35  # ...and this cut decides where the smoothed floor ends
MIN_PART_CELLS = 120  # floor patches smaller than this (~30 m²) are dropped; wall blocks smaller are filled
RDP_EPS_CELLS = 2.0   # simplification tolerance (1 m)
SNAP_DEG = 13         # snap a wall to the nearest 45° step when it is this close
GEOMETRY_VERSION = 6  # bump when the tracing or the payload changes (6: bbox covers spawns and sites)
MAPS_API = "https://valorant-api.com/v1/maps"
TRACED = "official minimap (traced)"
ICON_PX = 1024


@cache
def transforms() -> dict[str, dict]:
    if not MINIMAPS_FILE.exists():
        return {}
    return yaml.safe_load(MINIMAPS_FILE.read_text()) or {}


def to_minimap(map_name: str, x, y) -> tuple[np.ndarray, np.ndarray]:
    """Game x/y -> minimap (u, v) in 0..SCALE, v pointing down."""
    t = transforms()[map_name]
    x, y = np.asarray(x, float), np.asarray(y, float)
    return (y * t["x_mult"] + t["x_add"]) * SCALE, (x * t["y_mult"] + t["y_add"]) * SCALE


def rotate(u, v, turns: int) -> tuple[np.ndarray, np.ndarray]:
    """Quarter turns clockwise about the minimap centre (a rotation, so the map is never mirrored)."""
    u, v = np.asarray(u, float), np.asarray(v, float)
    for _ in range(turns % 4):
        u, v = SCALE - v, u
    return u, v


def turns_for(attacker_uv) -> int:
    """Quarter turns that put the attacker spawn at the bottom, the way the in-game minimap is usually read."""
    return max(range(4), key=lambda k: float(rotate(*attacker_uv, k)[1]))


def _axes(map_name: str, x, y) -> tuple[np.ndarray, np.ndarray]:
    """Game x/y -> centimetres along the minimap's right (h) and down (w) axes."""
    t = transforms()[map_name]
    x, y = np.asarray(x, float), np.asarray(y, float)
    return y * np.sign(t["x_mult"]), x * np.sign(t["y_mult"])


def _axes_to_minimap(map_name: str, h, w) -> tuple[np.ndarray, np.ndarray]:
    t = transforms()[map_name]
    return ((np.asarray(h) * abs(t["x_mult"]) + t["x_add"]) * SCALE,
            (np.asarray(w) * abs(t["y_mult"]) + t["y_add"]) * SCALE)


# ---- mask helpers (plain numpy) -----------------------------------------------------------------------

def _dilate(m: np.ndarray, r: int) -> np.ndarray:
    out = m.copy()
    p = np.pad(m, r)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= p[r + dy:r + dy + m.shape[0], r + dx:r + dx + m.shape[1]]
    return out


def _erode(m: np.ndarray, r: int) -> np.ndarray:
    return ~_dilate(~m, r)


def _components(m: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """4-connected labels (0 = background) and the size of each label."""
    lab = np.zeros(m.shape, dtype=np.int32)
    sizes = [0]
    ny, nx = m.shape
    for sy, sx in zip(*np.nonzero(m)):
        if lab[sy, sx]:
            continue
        k = len(sizes)
        lab[sy, sx] = k
        q, n = deque([(sy, sx)]), 0
        while q:
            y, x = q.popleft()
            n += 1
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < ny and 0 <= xx < nx and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = k
                    q.append((yy, xx))
        sizes.append(n)
    return lab, sizes


def _blur(h: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur with plain numpy."""
    r = max(1, int(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    h = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, h)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, h)


def clean_mask(hits: np.ndarray, min_hits: int = MIN_HITS, close: int = CLOSE_CELLS,
               min_part: int = MIN_PART_CELLS, shrink: int = 0, blur: float = BLUR_CELLS,
               thr: float = BLUR_THRESHOLD) -> np.ndarray:
    """Counts per cell -> a clean floor mask: threshold, close small gaps, shrink back off the walls (positions
    are ±1–4 m, so the raw floor bleeds into them), drop specks, fill small wall holes."""
    m = hits >= min_hits
    if blur:  # smooth the 50 cm staircase before tracing
        m = _blur(m.astype(float), blur) > thr
    pad = close + 1
    m = _erode(_dilate(np.pad(m, pad), close), close + shrink)[pad:-pad, pad:-pad]
    lab, sizes = _components(m)
    sz = np.array(sizes)
    keep = sz >= max(min_part, 0.15 * sz[1:].max(initial=0))  # the map, not stray patches outside it
    keep[0] = False
    m = keep[lab]
    lab, sizes = _components(np.pad(~m, 1, constant_values=True))  # holes = background not touching the border
    border = lab[0, 0]
    small = np.array(sizes) < min_part
    small[0] = small[border] = False
    m |= small[lab][1:-1, 1:-1]
    return m


# ---- tracing, simplifying, straightening ---------------------------------------------------------------

def trace_rings(mask: np.ndarray) -> list[np.ndarray]:
    """Closed boundary rings of a mask, in cell-corner coordinates (col, row), floor kept on the left."""
    f = np.pad(mask, 1)
    edges: dict[tuple, list[tuple]] = {}
    for j, i in zip(*np.nonzero(mask)):
        j, i = int(j), int(i)
        if not f[j, i + 1]:
            edges.setdefault((i + 1, j), []).append((i, j))
        if not f[j + 2, i + 1]:
            edges.setdefault((i, j + 1), []).append((i + 1, j + 1))
        if not f[j + 1, i]:
            edges.setdefault((i, j), []).append((i, j + 1))
        if not f[j + 1, i + 2]:
            edges.setdefault((i + 1, j + 1), []).append((i + 1, j))
    rings = []
    while edges:
        start = next(iter(edges))
        ring, cur = [start], start
        while True:
            nxt = edges[cur].pop()
            if not edges[cur]:
                del edges[cur]
            if nxt == start or nxt not in edges:
                break
            ring.append(nxt)
            cur = nxt
        if len(ring) >= 4:
            rings.append(np.array(ring, float))
    return rings


def rdp(pts: np.ndarray, eps: float) -> np.ndarray:
    """Ramer-Douglas-Peucker on a closed ring (split at the point farthest from the first)."""
    def simp(p: np.ndarray) -> np.ndarray:
        if len(p) < 3:
            return p
        a, b = p[0], p[-1]
        ab = b - a
        length = np.hypot(*ab)
        d = (np.abs(ab[0] * (p[:, 1] - a[1]) - ab[1] * (p[:, 0] - a[0])) / length if length
             else np.hypot(*(p - a).T))
        i = int(d.argmax())
        if d[i] > eps:
            return np.vstack([simp(p[:i + 1])[:-1], simp(p[i:])])
        return np.vstack([a, b])
    # Keep only the corners of the traced staircase, so the ring starts on a real corner.
    d_in, d_out = pts - np.roll(pts, 1, 0), np.roll(pts, -1, 0) - pts
    turn = np.abs(d_in[:, 0] * d_out[:, 1] - d_in[:, 1] * d_out[:, 0]) > 1e-9
    if turn.sum() >= 3:
        pts = pts[turn]
    far = int(np.hypot(*(pts - pts[0]).T).argmax())
    loop = np.vstack([pts, pts[:1]])
    return np.vstack([simp(loop[:far + 1])[:-1], simp(loop[far:])[:-1]])


def _angle(d: np.ndarray) -> float:
    return float(np.degrees(np.arctan2(d[1], d[0])))


def straighten(pts: np.ndarray, snap_deg: float = SNAP_DEG, max_move: float = 3.0) -> np.ndarray:
    """Snap each wall to the nearest 45° step when close, merge walls that end up parallel, and rebuild the
    corners as intersections of neighbouring walls (a corner may move at most `max_move` cells)."""
    pts = pts.copy()
    for _ in range(4):  # merging can expose new parallel neighbours
        n = len(pts)
        if n < 4:
            return pts
        d = np.roll(pts, -1, 0) - pts
        ang = np.array([_angle(v) for v in d])
        snapped = np.round(ang / 45) * 45
        ok = np.abs(ang - snapped) <= snap_deg
        dirs = np.where(ok, snapped, ang)
        # drop vertices between two walls with the same direction (within 8°)
        turn = np.abs((dirs - np.roll(dirs, 1) + 180) % 360 - 180)
        drop = turn < 8
        if not drop.any() or drop.all():
            break
        pts = pts[~drop]
    d = np.roll(pts, -1, 0) - pts
    ang = np.array([_angle(v) for v in d])
    snapped = np.round(ang / 45) * 45
    dirs = np.radians(np.where(np.abs(ang - snapped) <= snap_deg, snapped, ang))
    mids = (pts + np.roll(pts, -1, 0)) / 2
    u = np.column_stack([np.cos(dirs), np.sin(dirs)])
    out = pts.copy()
    for i in range(len(pts)):
        p1, d1 = mids[i - 1], u[i - 1]   # wall arriving at vertex i
        p2, d2 = mids[i], u[i]           # wall leaving vertex i
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-6:
            continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        q = p1 + t * d1
        if np.hypot(*(q - pts[i])) <= max_move:
            out[i] = q
    return out


def _area(r: np.ndarray) -> float:
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


# ---- the floor plan ------------------------------------------------------------------------------------

def _positions(map_name: str) -> tuple[np.ndarray, np.ndarray]:
    from opscope.load import load
    from opscope.zones import plant_positions
    d = load()
    precise = (d.casts["map"] == map_name) & (d.casts["quality"] == "ok")
    parts = [
        d.casts.loc[precise, ["x", "y"]].to_numpy(float),
        d.snapshots.loc[(d.snapshots["map"] == map_name) & d.snapshots["alive"].fillna(False), ["x", "y"]].to_numpy(float),
    ]
    p = plant_positions()
    parts.append(p.loc[p["map"] == map_name, ["x", "y"]].to_numpy(float))
    pts = np.vstack(parts)
    pts = pts[np.isfinite(pts).all(1)]
    g = d.games[d.games["map"] == map_name].iloc[0]  # GRID's map bounds
    inside = ((pts[:, 0] >= g.min_x) & (pts[:, 0] <= g.max_x) & (pts[:, 1] >= g.min_y) & (pts[:, 1] <= g.max_y))
    return pts[inside, 0], pts[inside, 1]


def floor_rings(map_name: str, x: np.ndarray, y: np.ndarray) -> list[list[list[float]]]:
    """Positions -> straightened floor rings in minimap units (outer outline and wall blocks alike)."""
    h, w = _axes(map_name, x, y)
    if not len(h):
        return []
    h0, w0 = h.min() - 4 * BIN_CM, w.min() - 4 * BIN_CM
    nx, ny = int((h.max() - h0) // BIN_CM) + 5, int((w.max() - w0) // BIN_CM) + 5
    hits, _, _ = np.histogram2d(w, h, bins=[ny, nx], range=[[w0, w0 + ny * BIN_CM], [h0, h0 + nx * BIN_CM]])
    mask = clean_mask(hits)
    rings = []
    for r in trace_rings(mask):
        s = straighten(rdp(r, RDP_EPS_CELLS))
        if len(s) < 3 or abs(_area(s)) < MIN_PART_CELLS / 2:
            continue
        u, v = _axes_to_minimap(map_name, h0 + s[:, 0] * BIN_CM, w0 + s[:, 1] * BIN_CM)
        rings.append([[round(float(a), 1), round(float(b), 1)] for a, b in zip(u, v)])
    rings.sort(key=len, reverse=True)
    return rings


# ---- traced from the official minimap -----------------------------------------------------------------

def _icon_path(map_name: str) -> Path:
    from opscope.ingest.build import cache_dir
    return cache_dir() / "minimaps" / f"{map_name}.png"


def fetch_icon(map_name: str) -> np.ndarray | None:
    """The official minimap as an RGBA array, downloaded once into the local cache (None when offline)."""
    path = _icon_path(map_name)
    if not path.exists():
        import urllib.request
        try:
            with urllib.request.urlopen(MAPS_API, timeout=30) as resp:
                maps = json.load(resp)["data"]
            url = next(m["displayIcon"] for m in maps if m["displayName"].lower() == map_name and m.get("displayIcon"))
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=60) as resp:
                path.write_bytes(resp.read())
        except (OSError, StopIteration, KeyError, ValueError):
            return None
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGBA"))


def _drop_small(m: np.ndarray, min_px: int) -> np.ndarray:
    lab, sizes = _components(m)
    keep = np.array(sizes) >= min_px
    keep[0] = False
    return keep[lab]


def _rings_px(mask: np.ndarray, eps: float = 0.8, min_area: float = 12) -> list[np.ndarray]:
    out = []
    for r in trace_rings(mask):
        s = rdp(r, eps)
        if len(s) >= 3 and abs(_area(s)) >= min_area:
            out.append(s)
    return out


def trace_icon(rgba: np.ndarray) -> dict[str, list]:
    """Minimap image -> vector layers in minimap units (unrotated): floor rings (walls are the holes), props
    (the lighter boxes and ledges drawn on the floor) and site areas (the tinted plant zones)."""
    h, w = rgba.shape[:2]
    r, g, b, a = (rgba[..., i].astype(int) for i in range(4))
    opaque = a > 128
    floor = _drop_small(opaque, 200)
    holes = _drop_small(~floor, 12)  # wall pixels; tiny specks inside the floor are filled
    floor = ~holes
    grey = (np.abs(r - g) < 6) & (np.abs(g - b) < 6)
    base = int(np.median(r[floor & grey]))
    tinted = floor & ((r - b) > 20)                       # plant sites are olive
    props = floor & grey & (r > base + 6) & (r < 240)     # lighter boxes, ledges, cover
    sx, sy = SCALE / w, SCALE / h
    to_units = lambda ring: [[round(float(x * sx), 1), round(float(y * sy), 1)] for x, y in ring]  # noqa: E731
    return {
        "rings": [to_units(x) for x in sorted(_rings_px(floor), key=len, reverse=True)],
        "props": [to_units(x) for x in _rings_px(_drop_small(props, 30), eps=1.0, min_area=30)],
        "site_areas": [to_units(x) for x in _rings_px(_drop_small(tinted, 400), eps=1.0, min_area=400)],
    }


def inside(pt, rings) -> bool:
    """Point on the floor (even-odd over every ring, so wall blocks count as outside)."""
    x, y = pt
    c = False
    for r in rings:
        r = np.asarray(r, float)
        x1, y1 = r[:, 0], r[:, 1]
        x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
        cross = (y1 > y) != (y2 > y)
        xs = (x2 - x1) * (y - y1) / np.where(cross, y2 - y1, 1) + x1
        c ^= bool(np.count_nonzero(cross & (x < xs)) % 2)
    return c


def snap_to_floor(pt, rings, inset: float = 6.0) -> list[float]:
    """Move a marker that sits on a wall or off the map onto the nearest floor, `inset` units in."""
    p = np.asarray(pt, float)
    if inside(p, rings):
        return [round(float(p[0]), 1), round(float(p[1]), 1)]
    best, best_d = p, np.inf
    for r in rings:
        a = np.asarray(r, float)
        ab = np.roll(a, -1, 0) - a
        t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-9), 0, 1)
        q = a + ab * t[:, None]
        d = np.hypot(*(q - p).T)
        i = int(d.argmin())
        if d[i] < best_d:
            best, best_d = q[i], d[i]
    step = (best - p) / max(best_d, 1e-9)
    for k in (1, 2, 4):  # nudge past the wall line until we're on the floor
        q = best + step * inset * k
        if inside(q, rings):
            return [round(float(q[0]), 1), round(float(q[1]), 1)]
    return [round(float(best[0]), 1), round(float(best[1]), 1)]


def to_view(map_name: str, x, y) -> tuple[np.ndarray, np.ndarray]:
    """Game x/y -> the frame every OpScope map is drawn in: the official minimap, turned so attackers start at
    the bottom. Use this for every layer (dots, kills, habit spots, landings)."""
    return rotate(*to_minimap(map_name, x, y), map_geometry(map_name)["turns"])


def _geometry_path(map_name: str) -> Path:
    from opscope.ingest.build import cache_dir
    return cache_dir() / "geometry" / f"{map_name}.json"


_FALLBACK: dict[str, dict] = {}  # match-data outlines, kept for this process only


def map_geometry(map_name: str, refresh: bool = False) -> dict:
    """Floor rings, spawns, sites and callouts for one map, all in minimap units. A traced minimap is cached under
    the (gitignored) data cache. The match-data fallback (no network) is kept in memory only, so the next run tries
    the download again instead of keeping the rough outline for good."""
    path = _geometry_path(map_name)
    if not refresh:
        if map_name in _FALLBACK:
            return _FALLBACK[map_name]
        if path.exists():
            g = json.loads(path.read_text())
            if g.get("version") == GEOMETRY_VERSION and g.get("source") == TRACED:
                return g
    from opscope.maps import spawns
    from opscope.zones import callouts, sites
    sp = spawns(map_name)
    k = turns_for(to_minimap(map_name, *sp["attacker"])) if "attacker" in sp else 0
    icon = fetch_icon(map_name)
    if icon is not None:
        layers, source = trace_icon(icon), TRACED
    else:
        layers, source = {"rings": floor_rings(map_name, *_positions(map_name)), "props": [], "site_areas": []}, "match data"
    turn = lambda rings: [np.column_stack(rotate(*np.array(r).T, k)).round(1).tolist() for r in rings]  # noqa: E731
    layers = {name: turn(rings) for name, rings in layers.items()}
    rings = layers["rings"]
    pt = lambda x, y: [round(float(c), 1) for c in rotate(*to_minimap(map_name, x, y), k)]  # noqa: E731
    sites_ = [{"name": s["name"], "at": pt(s["x"], s["y"])} for s in sites().get(map_name, [])]
    site_areas = []
    for ring in layers["site_areas"]:  # name each tinted zone after the plant-site centre inside or nearest it
        c = np.array(ring).mean(0)
        near = min(sites_, key=lambda s: np.hypot(*(np.array(s["at"]) - c)), default=None)
        site_areas.append({"name": near["name"] if near else None, "ring": ring})
    spawns_ = {side: pt(*xy) for side, xy in sp.items()}
    # The view box covers the floor and every spawn and site marker, so none is cropped (a sparse fallback outline
    # can be much smaller than the map).
    allp = np.array([p for r in rings for p in r] + list(spawns_.values()) + [s["at"] for s in sites_], float)
    bbox = ([float(allp[:, 0].min()), float(allp[:, 1].min()), float(allp[:, 0].max()), float(allp[:, 1].max())]
            if len(allp) else [0.0, 0.0, float(SCALE), float(SCALE)])
    g = {
        "version": GEOMETRY_VERSION, "map": map_name, "source": source, "turns": k, "rings": rings,
        "units_per_m": round(SCALE * abs(transforms()[map_name]["x_mult"]) * 100, 3),  # map units per metre
        "props": layers["props"], "site_areas": site_areas,
        "bbox": bbox,
        "spawns": spawns_,
        "sites": sites_,
        # Community callout markers sometimes sit on a wall or roof; pins should land on walkable floor.
        "callouts": [{"name": c["name"], "at": snap_to_floor(pt(c["x"], c["y"]), rings)} for c in callouts().get(map_name, [])],
    }
    if source != TRACED:
        _FALLBACK[map_name] = g
        return g
    _FALLBACK.pop(map_name, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(g))
    return g
