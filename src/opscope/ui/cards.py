"""Insight cards: one headline number, the sample it came from, and league context."""
from __future__ import annotations

import streamlit as st

from opscope.analytics.stats import MIN_SAMPLE, of, pct, wilson


def stat_card(title: str, value: str, sample: str, context: str | None = None, tone: str = "neutral") -> None:
    colors = {"neutral": "#c9d3dd", "good": "#7BD389", "bad": "#F25F5C", "accent": "#00AEEF"}
    ctx = f'<div class="ops-ctx">{context}</div>' if context else ""
    st.markdown(
        f'<div class="ops-card"><div class="ops-title">{title}</div>'
        f'<div class="ops-value" style="color:{colors.get(tone, colors["neutral"])}">{value}</div>'
        f'<div class="ops-sample">{sample}</div>{ctx}</div>',
        unsafe_allow_html=True,
    )


def rate_card(title: str, k: int, n: int, unit: str = "rounds", league: tuple[int, int] | None = None,
              league_label: str = "league", league_rate: float | None = None,
              higher_is: str = "neutral") -> None:
    """Percentage card that refuses to make a claim on tiny samples."""
    if n < MIN_SAMPLE:
        stat_card(title, "—", f"{of(k, n, unit)} · too few to call", None)
        return
    lo, hi = wilson(k, n)
    context, tone = None, "accent"
    if league and league[1]:
        lp = league_rate if league_rate is not None else pct(*league)
        context = f"{league_label} {lp:.0%} · 95% range {lo:.0%}–{hi:.0%}"
        if higher_is != "neutral" and not (lo <= lp <= hi):
            above = pct(k, n) > lp
            tone = "good" if above == (higher_is == "good") else "bad"
    else:
        context = f"95% range {lo:.0%}–{hi:.0%}"
    stat_card(title, f"{pct(k, n):.0%}", of(k, n, unit), context, tone)


CSS = """
<style>
.ops-card {background:#151c24;border:1px solid #243140;border-radius:10px;padding:14px 16px;height:100%;}
.ops-title {color:#8b9bab;font-size:0.78rem;text-transform:uppercase;letter-spacing:.06em;}
.ops-value {font-size:clamp(1.15rem, 2.1vw, 2rem);font-weight:700;line-height:1.2;margin-top:2px;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ops-sample {color:#c9d3dd;font-size:0.85rem;}
.ops-ctx {color:#8b9bab;font-size:0.78rem;margin-top:4px;}
.ops-insight {background:#0f2533;border-left:4px solid #00AEEF;border-radius:6px;padding:10px 14px;margin:6px 0;color:#dce6ef;}
.ops-insight b {color:#fff;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


CATEGORY_COLORS = {"Operator": "#F25F5C", "Utility": "#00AEEF", "Attack": "#F5B700"}


def insight_card(ins) -> None:
    """A ranked scouting insight: category chip, map/side, sentence, sample and league context."""
    color = CATEGORY_COLORS.get(ins.category, "#8b9bab")
    side = {"attacker": "attack", "defender": "defense"}.get(ins.side, ins.side)
    league = f" · {getattr(ins, 'peers', 'others')} {ins.league_rate:.0%}" if ins.league_rate is not None else ""
    former = (f'<div class="ops-ctx" style="color:#F5B700">⚠ Former player: {ins.departed}</div>'
              if getattr(ins, "departed", None) else "")
    st.markdown(
        f'<div class="ops-card" style="border-left:4px solid {color}">'
        f'<div class="ops-title"><span style="color:{color}">{ins.category}</span> · {ins.map.title()} · {side}</div>'
        f'<div style="color:#dce6ef;margin:6px 0 4px 0;line-height:1.4">{ins.text}</div>'
        f'<div class="ops-ctx">{ins.sample}{league}</div>{former}</div>',
        unsafe_allow_html=True,
    )


def suggestion_card(s, number: int) -> None:
    """An anti-strat suggestion with the evidence it came from."""
    ins = s.evidence
    color = CATEGORY_COLORS.get(ins.category, "#8b9bab")
    st.markdown(
        f'<div class="ops-card" style="display:flex;gap:12px;align-items:flex-start;margin-bottom:8px">'
        f'<div style="font-size:1.4rem;font-weight:700;color:{color};min-width:1.6rem">{number}</div>'
        f'<div><div style="color:#fff;font-weight:600;line-height:1.35">{s.headline}</div>'
        f'<div style="color:#c9d3dd;margin-top:3px;line-height:1.4">{s.detail}</div>'
        f'<div class="ops-ctx" style="margin-top:4px">Based on: {ins.category} · {ins.map.title()} · {ins.sample}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def insight(text: str) -> None:
    st.markdown(f'<div class="ops-insight">{text}</div>', unsafe_allow_html=True)
