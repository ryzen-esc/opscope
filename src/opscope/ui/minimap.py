"""Plotly minimap: data-drawn backdrop plus overlays (points, sightlines, spawns)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from opscope.maps import backdrop, spawns

BUCKET_COLORS = {"0–20s": "#00AEEF", "20–40s": "#7BD389", "40–60s": "#F5B700", "60s+": "#F25F5C"}
SIDE_COLORS = {"attacker": "#F25F5C", "defender": "#00AEEF"}


def base_map(map_name: str, height: int = 620) -> go.Figure:
    bd = backdrop(map_name)
    ny, nx = bd.z.shape
    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=np.where(bd.z > 0.05, bd.z, np.nan), x0=bd.x0 + bd.bin / 2, dx=bd.bin, y0=bd.y0 + bd.bin / 2, dy=bd.bin,
        colorscale=[[0, "#1d2733"], [1, "#4a5d73"]], showscale=False, hoverinfo="skip", name="map",
    ))
    for side, (x, y) in spawns(map_name).items():
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text", text=[f"{side[:3].upper()} spawn"], textposition="bottom center",
            marker=dict(symbol="square", size=12, color=SIDE_COLORS.get(side, "#aaa")),
            textfont=dict(color="#9aa7b4", size=11), hoverinfo="skip", showlegend=False,
        ))
    pad = 0.06 * max(nx, ny) * bd.bin  # room for spawn labels at the edges
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[bd.x0 - pad, bd.x0 + nx * bd.bin + pad]),
        yaxis=dict(visible=False, range=[bd.y0 - pad, bd.y0 + ny * bd.bin + pad], scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", y=1.02, x=0, font=dict(color="#c9d3dd"), bgcolor="rgba(0,0,0,0)"),
        dragmode="pan",
    )
    return fig


def add_sightlines(fig: go.Figure, df: pd.DataFrame, color: str = "rgba(242,95,92,0.45)", name: str = "Op kills") -> None:
    """Shooter → victim line per kill; the shooter end is marked."""
    if df.empty:
        return
    xs = np.column_stack([df["ax"], df["tx"], np.full(len(df), np.nan)]).ravel()
    ys = np.column_stack([df["ay"], df["ty"], np.full(len(df), np.nan)]).ravel()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=1.4),
                             hoverinfo="skip", name=name))
    fig.add_trace(go.Scatter(x=df["tx"], y=df["ty"], mode="markers", name="victim",
                             marker=dict(symbol="x", size=6, color=color), hoverinfo="skip", showlegend=False))


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
        z=np.where(z > 0.12, z, np.nan), x0=bd.x0 + bin_cm / 2, dx=bin_cm, y0=bd.y0 + bin_cm / 2, dy=bin_cm,
        colorscale=[[0, f"rgba({rgb},0.15)"], [1, f"rgba({rgb},0.75)"]], zmin=0.12, zmax=1,
        showscale=False, hoverinfo="skip", name="density", zsmooth="best",
    ))


CATEGORY_COLORS = ["#00AEEF", "#F5B700", "#7BD389", "#F25F5C", "#B388EB", "#4DD0E1", "#FF9F68", "#E0E0E0"]


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
            marker=dict(size=7, color=color, line=dict(width=0.5, color="#0e1117"), opacity=0.85),
            customdata=part[hover_cols].to_numpy(),
            hovertemplate="<br>".join(f"{c}: %{{customdata[{i}]}}" for i, c in enumerate(hover_cols)) + "<extra></extra>",
        ))
    return colors


def add_spots(fig: go.Figure, spots: pd.DataFrame, radius_cm: float, label_col: str = "label") -> None:
    """Numbered rings for habitual spots."""
    for _, s in spots.iterrows():
        fig.add_shape(type="circle", x0=s.x - radius_cm, x1=s.x + radius_cm, y0=s.y - radius_cm, y1=s.y + radius_cm,
                      line=dict(color="#ffffff", width=2), fillcolor="rgba(255,255,255,0.08)")
    fig.add_trace(go.Scatter(
        x=spots["x"], y=spots["y"] + radius_cm * 1.6, mode="text", text=spots[label_col],
        textfont=dict(color="#ffffff", size=13), hoverinfo="skip", showlegend=False))


def add_points_by_bucket(fig: go.Figure, df: pd.DataFrame, hover_cols: list[str]) -> None:
    for bucket, color in BUCKET_COLORS.items():
        part = df[df["bucket"] == bucket]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(
            x=part["x"], y=part["y"], mode="markers", name=bucket,
            marker=dict(size=8, color=color, line=dict(width=1, color="#0e1117"), opacity=0.85),
            customdata=part[hover_cols].to_numpy(),
            hovertemplate="<br>".join(f"{c}: %{{customdata[{i}]}}" for i, c in enumerate(hover_cols)) + "<extra></extra>",
        ))
