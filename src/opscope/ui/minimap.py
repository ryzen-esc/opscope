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


def add_points_by_bucket(fig: go.Figure, df: pd.DataFrame, hover_cols: list[str]) -> None:
    for bucket, color in BUCKET_COLORS.items():
        part = df[df["bucket"] == bucket]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(
            x=part["x"], y=part["y"], mode="markers", name=f"first seen {bucket}",
            marker=dict(size=10, color=color, line=dict(width=1, color="#0e1117"), opacity=0.9),
            customdata=part[hover_cols].to_numpy(),
            hovertemplate="<br>".join(f"{c}: %{{customdata[{i}]}}" for i, c in enumerate(hover_cols)) + "<extra></extra>",
        ))
