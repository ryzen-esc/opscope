"""Scouting-report insights: short, ranked, evidence-backed tendencies for one team.

Every insight carries its sample ("k of n") and, where a fair comparison exists, the league rate for the
same map and side. Ranking favours findings that are both well-sampled and far from the league:

    surprise = gap between the team's 95% Wilson interval and the league rate (0 if they overlap)

Habits (repeat utility spots) have no league comparison; they rank by share and sample size.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

import numpy as np
import pandas as pd

from opscope.analytics.operator import Scope, _filter_rounds, team_rounds
from opscope.analytics.stats import MIN_SAMPLE, of, pct, wilson
from opscope.analytics.utility import UtilityScope, utility_report
from opscope.load import load
from opscope.zones import assign_site, plant_positions

SIDE_WORD = {"attacker": "attack", "defender": "defense"}
GUNS = {"operator": "Operator", "odin": "Odin"}


@dataclass
class Insight:
    category: str          # "Operator" | "Utility" | "Attack"
    map: str
    side: str
    text: str              # HTML, coach-facing sentence
    k: int
    n: int
    unit: str
    league: tuple[int, int] | None = None
    score: float = 0.0
    tags: dict = field(default_factory=dict)

    @property
    def sample(self) -> str:
        return of(self.k, self.n, self.unit)

    @property
    def league_rate(self) -> float | None:
        return pct(*self.league) if self.league and self.league[1] else None


def surprise(k: int, n: int, league_rate: float) -> float:
    """How far the team's 95% interval sits from the league rate (0 when they overlap)."""
    lo, hi = wilson(k, n)
    return max(0.0, lo - league_rate, league_rate - hi)


def pretty(ability_id: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in str(ability_id).split("-"))


@cache
def plant_sites() -> pd.DataFrame:
    """Every plant with its site name (from sites.yaml)."""
    parts = [g.assign(site=assign_site(m, g["x"], g["y"])) for m, g in plant_positions().groupby("map")]
    return pd.concat(parts, ignore_index=True)


# ---- generators ------------------------------------------------------------------------------

def gun_insights(s: Scope) -> list[Insight]:
    """Big-gun usage per map/side vs the league, and who carries it."""
    d = load()
    tr_all = team_rounds()
    league = _filter_rounds(tr_all, Scope(team_id="", side=None, maps=s.maps, patches=s.patches, events=s.events))
    team = _filter_rounds(tr_all, Scope(team_id=s.team_id, side=None, maps=s.maps, opponents=s.opponents,
                                        patches=s.patches, events=s.events))
    out = []
    for weapon, label in GUNS.items():
        lo = d.loadouts.loc[d.loadouts["primary_fe"] == weapon, ["game_id", "round_num", "team_id", "player_name", "agent"]]
        has = lo[["game_id", "round_num", "team_id"]].drop_duplicates().assign(has=True)

        def flag(df: pd.DataFrame) -> pd.DataFrame:
            df = df.merge(has, on=["game_id", "round_num", "team_id"], how="left")
            return df.assign(has=df["has"].fillna(False).astype(bool))

        t = flag(team)
        lg = flag(league[league["team_id"] != s.team_id])  # league = everyone else
        tg = t.groupby(["map", "side"])["has"].agg(["sum", "size"])
        lgg = lg.groupby(["map", "side"])["has"].agg(["sum", "size"])
        for (m, side), row in tg.iterrows():
            k, n = int(row["sum"]), int(row["size"])
            if n < 2 * MIN_SAMPLE or (m, side) not in lgg.index:
                continue
            lk, ln = (int(v) for v in lgg.loc[(m, side)])
            lr = pct(lk, ln)
            sc = surprise(k, n, lr)
            if sc <= 0:
                continue
            more = pct(k, n) > lr
            holders = (lo.merge(t[t["has"] & (t["map"] == m) & (t["side"] == side)][["game_id", "round_num", "team_id"]],
                                on=["game_id", "round_num", "team_id"]))
            who = ""
            if more and len(holders):
                top = holders.groupby(["player_name", "agent"]).size().sort_values(ascending=False)
                (pname, agent), cnt = top.index[0], int(top.iloc[0])
                who = f" Usually <b>{pname}</b> on {agent.title()} ({cnt} of {k})."
            verb = "often" if more else "rarely"
            out.append(Insight(
                category="Operator", map=m, side=side,
                text=f"{verb.capitalize()} buy the <b>{label}</b> on {SIDE_WORD[side]} on <b>{m.title()}</b>: "
                     f"<b>{of(k, n, SIDE_WORD[side] + ' rounds')}</b> (league {lr:.0%}).{who}",
                k=k, n=n, unit=f"{SIDE_WORD[side]} rounds", league=(lk, ln), score=sc + (0.05 if more else 0),
                tags={"weapon": weapon, "direction": "more" if more else "less"}))
    return out


