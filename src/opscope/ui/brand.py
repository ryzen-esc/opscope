"""OpScope brand: the reticle icon (assets/opscope-icon.svg) and the HTML wordmark that uses the app's fonts."""
from __future__ import annotations

from pathlib import Path

ICON = str(Path(__file__).resolve().parents[3] / "assets" / "opscope-icon.svg")
TAGLINE = "VALORANT scouting you can check."

WORDMARK_HTML = (
    '<div class="ops-wordmark"><span>OP</span><span class="ops-accent">SCOPE</span></div>'
    f'<div class="ops-tagline">{TAGLINE}</div>'
)
