"""Who was on a team, and when, according to the match data.

A team's roster for an event = the players who played at least ROSTER_SHARE of the team's rounds in that event
(so a one-map substitute doesn't count). The "latest roster" is the roster of the team's most recent event in
the data. It is *as of that last match*, not today: the data can't know about later changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import pandas as pd

from opscope.load import load

ROSTER_SHARE = 0.2


@dataclass(frozen=True)
class Roster:
    event: str
    last_match: str             # YYYY-MM-DD of the team's last map in that event
    player_ids: frozenset[str]
    names: tuple[str, ...]


@cache
def team_rosters(team_id: str) -> list[Roster]:
    """One roster per event the team played, oldest first."""
    lo = load().loadouts
    lo = lo[lo["team_id"] == team_id]
    if lo.empty:
        return []
    out = []
    order = lo.groupby("event")["started_at"].max().sort_values()
    for event, last in order.items():
        ev = lo[lo["event"] == event]
        rounds = ev[["game_id", "round_num"]].drop_duplicates().shape[0]
        per_player = ev.groupby(["player_id", "player_name"]).size()
        regulars = per_player[per_player >= ROSTER_SHARE * rounds]
        out.append(Roster(event=str(event), last_match=str(last)[:10],
                          player_ids=frozenset(str(p) for p, _ in regulars.index),
                          names=tuple(sorted(str(n) for _, n in regulars.index))))
    return out


def latest_roster(team_id: str) -> Roster | None:
    rosters = team_rosters(team_id)
    return rosters[-1] if rosters else None


def last_event_with(team_id: str, player_id: str) -> str | None:
    """The last event in which this player was a regular for this team."""
    for r in reversed(team_rosters(team_id)):
        if player_id in r.player_ids:
            return r.event
    return None


def lineups_in(team_id: str, events) -> int:
    """How many different lineups the team used across these events."""
    events = set(events)
    return len({r.player_ids for r in team_rosters(team_id) if r.event in events})


def short_event(event: str) -> str:
    """'VCT Americas - Stage 1 2025' -> 'Stage 1 2025'."""
    return event.split(" - ", 1)[-1]
