"""Plotly minimap: data-drawn backdrop plus overlays (points, sightlines, spawns)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from opscope.maps import backdrop, spawns
from opscope.ui.theme import ACCENT, AMBER, ATTACK, BG, DISPLAY, GOOD, MONO, SIDE_COLORS, TEXT_DIM
from opscope.ui.theme import COLORWAY as CATEGORY_COLORS

BUCKET_COLORS = {"0–20s": ACCENT, "20–40s": GOOD, "40–60s": AMBER, "60s+": ATTACK}
FLOOR = [[0, "#132131"], [1, "#2b4258"]]
EDGE = "#4f86ad"


def _edges(mask: np.ndarray) -> np.ndarray:
    """Cells on the boundary of the playable area (in the mask, with a 4-neighbour outside it)."""
    pad = np.pad(mask, 1, constant_values=False)
    inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    return mask & ~inner


def base_map(map_name: str, height: int = 620) -> go.Figure:
    """Data-drawn floor plan: a soft floor, a bright outline where walls are, ATK/DEF spawn badges."""
    bd = backdrop(map_name)
    ny, nx = bd.z.shape
    # Blur the raw "anyone stood here" mask a little: fills 1 m speckle holes and rounds the jagged edges.
    floor = _blur((bd.z > 0.05).astype(float), 0.9) > 0.45
    grid = dict(x0=bd.x0 + bd.bin / 2, dx=bd.bin, y0=bd.y0 + bd.bin / 2, dy=bd.bin, showscale=False, hoverinfo="skip")
    fig = go.Figure()
    fig.add_trace(go.Heatmap(z=np.where(floor, bd.z, np.nan), colorscale=FLOOR, name="map", **grid))
    fig.add_trace(go.Heatmap(z=np.where(_edges(floor), 1.0, np.nan), colorscale=[[0, EDGE], [1, EDGE]],
                             name="walls", **grid))
    for side, (x, y) in spawns(map_name).items():
        color = SIDE_COLORS.get(side, TEXT_DIM)
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text", text=[side[:3].upper()], textposition="middle center",
            marker=dict(symbol="square", size=30, color=BG, line=dict(color=color, width=2)),
            textfont=dict(family=MONO, color=color, size=11), hoverinfo="skip", showlegend=False,
        ))
    pad = 0.07 * max(nx, ny) * bd.bin  # room for spawn badges at the edges
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(visible=False, range=[bd.x0 - pad, bd.x0 + nx * bd.bin + pad]),
        yaxis=dict(visible=False, range=[bd.y0 - pad, bd.y0 + ny * bd.bin + pad], scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0),
        dragmode="pan",
    )
    return fig


def add_sightlines(fig: go.Figure, df: pd.DataFrame, color: str = "rgba(242,95,92,0.55)", name: str = "Op kills",
                   hover: list[str] | None = None) -> None:
    """Shooter → victim line per kill: a ring at the shooter, an ✕ at the victim."""
    if df.empty:
        return
    xs = np.column_stack([df["ax"], df["tx"], np.full(len(df), np.nan)]).ravel()
    ys = np.column_stack([df["ay"], df["ty"], np.full(len(df), np.nan)]).ravel()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=1.6),
                             hoverinfo="skip", name=name, legendgroup="kills"))
    fig.add_trace(go.Scatter(x=df["ax"], y=df["ay"], mode="markers", name="shooter", legendgroup="kills",
                             marker=dict(symbol="circle-open", size=11, color=ATTACK, line=dict(width=2)),
                             text=hover, hoverinfo="text" if hover else "skip", showlegend=False))
    fig.add_trace(go.Scatter(x=df["tx"], y=df["ty"], mode="markers", name="victim", legendgroup="kills",
                             marker=dict(symbol="x-thin", size=9, color=ATTACK, line=dict(width=2, color=ATTACK)),
                             hoverinfo="skip", showlegend=False))


def _blur(h: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur with plain numpy (no scipy dependency)."""
    r = max(1, int(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    h = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, h)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, h)


