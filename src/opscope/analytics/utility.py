"""Utility profiler: where and when a team casts its abilities.

Positions are the caster's position at the moment of the cast (from the ability supplement when available).
GRID does not record where utility lands, so for thrown smokes/flashes the map shows the cast spot plus the
aim direction. For placed utility (trips, alarmbots, sensors, turrets) the caster stands next to where it goes,
so cast spots are a good proxy for placements.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from opscope.analytics.operator import Scope, _filter_rounds, team_rounds, time_bucket
from opscope.load import load
from opscope.zones import nearest_callout

SPOT_RADIUS_CM = 400  # casts within 4 m count as "the same spot"


@dataclass(frozen=True)
class UtilityScope(Scope):
    """Scope plus utility-specific filters. Empty tuples mean 'all'."""
    classes: tuple[str, ...] = ()
    abilities: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    phases: tuple[str, ...] = ()  # "buy" (pre-round setup) and/or "live"


def repeat_spots(df: pd.DataFrame, radius: float = SPOT_RADIUS_CM, max_spots: int = 3,
                 min_rounds: int = 2) -> list[dict]:
    """Greedy clustering of cast positions into habitual spots.

    Repeatedly takes the cast with the most neighbours within `radius`, makes that neighbourhood a spot,
    removes it, and continues. A spot counts *rounds*, not casts, so double casts in one round count once.
    """
    if df.empty:
        return []
    pts = df[["x", "y"]].to_numpy(float)
    rounds = list(zip(df["game_id"], df["round_num"]))
    left = np.ones(len(df), dtype=bool)
    spots = []
    while left.sum() and len(spots) < max_spots:
        idx = np.flatnonzero(left)
        p = pts[idx]
        dist = np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1])
        near = dist < radius
        centre = near.sum(1).argmax()
        members = idx[near[centre]]
        n_rounds = len({rounds[i] for i in members})
        if n_rounds < min_rounds:
            break
        cx, cy = pts[members].mean(0)
        spots.append({"x": float(cx), "y": float(cy), "rounds": n_rounds, "casts": len(members),
                      "members": members.tolist()})
        left[members] = False
    return spots


@dataclass
class UtilityReport:
    scope: UtilityScope
    rounds: pd.DataFrame   # team rounds in scope
    casts: pd.DataFrame    # the team's casts in those rounds, after utility filters
    agent_rounds: pd.DataFrame  # rounds each player spent on each agent (denominators)

    @property
    def n_rounds(self) -> int:
        return len(self.rounds)

    def ability_table(self) -> pd.DataFrame:
        """Per player + ability: casts, rounds used, rounds on that agent, casts per round on agent."""
        c = self.casts
        if c.empty:
            return pd.DataFrame(columns=["player_name", "agent", "ability", "util_class", "casts",
                                         "rounds_used", "rounds_on_agent", "per_round"])
        t = (c.groupby(["player_id", "player_name", "agent", "ability", "util_class"], observed=True)
             .agg(casts=("event_id", "size"),
                  rounds_used=("round_key", "nunique"))
             .reset_index())
        t = t.merge(self.agent_rounds, on=["player_id", "agent"], how="left")
        t["rounds_on_agent"] = t["rounds_on_agent"].fillna(t["rounds_used"]).astype(int)
        t["per_round"] = t["casts"] / t["rounds_on_agent"]
        return t.sort_values(["util_class", "casts"], ascending=[True, False]).drop(columns="player_id")

    def timing(self) -> pd.DataFrame:
        """Casts per time window and utility class (buy phase shown as its own window)."""
        c = self.casts
        if c.empty:
            return pd.DataFrame(columns=["window", "util_class", "casts"])
        window = np.where(c["phase"] == "buy", "buy phase", time_bucket(c["t"]).astype(str))
        t = c.assign(window=window).groupby(["window", "util_class"], observed=True).size().reset_index(name="casts")
        order = ["buy phase", "0–20s", "20–40s", "40–60s", "60s+"]
        t["window"] = pd.Categorical(t["window"], categories=order, ordered=True)
        return t.sort_values("window")

    def habits(self, map_name: str, max_per_ability: int = 2) -> pd.DataFrame:
        """Habitual spots per (player, ability) on one map, with 'k of n rounds on that agent'."""
        c = self.casts[self.casts["map"] == map_name]
        rows = []
        ar = self.agent_rounds_by_map(map_name)
        for (pid, name, agent, ability, cls), g in c.groupby(
                ["player_id", "player_name", "agent", "ability", "util_class"], observed=True):
            denom = int(ar.get((pid, agent), g["round_key"].nunique()))
            for rank, s in enumerate(repeat_spots(g.reset_index(drop=True), max_spots=max_per_ability), 1):
                rows.append({"player_id": pid, "player_name": name, "agent": agent, "ability": ability,
                             "util_class": cls, "spot": rank, "x": s["x"], "y": s["y"],
                             "rounds": s["rounds"], "rounds_on_agent": denom,
                             "share": s["rounds"] / denom if denom else 0.0})
        out = pd.DataFrame(rows)
        if out.empty:
            return out
        out["area"] = nearest_callout(map_name, out["x"], out["y"])
        return out.sort_values("rounds", ascending=False).reset_index(drop=True)

    def agent_rounds_by_map(self, map_name: str) -> dict:
        r = self.rounds[self.rounds["map"] == map_name]
        lo = _agent_loadouts(r, self.scope.team_id)
        return lo.groupby(["player_id", "agent"]).size().to_dict()


def _agent_loadouts(rounds: pd.DataFrame, team_id: str) -> pd.DataFrame:
    lo = load().loadouts
    lo = lo[lo["team_id"] == team_id]
    return lo.merge(rounds[["game_id", "round_num"]], on=["game_id", "round_num"], how="inner")


def utility_report(s: UtilityScope) -> UtilityReport:
    if not s.team_id:
        raise ValueError("utility_report needs a team_id")
    d = load()
    tr = _filter_rounds(team_rounds(), s)
    keys = tr[["game_id", "round_num", "won", "buy"]]
    c = d.casts[(d.casts["team_id"] == s.team_id) & d.casts["phase"].isin(["buy", "live"])]
    c = c.merge(keys, on=["game_id", "round_num"], how="inner")
    if s.classes:
        c = c[c["util_class"].isin(s.classes)]
    if s.abilities:
        c = c[c["ability"].isin(s.abilities)]
    if s.agents:
        c = c[c["agent"].isin(s.agents)]
    if s.players:
        c = c[c["player_id"].isin(s.players)]
    if s.phases:
        c = c[c["phase"].isin(s.phases)]
    names = d.loadouts.drop_duplicates("player_id").set_index("player_id")["player_name"]
    c = c.assign(player_name=c["player_id"].map(names).astype("string"),
                 round_key=c["game_id"] + ":" + c["round_num"].astype(str),
                 bucket=time_bucket(c["t"]))
    lo = _agent_loadouts(tr, s.team_id)
    agent_rounds = lo.groupby(["player_id", "agent"]).size().reset_index(name="rounds_on_agent")
    return UtilityReport(scope=s, rounds=tr, casts=c.reset_index(drop=True), agent_rounds=agent_rounds)