def plant_insights(s: Scope) -> list[Insight]:
    """Which site a team plants on, per map, vs where the league plants."""
    tr_all = team_rounds()
    rounds_scope = _filter_rounds(tr_all, Scope(team_id=s.team_id, side="attacker", maps=s.maps,
                                                opponents=s.opponents, patches=s.patches, events=s.events))
    lg_scope = _filter_rounds(tr_all, Scope(team_id="", side="attacker", maps=s.maps, patches=s.patches, events=s.events))
    plants = plant_sites()
    keys = ["game_id", "round_num"]
    team = rounds_scope.merge(plants[keys + ["site"]], on=keys)
    league = lg_scope[lg_scope["team_id"] != s.team_id].merge(plants[keys + ["site"]], on=keys)
    out = []
    for m, g in team.groupby("map"):
        n = len(g)
        if n < MIN_SAMPLE or g["site"].isna().all():
            continue
        lgm = league[league["map"] == m]
        for site, k in g["site"].value_counts().items():
            lk, ln = int((lgm["site"] == site).sum()), len(lgm)
            if not ln:
                continue
            lr = pct(lk, ln)
            sc = surprise(int(k), n, lr)
            more = pct(int(k), n) > lr
            if sc <= 0 or not more:
                continue  # "plants B less" is just the mirror of "plants A more"
            out.append(Insight(
                category="Attack", map=m, side="attacker",
                text=f"On <b>{m.title()}</b> attack they plant <b>{site}</b> in <b>{of(int(k), n, 'planted rounds')}</b> "
                     f"(league {lr:.0%}).",
                k=int(k), n=n, unit="planted rounds", league=(lk, ln), score=sc,
                tags={"site": site, "direction": "more" if more else "less"}))
    return out


@cache
def league_habit_rates(map_name: str, side: str) -> dict[str, tuple[float, int]]:
    """For each ability on a map/side: the median 'same-spot share' across all players in the league.

    Some utility is *always* placed the same way (e.g. a Viper wall lineup), so a 70-of-71 habit is only
    worth a coach's time if it is more predictable than other players of that agent. Returns
    {ability: (median share, number of players)} over players with at least MIN_SAMPLE rounds on the agent.
    """
    from opscope.analytics.utility import repeat_spots
    d = load()
    tr = team_rounds()
    rounds = tr[(tr["map"] == map_name) & (tr["side"] == side)][["game_id", "round_num", "team_id"]]
    c = d.casts[(d.casts["map"] == map_name) & (d.casts["side"] == side) & d.casts["phase"].isin(["buy", "live"])]
    c = c.merge(rounds, on=["game_id", "round_num", "team_id"])
    lo = d.loadouts.merge(rounds, on=["game_id", "round_num", "team_id"])
    on_agent = lo.groupby(["player_id", "agent"]).size()
    shares: dict[str, list[float]] = {}
    for (pid, agent, ability), g in c.groupby(["player_id", "agent", "ability"]):
        n = int(on_agent.get((pid, agent), 0))
        if n < MIN_SAMPLE:
            continue
        spots = repeat_spots(g.reset_index(drop=True), max_spots=1)
        shares.setdefault(ability, []).append(spots[0]["rounds"] / n if spots else 0.0)
    return {a: (float(np.median(v)), len(v)) for a, v in shares.items()}