def add_density(fig: go.Figure, df: pd.DataFrame, map_name: str, rgb: str = "0,174,239",
                bin_cm: float = 300, sigma_bins: float = 1.3) -> None:
    """Soft density cloud of positions (3 m bins, blurred to match the ±1–4 m position error)."""
    if len(df) < 3:
        return
    bd = backdrop(map_name)
    ny_px, nx_px = bd.z.shape
    x1, y1 = bd.x0 + nx_px * bd.bin, bd.y0 + ny_px * bd.bin
    nx, ny = int((x1 - bd.x0) // bin_cm) + 1, int((y1 - bd.y0) // bin_cm) + 1
    h, _, _ = np.histogram2d(df["y"], df["x"], bins=[ny, nx],
                             range=[[bd.y0, bd.y0 + ny * bin_cm], [bd.x0, bd.x0 + nx * bin_cm]])
    z = _blur(h, sigma_bins)
    z = z / z.max() if z.max() > 0 else z
    fig.add_trace(go.Heatmap(
        z=z, x0=bd.x0 + bin_cm / 2, dx=bin_cm, y0=bd.y0 + bin_cm / 2, dy=bin_cm,
        colorscale=[[0, f"rgba({rgb},0)"], [0.12, f"rgba({rgb},0)"], [0.25, f"rgba({rgb},0.18)"],
                    [1, f"rgba({rgb},0.7)"]], zmin=0, zmax=1,
        showscale=False, hoverinfo="skip", name="density", zsmooth="best",
    ))


def add_points_by_category(fig: go.Figure, df: pd.DataFrame, category: str, hover_cols: list[str],
                           arrows: bool = False, arrow_cm: float = 700) -> dict[str, str]:
    """One colored trace per category value (e.g. per ability); optional aim arrows from the view vector.

    Returns the color used for each category so the page can reuse it.
    """
    colors = {}
    order = df[category].value_counts().index.tolist()
    for i, value in enumerate(order):
        color = CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
        colors[value] = color
        part = df[df[category] == value]
        if arrows and {"view_x", "view_y"} <= set(part.columns):
            aim = part.dropna(subset=["view_x", "view_y"])
            if not aim.empty:
                xs = np.column_stack([aim["x"], aim["x"] + aim["view_x"] * arrow_cm, np.full(len(aim), np.nan)]).ravel()
                ys = np.column_stack([aim["y"], aim["y"] + aim["view_y"] * arrow_cm, np.full(len(aim), np.nan)]).ravel()
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=1),
                                         opacity=0.5, hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=part["x"], y=part["y"], mode="markers", name=str(value),
            marker=dict(size=7, color=color, line=dict(width=0.6, color=BG), opacity=0.85),
            customdata=part[hover_cols].to_numpy(),
            hovertemplate="<br>".join(f"{c}: %{{customdata[{i}]}}" for i, c in enumerate(hover_cols)) + "<extra></extra>",
        ))
    return colors


def add_throw_lines(fig: go.Figure, df: pd.DataFrame, color: str = "rgba(220,230,240,0.35)") -> None:
    """Faint line from where each utility was cast (cast_x/cast_y) to where it is estimated to land (x/y)."""
    if df.empty:
        return
    xs = np.column_stack([df["cast_x"], df["x"], np.full(len(df), np.nan)]).ravel()
    ys = np.column_stack([df["cast_y"], df["y"], np.full(len(df), np.nan)]).ravel()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=1),
                             hoverinfo="skip", name="thrown from"))


def add_spots(fig: go.Figure, spots: pd.DataFrame, radius_cm: float, label_col: str = "label") -> None:
    """Numbered rings for habitual spots."""
    for _, s in spots.iterrows():
        fig.add_shape(type="circle", x0=s.x - radius_cm, x1=s.x + radius_cm, y0=s.y - radius_cm, y1=s.y + radius_cm,
                      line=dict(color="#ffffff", width=2, dash="dot"), fillcolor="rgba(255,255,255,0.07)")
    fig.add_trace(go.Scatter(
        x=spots["x"], y=spots["y"] + radius_cm * 1.6, mode="text", text=spots[label_col],
        textfont=dict(family=DISPLAY, color="#ffffff", size=13), hoverinfo="skip", showlegend=False))


def add_sites(fig: go.Figure, sites: pd.DataFrame, radius_cm: float, color: str = AMBER) -> None:
    """Bomb sites: a ring with the site letter inside and a caption (e.g. "55 plants") under it."""
    for _, s in sites.iterrows():
        fig.add_shape(type="circle", x0=s.x - radius_cm, x1=s.x + radius_cm, y0=s.y - radius_cm, y1=s.y + radius_cm,
                      line=dict(color=color, width=2), fillcolor="rgba(245,183,0,0.10)")
    fig.add_trace(go.Scatter(
        x=sites["x"], y=sites["y"], mode="text", text=[str(n).split()[0] for n in sites["name"]],
        textfont=dict(family=DISPLAY, color=color, size=24), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=sites["x"], y=sites["y"] - radius_cm * 1.45, mode="text", text=sites["caption"],
        textfont=dict(family=MONO, color="#ffffff", size=11), hoverinfo="skip", showlegend=False))


def add_points_by_bucket(fig: go.Figure, df: pd.DataFrame, hover_cols: list[str]) -> None:
    for bucket, color in BUCKET_COLORS.items():
        part = df[df["bucket"] == bucket]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(
            x=part["x"], y=part["y"], mode="markers", name=bucket,
            marker=dict(size=8, color=color, line=dict(width=1, color=BG), opacity=0.85),
            customdata=part[hover_cols].to_numpy(),
            hovertemplate="<br>".join(f"{c}: %{{customdata[{i}]}}" for i, c in enumerate(hover_cols)) + "<extra></extra>",
        ))
