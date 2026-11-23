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
              higher_is: str = "neutral") -> None:
    """Percentage card that refuses to make a claim on tiny samples."""
    if n < MIN_SAMPLE:
        stat_card(title, "—", f"{of(k, n, unit)} · too few to call", None)
        return
    lo, hi = wilson(k, n)
    context, tone = None, "accent"
    if league and league[1]:
        lp = pct(*league)
        context = f"league {lp:.0%} · 95% range {lo:.0%}–{hi:.0%}"
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
.ops-value {font-size:2rem;font-weight:700;line-height:1.2;margin-top:2px;}
.ops-sample {color:#c9d3dd;font-size:0.85rem;}
.ops-ctx {color:#8b9bab;font-size:0.78rem;margin-top:4px;}
.ops-insight {background:#0f2533;border-left:4px solid #00AEEF;border-radius:6px;padding:10px 14px;margin:6px 0;color:#dce6ef;}
.ops-insight b {color:#fff;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def insight(text: str) -> None:
    st.markdown(f'<div class="ops-insight">{text}</div>', unsafe_allow_html=True)
