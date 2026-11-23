"""Sidebar filters shared by every page. Values live in st.session_state so they persist across pages."""
from __future__ import annotations

from functools import cache

import pandas as pd
import streamlit as st

from opscope.analytics.operator import team_rounds
from opscope.load import CLOUD9_TEAMS, load

SIDES = {"Defense": "defender", "Attack": "attacker", "Both": None}


@cache
def team_labels() -> dict[str, str]:
    """team_id -> label, Cloud9 eras first, then every other team by name."""
    d = load()
    names = d.teams.set_index("team_id")["name"].to_dict()
    ids = set(d.games["team1_id"]) | set(d.games["team2_id"])
    others = sorted((i for i in ids if i not in CLOUD9_TEAMS), key=lambda i: str(names.get(i, i)).lower())
    return {**CLOUD9_TEAMS, **{i: str(names.get(i, i)) for i in others}}


def team_name(team_id: str) -> str:
    return team_labels().get(team_id, team_id)


def sidebar() -> dict:
    labels = team_labels()
    st.sidebar.markdown("### Scout")
    team_id = st.sidebar.selectbox("Team", list(labels), format_func=labels.get, key="team_id")

    tr = team_rounds()
    mine = tr[tr["team_id"] == team_id]
    map_counts = mine.drop_duplicates(["game_id"])["map"].value_counts()
    map_opts = ["All maps"] + list(map_counts.index)
    map_choice = st.sidebar.selectbox(
        "Map", map_opts, key="map",
        format_func=lambda m: m if m == "All maps" else f"{m.title()} ({map_counts[m]} games)")
    side_label = st.sidebar.segmented_control("Side", list(SIDES), default="Defense", key="side") or "Both"

    opp_ids = mine["opp_id"].value_counts()
    opponents = st.sidebar.multiselect("Opponents", list(opp_ids.index), key="opponents",
                                       format_func=lambda i: f"{team_name(i)} ({opp_ids[i]} rds)")
    with st.sidebar.expander("More filters"):
        patches = st.multiselect("Patch", sorted(mine["patch"].dropna().unique()), key="patches")
        events = st.multiselect("Event", sorted(mine["event"].dropna().unique()), key="events")

    st.sidebar.caption(f"{mine['game_id'].nunique()} maps · {mine['series_id'].nunique()} series in the data")
    return {
        "team_id": team_id,
        "maps": () if map_choice == "All maps" else (map_choice,),
        "side": SIDES[side_label],
        "side_label": side_label,
        "opponents": tuple(opponents),
        "patches": tuple(patches),
        "events": tuple(events),
    }
