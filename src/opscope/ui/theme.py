"""One palette and one Plotly template for the whole app, so every chart and card looks like the same product."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---- palette ------------------------------------------------------------------------------------
BG = "#0b0f14"
PANEL = "#111821"
PANEL_2 = "#0f151c"
BORDER = "#223040"
GRID = "#1a2430"
TEXT = "#dce6ef"
TEXT_DIM = "#9aa9b8"
TEXT_FAINT = "#6c7e90"
ACCENT = "#00AEEF"   # Cloud9-style cyan: the app's own colour, and defense
ATTACK = "#F25F5C"
DEFENSE = ACCENT
AMBER = "#F5B700"    # "pay attention"
GOOD = "#7BD389"
NEUTRAL_BAR = "#3a4b5e"  # comparison bars (other teams)
SIDE_COLORS = {"attacker": ATTACK, "defender": DEFENSE}
COLORWAY = [ACCENT, AMBER, GOOD, ATTACK, "#B388EB", "#4DD0E1", "#FF9F68", "#c9d3dd"]

FONT = "Inter, 'Source Sans Pro', sans-serif"
MONO = "'JetBrains Mono', 'Source Code Pro', monospace"
DISPLAY = "'Chakra Petch', Inter, sans-serif"

# ---- Plotly template ----------------------------------------------------------------------------
_axis = dict(automargin=True, gridcolor=GRID, zerolinecolor=GRID, linecolor=BORDER, tickcolor=BORDER,
             tickfont=dict(family=MONO, size=11, color=TEXT_DIM), title=dict(font=dict(size=12, color=TEXT_DIM), standoff=10))
pio.templates["opscope"] = go.layout.Template(layout=go.Layout(
    font=dict(family=FONT, color=TEXT, size=13),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=COLORWAY, margin=dict(l=0, r=0, t=10, b=0),
    xaxis=_axis, yaxis=_axis,
    hoverlabel=dict(bgcolor=PANEL, bordercolor=ACCENT, font=dict(family=FONT, color=TEXT, size=12)),
    legend=dict(orientation="h", bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_DIM, size=12)),
    bargap=0.25,
))
pio.templates["opscope"].data.bar = [go.Bar(textfont=dict(family=MONO, size=11), textposition="auto",
                                            marker=dict(line=dict(width=0)))]
pio.templates.default = "opscope"


def chart(fig: go.Figure, interactive: bool = False) -> None:
    """Show a Plotly figure with the OpScope template (Streamlit's own chart theme would override it).

    interactive=True keeps zoom/pan (maps); otherwise the mode bar is hidden.
    """
    config = {"scrollZoom": True, "displaylogo": False} if interactive else {"displayModeBar": False}
    st.plotly_chart(fig, width="stretch", theme=None, config=config)
