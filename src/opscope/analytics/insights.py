"""Scouting-report insights: short, ranked, evidence-backed tendencies for one team.

Every insight carries its sample ("k of n") and, where a fair comparison exists, the league rate for the
same map and side. Ranking favours findings that are both well-sampled and far from the league:

    surprise = gap between the team's 95% Wilson interval and the league rate (0 if they overlap)

Habits (repeat utility spots) have no league comparison; they rank by share and sample size.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache

import numpy as np
import pandas as pd

from opscope.analytics.operator import (SETUP_WINDOW, Scope, _filter_rounds, league_scope, positions,
                                       season_weighted_rate, team_rounds)
from opscope.analytics.stats import MIN_SAMPLE, of, pct, wilson
from opscope.analytics.utility import UtilityScope, utility_report
from opscope.ingest.build import cache_dir
from opscope.analytics.roster import last_event_with, latest_roster, short_event
from opscope.load import load, peer_group
from opscope.zones import assign_site, nearest_callout, plant_positions

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
    departed: str | None = None  # set when the insight's player isn't on the team's latest roster
    peers: str = "other teams"   # who the league rate comes from, e.g. "typical VCT 2025 team"
    baseline: float | None = None  # the comparison rate actually used (typical team), if not the pooled one

    @property
    def sample(self) -> str:
        return of(self.k, self.n, self.unit)

    @property
    def league_rate(self) -> float | None:
        if self.baseline is not None:
            return self.baseline
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

def early_area(holders: pd.DataFrame, map_name: str, window: float = SETUP_WINDOW) -> tuple[str | None, int, int]:
    """Most common named area for the gun holder in the first `window` seconds: (area, rounds there, rounds seen)."""
    keys = ["game_id", "round_num", "player_id"]
    pos = positions()
    early = holders[keys].merge(pos[(pos["t"] <= window)], on=keys)
    if early.empty:
        return None, 0, 0
    early = early.assign(area=nearest_callout(map_name, early["x"], early["y"])).dropna(subset=["area"])
    seen = early[["game_id", "round_num"]].drop_duplicates().shape[0]
    if not seen:
        return None, 0, 0
    counts = early.drop_duplicates(["game_id", "round_num", "area"])["area"].value_counts()
    if counts.iloc[0] < 3:
        return None, 0, seen  # too thin to name a spot
    return str(counts.index[0]), int(counts.iloc[0]), seen


def gun_insights(s: Scope) -> list[Insight]:
    """Big-gun usage per map/side vs the typical other team in the same tier and season, and who carries it."""
    d = load()
    tr_all = team_rounds()
    team = _filter_rounds(tr_all, Scope(team_id=s.team_id, side=None, maps=s.maps, opponents=s.opponents,
                                        patches=s.patches, events=s.events))
    lg_s = league_scope(s, team, side=None)
    league = _filter_rounds(tr_all, lg_s)
    who_lg = peer_group(lg_s.cohorts)
    out = []
    for weapon, label in GUNS.items():
        lo = d.loadouts.loc[d.loadouts["primary_fe"] == weapon,
                            ["game_id", "round_num", "team_id", "player_id", "player_name", "agent"]]
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
            lr, method = season_weighted_rate(t[(t["map"] == m) & (t["side"] == side)],
                                              lg[(lg["map"] == m) & (lg["side"] == side)], "has")
            peer = f"typical {who_lg} team" if method == "typical team" else f"all other {who_lg} rounds"
            sc = surprise(k, n, lr)
            if sc <= 0:
                continue
            more = pct(k, n) > lr
            holders = (lo.merge(t[t["has"] & (t["map"] == m) & (t["side"] == side)][["game_id", "round_num", "team_id"]],
                                on=["game_id", "round_num", "team_id"]))
            who, tags = "", {"weapon": weapon, "label": label, "direction": "more" if more else "less"}
            if more and len(holders):
                top = holders.groupby(["player_id", "player_name", "agent"]).size().sort_values(ascending=False)
                (pid, pname, agent), cnt = top.index[0], int(top.iloc[0])
                who = f" Usually <b>{pname}</b> on {agent.title()} ({cnt} of {k})."
                tags.update(player=pname, player_id=str(pid), agent=agent)
                area, ak, an = early_area(holders, m)
                if area:
                    who += f" Early in the round it's most often seen near <b>{area}</b> ({of(ak, an, 'rounds seen')})."
                    tags.update(area=area, area_k=ak, area_n=an)
            verb = "often" if more else "rarely"
            out.append(Insight(
                category="Operator", map=m, side=side,
                text=f"{verb.capitalize()} buy the <b>{label}</b> on {SIDE_WORD[side]} on <b>{m.title()}</b>: "
                     f"<b>{of(k, n, SIDE_WORD[side] + ' rounds')}</b> ({peer}: {lr:.0%}).{who}",
                k=k, n=n, unit=f"{SIDE_WORD[side]} rounds", league=(lk, ln), score=sc + (0.05 if more else 0),
                peers=peer, baseline=lr,
                tags=tags))
    return out


def plant_insights(s: Scope) -> list[Insight]:
    """Which site a team plants on, per map, vs where the league plants."""
    tr_all = team_rounds()
    rounds_scope = _filter_rounds(tr_all, Scope(team_id=s.team_id, side="attacker", maps=s.maps,
                                                opponents=s.opponents, patches=s.patches, events=s.events))
    lg_s = league_scope(s, rounds_scope, side="attacker")
    lg_scope = _filter_rounds(tr_all, lg_s)
    who_lg = peer_group(lg_s.cohorts)
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
            lr, method = season_weighted_rate(g, lgm.assign(hit=lgm["site"] == site), "hit", min_rounds=MIN_SAMPLE)
            peer = f"typical {who_lg} team" if method == "typical team" else f"all other {who_lg} plants"
            sc = surprise(int(k), n, lr)
            more = pct(int(k), n) > lr
            if sc <= 0 or not more:
                continue  # "plants B less" is just the mirror of "plants A more"
            out.append(Insight(
                category="Attack", map=m, side="attacker",
                text=f"On <b>{m.title()}</b> attack they plant <b>{site}</b> in <b>{of(int(k), n, 'planted rounds')}</b> "
                     f"({peer}: {lr:.0%}).",
                k=int(k), n=n, unit="planted rounds", league=(lk, ln), score=sc, peers=peer, baseline=lr,
                tags={"site": site, "direction": "more" if more else "less"}))
    return out


def _habit_shares_path(map_name: str, side: str, cohort: str):
    from opscope.analytics.utility import SPOT_RADIUS_CM
    return cache_dir() / "baselines" / f"habit_shares_{map_name}_{side}_{cohort}_r{SPOT_RADIUS_CM}_n{MIN_SAMPLE}.json"


@cache
def player_habit_shares(map_name: str, side: str, cohort: str,
                        patches: tuple[str, ...] = (), events: tuple[str, ...] = ()) -> pd.DataFrame:
    """Every player's 'same-spot share' per ability on one map/side in one season (cohort).

    One row per (ability, player): `share` = rounds in their most-used spot / rounds on that agent. Players need
    MIN_SAMPLE rounds on the agent. Slow (it clusters every player's casts), so the unfiltered version is saved
    under the gitignored cache folder; patch/event-filtered versions are computed on demand and kept in memory.
    """
    path = _habit_shares_path(map_name, side, cohort)
    if not patches and not events and path.exists():
        return pd.DataFrame(json.loads(path.read_text()), columns=["ability", "player_id", "team_id", "share"])
    df = _compute_habit_shares(map_name, side, cohort, patches, events)
    if not patches and not events:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(df.values.tolist()))
    return df


def _compute_habit_shares(map_name: str, side: str, cohort: str, patches=(), events=()) -> pd.DataFrame:
    from opscope.analytics.utility import repeat_spots
    d = load()
    tr = team_rounds()
    sel = (tr["map"] == map_name) & (tr["side"] == side) & (tr["cohort"] == cohort)
    if patches:
        sel &= tr["patch"].isin(patches)
    if events:
        sel &= tr["event"].isin(events)
    rounds = tr[sel][["game_id", "round_num", "team_id"]]
    c = d.casts[(d.casts["map"] == map_name) & (d.casts["side"] == side) & d.casts["phase"].isin(["buy", "live"])]
    c = c.merge(rounds, on=["game_id", "round_num", "team_id"])
    lo = d.loadouts.merge(rounds, on=["game_id", "round_num", "team_id"])
    on_agent = lo.groupby(["player_id", "agent"]).size()
    team_of = lo.drop_duplicates("player_id").set_index("player_id")["team_id"]
    rows = []
    for (pid, agent, ability), g in c.groupby(["player_id", "agent", "ability"]):
        n = int(on_agent.get((pid, agent), 0))
        if n < MIN_SAMPLE:
            continue
        spots = repeat_spots(g.reset_index(drop=True), max_spots=1)
        rows.append([str(ability), str(pid), str(team_of.get(pid, "")), spots[0]["rounds"] / n if spots else 0.0])
    return pd.DataFrame(rows, columns=["ability", "player_id", "team_id", "share"])


def league_habit_rate(map_name: str, side: str, ability: str, team_weights: dict[str, int], exclude_team: str,
                      patches: tuple[str, ...] = (), events: tuple[str, ...] = ()) -> tuple[float | None, int]:
    """The typical *other* player's same-spot share for an ability, season-matched.

    Per season the team played (weighted by its rounds there): the median share of players on other teams
    (at least 3 of them). Returns (share, players compared) or (None, 0) when no fair comparison exists.
    """
    acc = total = 0.0
    players = 0
    for cohort, w in team_weights.items():
        shares = player_habit_shares(map_name, side, cohort, patches, events)
        others = shares[(shares["ability"] == ability) & (shares["team_id"] != exclude_team)]["share"]
        if len(others) < 3:
            continue
        acc += w * float(np.median(others))
        total += w
        players += len(others)
    return (acc / total, players) if total else (None, 0)


def habit_insights(s: Scope, min_share: float = 0.6) -> list[Insight]:
    """Utility a player puts in the same spot round after round, more predictably than the league."""
    out = []
    for side in ("defender", "attacker"):
        rep = utility_report(UtilityScope(team_id=s.team_id, side=side, maps=s.maps, opponents=s.opponents,
                                          patches=s.patches, events=s.events,
                                          classes=("trap", "recon", "smoke", "flash", "stall")))
        who_lg = peer_group(rep.rounds["cohort"].dropna().unique())
        for m in rep.casts["map"].dropna().unique():
            h = rep.habits(m, max_per_ability=1)
            if h.empty:
                continue
            h = h[(h["rounds_on_agent"] >= MIN_SAMPLE) & (h["share"] >= min_share)]
            weights = rep.rounds[rep.rounds["map"] == m]["cohort"].value_counts().to_dict()
            for _, row in h.iterrows():
                k, n = int(row["rounds"]), int(row["rounds_on_agent"])
                lg_share, lg_players = league_habit_rate(m, side, row["ability"], weights, s.team_id,
                                                         s.patches, s.events)
                if lg_share is None:
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
                         f"(typical {who_lg} player: {lg_share:.0%} in their usual spot).",
                    k=k, n=n, unit=f"rounds on {row['agent'].title()}", score=sc,
                    peers=f"typical {who_lg} player", baseline=lg_share,
                    tags={"player": row["player_name"], "player_id": str(row["player_id"]),
                          "ability": row["ability"], "x": row["x"], "y": row["y"],
                          "util_class": row["util_class"], "area": area if isinstance(area, str) else None}))
    return out


def mark_departed(items: list[Insight], team_id: str) -> None:
    """Flag insights about players who aren't on the team's latest roster in the data (kept, not hidden)."""
    latest = latest_roster(team_id)
    if latest is None:
        return
    for ins in items:
        pid = ins.tags.get("player_id")
        if pid and pid not in latest.player_ids:
            last = last_event_with(team_id, pid)
            ins.departed = f"not on the roster after {short_event(last)}" if last else "not on the latest roster"


def team_insights(s: Scope, limit: int | None = None) -> list[Insight]:
    """All insights for a team, best first."""
    items = gun_insights(s) + plant_insights(s) + habit_insights(s)
    mark_departed(items, s.team_id)
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


def warm() -> None:
    """Precompute the league habit baselines for every map and side (about a minute; saved to cache/)."""
    import time
    started = time.time()
    g = load().games
    maps = sorted(g["map"].dropna().unique())
    for cohort in sorted(g["cohort"].dropna().unique()):
        for m in sorted(g.loc[g["cohort"] == cohort, "map"].dropna().unique()):
            for side in ("defender", "attacker"):
                player_habit_shares(m, side, cohort)
    from opscope.analytics.landing import landing_model
    landing_model()
    print(f"Baselines ready for {len(maps)} maps in {time.time() - started:.0f}s")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Scouting insights")
    ap.add_argument("--warm", action="store_true", help="precompute league baselines so reports load fast")
    if ap.parse_args().warm:
        warm()
