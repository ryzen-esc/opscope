"""Cards and page furniture: one headline number, the sample it came from, and league context.

The visual signature is the evidence bar: the team's rate, its 95% range, and a tick for the typical team,
so "is this real?" can be read at a glance on every card.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from opscope.analytics.stats import MIN_SAMPLE, of, pct, wilson
from opscope.ui.brand import WORDMARK_HTML
from opscope.ui.theme import (ACCENT, AMBER, ATTACK, BORDER, DEFENSE, GOOD, PANEL, PANEL_2, TEXT, TEXT_DIM,
                              TEXT_FAINT)

TONES = {"neutral": TEXT, "good": GOOD, "bad": ATTACK, "accent": ACCENT, "amber": AMBER}
CATEGORY_COLORS = {"Operator": ATTACK, "Utility": ACCENT, "Attack": AMBER}
CATEGORY_ICONS = {"Operator": "◎", "Utility": "◆", "Attack": "▲"}
# What each insight category is about, in a coach's words ("Operator" covers Operator, Odin, Outlaw and Marshal).
CATEGORY_LABELS = {"Operator": "Gun choice", "Utility": "Utility habit", "Attack": "Plant site"}


def category_tag(category: str) -> str:
    return f"{CATEGORY_ICONS.get(category, '')} {CATEGORY_LABELS.get(category, category)}"
SIDE_BADGES = {"attack": ("ATK", ATTACK), "defense": ("DEF", DEFENSE)}


def _side_word(side: str) -> str:
    return {"attacker": "attack", "defender": "defense"}.get(side, side)


def side_badge(side_word: str) -> str:
    label, color = SIDE_BADGES.get(side_word, (side_word.upper()[:3], TEXT_DIM))
    return f'<span class="ops-badge" style="color:{color};border-color:{color}">{label}</span>'


def evidence_bar(k: int, n: int, peer_rate: float | None = None, color: str = ACCENT, peer_label: str = "typical") -> str:
    """HTML bar on a 0–100% scale: shaded 95% range, solid marker at the team's rate, grey tick for peers."""
    if not n:
        return ""
    p = pct(k, n)
    lo, hi = wilson(k, n)
    peer = ""
    if peer_rate is not None:
        peer = (f'<div class="ops-ev-peer" style="left:calc({peer_rate:.4f} * 100%)" '
                f'title="{escape(peer_label)} {peer_rate:.0%}"></div>')
    return (
        f'<div class="ops-ev" title="{k} of {n}: 95% range {lo:.0%}–{hi:.0%}">'
        f'<div class="ops-ev-range" style="left:calc({lo:.4f} * 100%);width:calc({hi - lo:.4f} * 100%);'
        f'background:{color}55"></div>'
        f'{peer}<div class="ops-ev-dot" style="left:calc({p:.4f} * 100%);background:{color}"></div></div>'
    )