def habit_insights(s: Scope, min_share: float = 0.6) -> list[Insight]:
    """Utility a player puts in the same spot round after round, more predictably than the league."""
    out = []
    for side in ("defender", "attacker"):
        rep = utility_report(UtilityScope(team_id=s.team_id, side=side, maps=s.maps, opponents=s.opponents,
                                          patches=s.patches, events=s.events,
                                          classes=("trap", "recon", "smoke", "flash", "stall")))
        for m in rep.casts["map"].dropna().unique():
            h = rep.habits(m, max_per_ability=1)
            if h.empty:
                continue
            h = h[(h["rounds_on_agent"] >= MIN_SAMPLE) & (h["share"] >= min_share)]
            baseline = league_habit_rates(m, side) if not h.empty else {}
            for _, row in h.iterrows():
                k, n = int(row["rounds"]), int(row["rounds_on_agent"])
                lg_share, lg_players = baseline.get(row["ability"], (None, 0))
                if lg_share is None or lg_players < 3:
                    continue  # no fair comparison
                sc = surprise(k, n, lg_share)
                if sc <= 0 or k / n <= lg_share:
                    continue  # standard lineup, or less predictable than a typical player
                area = row.get("area")
                where = f" near <b>{area}</b>" if isinstance(area, str) else ""
                out.append(Insight(
                    category="Utility", map=m, side=side,
                    text=f"<b>{row['player_name']}</b> ({row['agent'].title()}) puts <b>{pretty(row['ability'])}</b> "
                         f"in the same spot{where} on {SIDE_WORD[side]} on <b>{m.title()}</b>: <b>{of(k, n, 'rounds on ' + row['agent'].title())}</b> "
                         f"(typical player: {lg_share:.0%} in their usual spot).",
                    k=k, n=n, unit=f"rounds on {row['agent'].title()}", score=sc,
                    tags={"player": row["player_name"], "ability": row["ability"], "x": row["x"], "y": row["y"],
                          "util_class": row["util_class"], "area": area if isinstance(area, str) else None}))
    return out


def team_insights(s: Scope, limit: int | None = None) -> list[Insight]:
    """All insights for a team, best first."""
    items = gun_insights(s) + plant_insights(s) + habit_insights(s)
    items.sort(key=lambda i: i.score, reverse=True)
    return items[:limit] if limit else items


def map_pool(s: Scope) -> pd.DataFrame:
    """Per map: games, wins, and round win rate by side, for the scope's team."""
    tr = _filter_rounds(team_rounds(), Scope(team_id=s.team_id, side=None, maps=s.maps, opponents=s.opponents,
                                             patches=s.patches, events=s.events))
    if tr.empty:
        return pd.DataFrame(columns=["map", "games", "wins", "atk_won", "atk_n", "def_won", "def_n"])
    g = load().games.set_index("game_id")
    games = tr.drop_duplicates("game_id")[["game_id", "map"]]
    games["won"] = games["game_id"].map(g["winner_team_id"]).eq(s.team_id)
    pool = games.groupby("map").agg(games=("game_id", "size"), wins=("won", "sum"))
    side = tr.groupby(["map", "side"])["won"].agg(["sum", "size"]).unstack("side")
    for sd, pre in (("attacker", "atk"), ("defender", "def")):
        pool[f"{pre}_won"] = side[("sum", sd)] if ("sum", sd) in side.columns else 0
        pool[f"{pre}_n"] = side[("size", sd)] if ("size", sd) in side.columns else 0
    return pool.fillna(0).astype(int).reset_index().sort_values("games", ascending=False)
