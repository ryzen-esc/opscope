"""'View the evidence' links under report cards: open the right profiler with its filters already set.

Streamlit can't switch pages from inside a button callback, so the callback sets the target page's widget
state plus a pending page, and the report calls follow_link() at the top of its next run.
"""
from __future__ import annotations

import streamlit as st

_GOTO = "_ops_goto"
SIDE_LABELS = {"defender": "Defense", "attacker": "Attack"}
UTIL_CLASS_LABELS = {"trap": "Traps & setups", "recon": "Recon", "smoke": "Smokes", "stall": "Stalls",
                     "flash": "Flashes"}


def follow_link() -> None:
    """Call at the top of the report: performs a page switch requested by an evidence link."""
    target = st.session_state.pop(_GOTO, None)
    if target:
        st.switch_page(target)


def _open(ins, report_map_key: str) -> None:
    tags, side = ins.tags, SIDE_LABELS.get(ins.side)
    if ins.category == "Operator":
        st.session_state.update(side=side, weapon=tags.get("label", "Operator"), op_map=ins.map)
        st.session_state[_GOTO] = "views/operator.py"
    elif ins.category == "Utility":
        st.session_state.update(side=side, util_class=UTIL_CLASS_LABELS.get(tags.get("util_class"), "All"),
                                util_phase="Both", util_map=ins.map)
        st.session_state[_GOTO] = "views/utility.py"
    else:  # plant site: stay on the report, show that map in the breakdown
        st.session_state[report_map_key] = ins.map
        st.toast(f"The Map breakdown tab (under Details) now shows {ins.map.title()}.")


def link_label(ins) -> str:
    m = ins.map.title()
    if ins.category == "Operator":
        return f"View the {ins.tags.get('label', 'Operator')} on the {m} map"
    if ins.category == "Utility":
        ability = " ".join(w[:1].upper() + w[1:] for w in str(ins.tags.get("ability", "utility")).split("-"))
        return f"View the {ability} spot on {m}"
    return f"Show {m} in the map breakdown"


def evidence_link(ins, key: str, report_map_key: str) -> None:
    """A small link button under a card."""
    st.button(link_label(ins), key=key, type="tertiary", icon=":material/arrow_forward:", icon_position="right",
              on_click=_open, args=(ins, report_map_key))