def stat_card(title: str, value: str, sample: str, context: str | None = None, tone: str = "neutral",
              bar: str = "") -> None:
    ctx = f'<div class="ops-ctx">{context}</div>' if context else ""
    st.markdown(
        f'<div class="ops-card ops-cut"><div class="ops-title">{title}</div>'
        f'<div class="ops-value" style="color:{TONES.get(tone, TEXT)}">{value}</div>'
        f'<div class="ops-sample">{sample}</div>{bar}{ctx}</div>',
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
    context, tone, lp = None, "accent", None
    if league and league[1]:
        lp = league_rate if league_rate is not None else pct(*league)
        context = f"{league_label} {lp:.0%} · 95% range {lo:.0%}–{hi:.0%}"
        if higher_is != "neutral" and not (lo <= lp <= hi):
            above = pct(k, n) > lp
            tone = "good" if above == (higher_is == "good") else "bad"
    else:
        context = f"95% range {lo:.0%}–{hi:.0%}"
    stat_card(title, f"{pct(k, n):.0%}", of(k, n, unit), context, tone,
              bar=evidence_bar(k, n, lp, TONES[tone], league_label))


CSS = f"""
<style>
/* ---- chrome ---- */
header[data-testid="stHeader"] {{background:rgba(11,15,20,.94);border-bottom:1px solid {BORDER};backdrop-filter:blur(6px);}}
.block-container {{padding-top:2.2rem;}}
h1, h2, h3 {{letter-spacing:.02em;}}
h2, h3 {{text-transform:uppercase;font-size:1.05rem !important;color:{TEXT_DIM} !important;letter-spacing:.14em;
         border-bottom:1px solid {BORDER};padding-bottom:.35rem !important;margin-top:1.2rem;}}
[data-testid="stCaptionContainer"] {{color:{TEXT_FAINT};}}
.ops-wordmark {{font-family:'Chakra Petch',sans-serif;font-weight:700;font-size:1.45rem;letter-spacing:.16em;color:{TEXT};}}
.ops-accent {{color:{ACCENT};}}
.ops-tagline {{color:{TEXT_FAINT};font-size:.78rem;letter-spacing:.06em;margin:-2px 0 6px;}}
@keyframes ops-in {{from {{opacity:0;transform:translateY(4px);}} to {{opacity:1;transform:none;}}}}

/* ---- loading ---- */
.ops-splash {{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:70vh;}}
.ops-splash-reticle {{animation:ops-spin 2.4s cubic-bezier(.6,0,.4,1) infinite;}}
@keyframes ops-spin {{0% {{transform:rotate(0) scale(1);}} 50% {{transform:rotate(90deg) scale(.9);}} 100% {{transform:rotate(180deg) scale(1);}}}}
.ops-splash-bar {{width:220px;height:3px;background:{BORDER};margin-top:18px;overflow:hidden;}}
.ops-splash-bar div {{width:35%;height:3px;background:{ACCENT};animation:ops-scan 1.3s ease-in-out infinite;}}
@keyframes ops-scan {{from {{transform:translateX(-100%);}} to {{transform:translateX(290%);}}}}
[data-testid="stSpinner"] {{color:{ACCENT};font-family:'JetBrains Mono',monospace;font-size:.8rem;letter-spacing:.06em;}}
.ops-picks-label {{color:{TEXT_DIM};font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;}}

/* ---- cards ---- */
.ops-cut {{clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,0 100%);}}
.ops-card {{background:{PANEL};border:1px solid {BORDER};padding:14px 16px;height:100%;animation:ops-in .25s ease-out;}}
.ops-title {{color:{TEXT_DIM};font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;}}
.ops-value {{font-family:'JetBrains Mono',monospace;font-size:clamp(1.15rem, 2.1vw, 1.9rem);font-weight:500;line-height:1.25;
             margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.ops-sample {{color:{TEXT};font-size:.82rem;font-family:'JetBrains Mono',monospace;}}
.ops-ctx {{color:{TEXT_FAINT};font-size:.76rem;margin-top:5px;}}
.ops-badge {{font-family:'JetBrains Mono',monospace;font-size:.68rem;font-weight:700;border:1px solid;padding:0 5px;
             letter-spacing:.08em;vertical-align:1px;}}
.ops-insight {{background:{PANEL_2};border:1px solid {BORDER};border-left:3px solid {ACCENT};padding:10px 14px;margin:6px 0;
               color:{TEXT};animation:ops-in .25s ease-out;}}
.ops-insight b, .ops-card b {{color:#fff;font-weight:600;}}

/* ---- evidence bar ---- */
.ops-ev {{position:relative;height:14px;background:#18212c;margin:8px 0 2px;}}
.ops-ev-range {{position:absolute;top:3px;height:8px;}}
.ops-ev-dot {{position:absolute;top:0;width:3px;height:14px;margin-left:-1px;}}
.ops-hero .ops-ev {{height:20px;margin:12px 0 4px;}}
.ops-hero .ops-ev-range {{top:4px;height:12px;}}
.ops-hero .ops-ev-dot {{height:20px;width:4px;}}
.ops-hero .ops-ev-peer {{height:26px;}}
.ops-ev-peer {{position:absolute;top:-3px;width:2px;height:20px;margin-left:-1px;background:{TEXT_DIM};}}

/* ---- dossier header ---- */
.ops-dossier {{background:linear-gradient(100deg,#10304a 0%,#0f1a24 55%,{PANEL} 100%);border-left:3px solid {ACCENT};
               padding:18px 22px 16px;margin-bottom:12px;animation:ops-in .3s ease-out;}}
.ops-kicker {{color:{TEXT_DIM};font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;}}
.ops-team {{font-family:'Chakra Petch',sans-serif;font-weight:700;font-size:clamp(1.8rem,4vw,2.8rem);color:#fff;
            line-height:1.05;margin:4px 0 10px;letter-spacing:.03em;}}
.ops-chips {{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;align-items:center;}}
.ops-chip {{font-family:'JetBrains Mono',monospace;font-size:.78rem;padding:2px 9px;border:1px solid #2b3e52;color:#c3d0dc;
            background:rgba(11,15,20,.35);}}
.ops-stats {{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;}}
.ops-stat-v {{font-family:'JetBrains Mono',monospace;font-size:clamp(1.1rem,2.2vw,1.6rem);color:#fff;line-height:1.2;}}
.ops-stat-s {{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:{TEXT_FAINT};}}
@media (max-width: 640px) {{ .ops-stats {{grid-template-columns:repeat(2,minmax(0,1fr));}} }}

/* ---- headline finding and game plan ---- */
.ops-hero {{background:{PANEL};border:1px solid {BORDER};padding:16px 20px;margin-bottom:6px;animation:ops-in .35s ease-out;}}
.ops-hero-text {{font-size:1.15rem;color:#fff;line-height:1.4;margin:6px 0 10px;}}
.ops-hero-num {{font-family:'JetBrains Mono',monospace;font-size:2rem;font-weight:500;line-height:1;}}
.ops-plan {{display:flex;gap:14px;align-items:flex-start;margin-bottom:8px;background:{PANEL_2};border:1px solid {BORDER};
            padding:12px 14px;animation:ops-in .25s ease-out;}}
.ops-plan-n {{font-family:'Chakra Petch',sans-serif;font-weight:700;font-size:1.6rem;line-height:1;min-width:2.1rem;}}
.ops-plan-h {{color:#fff;font-weight:600;line-height:1.35;}}
.ops-plan-d {{color:#c3d0dc;margin-top:3px;line-height:1.4;font-size:.92rem;}}
.ops-mapkey {{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.8rem;color:#c3d0dc;margin:2px 0 6px;}}
.ops-mapkey b {{color:#fff;}}
.ops-meta {{color:{TEXT_FAINT};font-size:.75rem;margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.sidebar.markdown(WORDMARK_HTML, unsafe_allow_html=True)


def dossier_header(kicker: str, title: str, chips: list[str] | None = None, chip_label: str = "",
                   stats: list[tuple[str, str, str, str]] | None = None) -> None:
    """Banner at the top of a page. stats: (label, value, sub-line, colour)."""
    chip_html = ""
    if chips:
        label = f'<span class="ops-kicker" style="margin-right:4px">{chip_label}</span>' if chip_label else ""
        chip_html = '<div class="ops-chips">' + label + "".join(
            f'<span class="ops-chip">{escape(c)}</span>' for c in chips) + "</div>"
    stat_html = ""
    if stats:
        stat_html = '<div class="ops-stats">' + "".join(
            f'<div><div class="ops-kicker">{lbl}</div><div class="ops-stat-v" style="color:{color}">{val}</div>'
            f'<div class="ops-stat-s">{sub}</div></div>' for lbl, val, sub, color in stats) + "</div>"
    st.markdown(
        f'<div class="ops-dossier ops-cut"><div class="ops-kicker">{kicker}</div>'
        f'<div class="ops-team">{escape(title)}</div>{chip_html}{stat_html}</div>',
        unsafe_allow_html=True,
    )


def headline_card(ins, kicker: str = "#1 thing to know", sentence: str | None = None) -> None:
    """The single strongest tendency, big, with its evidence bar."""
    color = CATEGORY_COLORS.get(ins.category, ACCENT)
    side = _side_word(ins.side)
    lr = ins.league_rate
    peer = f'{getattr(ins, "peers", "others")} {lr:.0%}' if lr is not None else ""
    st.markdown(
        f'<div class="ops-hero ops-cut" style="border-left:3px solid {color}">'
        f'<div class="ops-kicker" style="color:{AMBER}">{kicker}</div>'
        f'<div class="ops-hero-text">{sentence or ins.text}</div>'
        f'<div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">'
        f'<span class="ops-hero-num" style="color:{color}">{pct(ins.k, ins.n):.0%}</span>'
        f'<span class="ops-sample">{ins.sample}</span>'
        f'<span class="ops-ctx" style="margin-left:auto">{peer}</span></div>'
        f'{evidence_bar(ins.k, ins.n, lr, color, getattr(ins, "peers", "typical"))}'
        f'<div class="ops-meta">{side_badge(side)}<span>{category_tag(ins.category)}</span>'
        f'<span>· {ins.map.title()}</span><span>· bar: shaded = 95% range, grey tick = comparison</span></div></div>',
        unsafe_allow_html=True,
    )


def insight_card(ins) -> None:
    """A ranked scouting insight: category, map/side, sentence, evidence bar, sample and league context."""
    color = CATEGORY_COLORS.get(ins.category, TEXT_DIM)
    side = _side_word(ins.side)
    lr = ins.league_rate
    league = f" · {getattr(ins, 'peers', 'others')} {lr:.0%}" if lr is not None else ""
    former = (f'<div class="ops-ctx" style="color:{AMBER}">⚠ Former player: {ins.departed}</div>'
              if getattr(ins, "departed", None) else "")
    st.markdown(
        f'<div class="ops-card ops-cut" style="border-left:3px solid {color}">'
        f'<div class="ops-title" style="display:flex;gap:6px;align-items:center">'
        f'<span style="color:{color}">{category_tag(ins.category)}</span>'
        f'<span>· {ins.map.title()}</span><span style="margin-left:auto">{side_badge(side)}</span></div>'
        f'<div style="color:{TEXT};margin:8px 0 4px 0;line-height:1.42;font-size:.93rem">{ins.text}</div>'
        f'{evidence_bar(ins.k, ins.n, lr, color, getattr(ins, "peers", "typical"))}'
        f'<div class="ops-ctx">{ins.sample}{league}</div>{former}</div>',
        unsafe_allow_html=True,
    )


def suggestion_card(s, number: int, self_scout: bool = False) -> None:
    """An anti-strat suggestion with the evidence it came from."""
    ins = s.evidence
    color = CATEGORY_COLORS.get(ins.category, TEXT_DIM)
    # Opponent mode: the side you play against it (their defense is your attack). Self-scout: the team's own side.
    badge = side_badge(_side_word(ins.side)) if self_scout else f"<span>you</span>{side_badge(s.phase)}"
    st.markdown(
        f'<div class="ops-plan ops-cut">'
        f'<div class="ops-plan-n" style="color:{color}">{number:02d}</div>'
        f'<div style="min-width:0"><div class="ops-plan-h">{s.headline}</div>'
        f'<div class="ops-plan-d">{s.detail}</div>'
        f'<div class="ops-meta">{badge}<span>{category_tag(ins.category)}</span>'
        f'<span>· {ins.map.title()}</span><span>· {ins.sample}</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def page_header(kicker: str, title: str, context: str) -> None:
    """Compact dossier strip for the profiler pages."""
    st.markdown(
        f'<div class="ops-dossier ops-cut" style="padding:14px 20px 12px">'
        f'<div class="ops-kicker">{kicker}</div>'
        f'<div class="ops-team" style="font-size:clamp(1.5rem,3vw,2.1rem);margin-bottom:4px">{escape(title)}</div>'
        f'<div class="ops-stat-s" style="font-size:.8rem;color:{TEXT_DIM}">{context}</div></div>',
        unsafe_allow_html=True,
    )


def map_key(items: list[str]) -> None:
    """One line above a map that says what every mark means and how much data is behind it."""
    st.markdown('<div class="ops-mapkey">' + "".join(f"<span>{i}</span>" for i in items) + "</div>",
                unsafe_allow_html=True)


def insight(text: str, color: str = ACCENT) -> None:
    st.markdown(f'<div class="ops-insight" style="border-left-color:{color}">{text}</div>', unsafe_allow_html=True)
