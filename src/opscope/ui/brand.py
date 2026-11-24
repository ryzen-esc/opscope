"""OpScope brand: the reticle icon (assets/opscope-icon.svg) and the HTML wordmark that uses the app's fonts."""
from __future__ import annotations

from pathlib import Path

ICON = str(Path(__file__).resolve().parents[3] / "assets" / "opscope-icon.svg")
TAGLINE = "VALORANT scouting you can check."

WORDMARK_HTML = (
    '<div class="ops-wordmark"><span>OP</span><span class="ops-accent">SCOPE</span></div>'
    f'<div class="ops-tagline">{TAGLINE}</div>'
)

# Shown while the dataset loads (first visit only): an animated reticle and a scanning bar.
SPLASH_HTML = """
<div class="ops-splash">
  <svg viewBox="0 0 32 32" width="72" height="72" class="ops-splash-reticle" aria-hidden="true">
    <circle cx="16" cy="16" r="10.5" fill="none" stroke="#00AEEF" stroke-width="1.6"/>
    <path d="M16 1.5v8M16 22.5v8M1.5 16h8M22.5 16h8" stroke="#00AEEF" stroke-width="1.6"/>
    <circle cx="16" cy="16" r="1.8" fill="#00AEEF"/>
  </svg>
  <div class="ops-wordmark" style="font-size:2rem;margin-top:18px">OP<span class="ops-accent">SCOPE</span></div>
  <div class="ops-tagline" style="font-size:.9rem">""" + TAGLINE + """</div>
  <div class="ops-splash-bar"><div></div></div>
  <div class="ops-kicker" style="margin-top:10px">Reading 2,000+ pro maps of GRID match data</div>
</div>
"""
