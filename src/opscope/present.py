"""What each page shows, as plain JSON-ready dicts (no UI code). The web front end draws these; the API serves them.

Rules carried over from the Streamlit pages, so the numbers and wording stay the same:
- every finding carries its sample (k of n), its 95% range and the typical-team rate it is compared with;
- positions, kills, casts and habit spots are given in the map frame (`geometry.to_view`), with time `t` (seconds
  after the buy phase; negative = before it) and a round index, so the front end can scrub through a round;
- labels for categories match the old pages: Gun choice / Utility habit / Plant site.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from functools import cache, lru_cache

import numpy as np
import pandas as pd

from opscope.analytics.antistrat import game_plan
from opscope.analytics.insights import Insight, map_pool, plant_sites, pretty, team_insights
from opscope.analytics.landing import add_landings, landing_model
from opscope.analytics.operator import (SETUP_WINDOW, Scope, _filter_rounds, league_scope, operator_report,
                                       season_weighted_rate, team_rounds)
from opscope.analytics.roster import latest_roster, lineups_in, short_event
from opscope.analytics.stats import MIN_SAMPLE, of, pct, wilson
from opscope.analytics.utility import SPOT_RADIUS_CM, UtilityScope, utility_report
from opscope.geometry import map_geometry, to_view
from opscope.load import CLOUD9_TEAMS, cohort_label, load, peer_group
from opscope.zones import nearest_callout, sites

CATEGORY_LABELS = {"Operator": "Gun choice", "Utility": "Utility habit", "Attack": "Plant site"}
SIDE_WORD = {"attacker": "attack", "defender": "defense"}
# One-click teams for a first look: Cloud9 (self-scout) and its main VCT Americas 2025 rivals. IDs, not names.
QUICK_PICKS = {"79": "Cloud9 · self-scout", "97": "NRG", "1079": "Sentinels", "96": "G2 Esports", "3429": "Cloud9 GC"}
WEAPONS = {"operator": "Operator", "odin": "Odin", "outlaw": "Outlaw", "marshal": "Marshal"}
UTIL_CLASSES = {"trap": "Traps & setups", "recon": "Recon", "smoke": "Smokes", "stall": "Stalls", "flash": "Flashes"}
HABIT_MIN_SHARE = 0.4  # a placement counts as a habit spot on the Utility page at 40%+ of rounds on the agent
AIM_CM = 900           # length of an aim-direction line, in game units


# ---- helpers ---------------------------------------------------------------------------------------

def _r(v, nd: int = 1):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), nd)


def _view(map_name: str, x, y) -> tuple[np.ndarray, np.ndarray]:
    u, v = to_view(map_name, np.asarray(x, float), np.asarray(y, float))
    return np.round(u, 1), np.round(v, 1)


def plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


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


def insight_json(i: Insight) -> dict:
    lo, hi = wilson(i.k, i.n)
    tags = {k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v)) for k, v in i.tags.items()}
    at = None
    if "x" in tags and "y" in tags:
        u, v = _view(i.map, [tags.pop("x")], [tags.pop("y")])
        at = [float(u[0]), float(v[0])]
    return {"category": i.category, "label": CATEGORY_LABELS.get(i.category, i.category), "map": i.map,
            "side": i.side, "text": i.text, "k": i.k, "n": i.n, "unit": i.unit, "sample": i.sample,
            "rate": _r(pct(i.k, i.n), 4), "lo": _r(lo, 4), "hi": _r(hi, 4), "base": _r(i.league_rate, 4),
            "peers": i.peers, "departed": i.departed, "at": at, "tags": tags}


# ---- meta: teams, filters, data summary --------------------------------------------------------------

def meta() -> dict:
    from opscope.ingest.build import cache_dir
    d = load()
    started = d.games["started_at"].dropna().str[:10]
    rep_path = cache_dir() / "ingest_report.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    rows, totals = rep.get("table_rows", {}), rep.get("totals", {})
    labels = team_labels()
    val = landing_model()["validation"]
    return {
        "teams": [{"id": k, "name": v, "self_scout": k in CLOUD9_TEAMS} for k, v in labels.items()],
        "quick_picks": [{"id": k, "label": v} for k, v in QUICK_PICKS.items() if k in labels],
        "summary": {"series": int(d.games["series_id"].nunique()), "maps": len(d.games),
                    "rounds": int(d.rounds["played"].sum()), "first": started.min(), "last": started.max()},
        "pipeline": {"series": rep.get("built_series", 0), "events": totals.get("events", 0),
                     "rollbacks": totals.get("rollback_applied", 0),
                     "cancelled_maps": totals.get("rolled_back_games", 0), "rounds": rows.get("rounds", 0),
                     "maps": rows.get("games", 0), "casts": rows.get("casts", 0),
                     "precise_share": _r(totals.get("casts_supplemented", 0) / max(rows.get("casts", 1), 1), 4)},
        "rules": {"min_sample": MIN_SAMPLE, "spot_radius_m": SPOT_RADIUS_CM // 100, "habit_min_share": HABIT_MIN_SHARE,
                  "setup_window_s": SETUP_WINDOW},
        "landing": {"median_model_m": val.get("median_model_m"), "median_cast_m": val.get("median_cast_m"),
                    "test_series": val.get("test_series")},
        "weapons": WEAPONS, "util_classes": UTIL_CLASSES, "categories": CATEGORY_LABELS,
    }


def team_filters(team_id: str) -> dict:
    """Options for the filter bar: maps played, opponents, patches and events (with counts)."""
    tr = team_rounds()
    mine = tr[tr["team_id"] == team_id]
    map_counts = mine.drop_duplicates(["game_id"])["map"].value_counts()
    opp = mine["opp_id"].value_counts()
    return {"team": team_id, "name": team_name(team_id), "self_scout": team_id in CLOUD9_TEAMS,
            "maps": [{"map": m, "games": int(n)} for m, n in map_counts.items()],
            "opponents": [{"id": i, "name": team_name(i), "rounds": int(n)} for i, n in opp.items()],
            "patches": sorted(mine["patch"].dropna().unique().tolist()),
            "events": sorted(mine["event"].dropna().unique().tolist()),
            "games": int(mine["game_id"].nunique()), "series": int(mine["series_id"].nunique())}


def geometry(map_name: str) -> dict:
    return map_geometry(map_name)


# ---- scouting report ----------------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _insights(scope: Scope) -> list[Insight]:
    return team_insights(scope)


def _plants(team_id: str, map_name: str, f: Scope, items: list[Insight]) -> dict:
    """Where the team plants on one map, per site, vs other teams in its tier and season."""
    tr = _filter_rounds(team_rounds(), Scope(team_id=team_id, side="attacker", maps=(map_name,),
                                             opponents=f.opponents, patches=f.patches, events=f.events))
    lg_s = league_scope(Scope(team_id=team_id, side="attacker", maps=(map_name,), patches=f.patches,
                              events=f.events), tr)
    lg = _filter_rounds(team_rounds(), lg_s)
    keys = ["game_id", "round_num"]
    pl = plant_sites()[keys + ["site"]]
    team_pl = tr.merge(pl, on=keys)
    lg_pl = lg[lg["team_id"] != team_id].merge(pl, on=keys)
    rows, peers = [], set()
    for s in sites().get(map_name, []):
        k, n = int((team_pl["site"] == s["name"]).sum()), len(team_pl)
        lo, hi = wilson(k, n)
        # Same comparison as the plant-site tendencies: the typical other team in the same tier and season.
        base, method = (season_weighted_rate(team_pl, lg_pl.assign(hit=lg_pl["site"] == s["name"]), "hit",
                                             min_rounds=MIN_SAMPLE) if n and len(lg_pl) else (None, None))
        if method:
            peers.add(f"typical {cohort_label(lg_s.cohorts)} team" if method == "typical team"
                      else f"all other {cohort_label(lg_s.cohorts)} plants")
        rows.append({"site": s["name"], "k": k, "n": n, "rate": _r(pct(k, n), 4), "lo": _r(lo, 4), "hi": _r(hi, 4),
                     "base": _r(base, 4)})
    return {"map": map_name, "attack_rounds": len(tr), "planted": len(team_pl), "sites": rows,
            "peers": " / ".join(sorted(peers)) or f"typical {cohort_label(lg_s.cohorts)} team",
            "tendencies": sum(1 for i in items if i.map == map_name)}


def _position(ins: Insight, items: list[Insight]) -> int:
    """Where a plan item's finding sits in the full list, so the front end can link the exact one.

    Different findings can share map, side, category and counts, so match the object itself
    (game_plan hands back the same Insight objects); fall back to equality, then -1 (no link).
    """
    j = next((j for j, x in enumerate(items) if x is ins), None)
    if j is None:
        j = next((j for j, x in enumerate(items) if x == ins), -1)
    return j


@lru_cache(maxsize=32)
def report(scope: Scope) -> dict:
    """The scouting report: dossier header, game plan, every tendency, map pool and per-map plants."""
    tid = scope.team_id
    self_scout = tid in CLOUD9_TEAMS
    pool = map_pool(scope)
    if pool.empty:
        return {"team": tid, "name": team_name(tid), "self_scout": self_scout, "empty": True}
    cohorts = _filter_rounds(team_rounds(), Scope(team_id=tid, side=None))["cohort"].dropna().unique()
    roster = latest_roster(tid)
    notes = []
    if roster:
        notes.append(f"Roster as of their last match in the data ({short_event(roster.event)}, {roster.last_match}).")
        n_lineups = lineups_in(tid, _filter_rounds(team_rounds(), scope)["event"].unique())
        if n_lineups > 1:
            notes.append(f"The data covers {n_lineups} lineups; filter by Event to focus on one. Tendencies about "
                         f"players who left are kept out of the game plan.")
    notes.append(f"Compared with other {peer_group(cohorts)} teams, each season with itself; covers both sides.")
    items = _insights(scope)
    plan = game_plan(items, self_scout=self_scout, limit=8)
    games, wins = int(pool["games"].sum()), int(pool["wins"].sum())
    return {
        "team": tid, "name": team_name(tid), "self_scout": self_scout, "empty": False,
        "peers": peer_group(cohorts), "roster": list(roster.names) if roster else [],
        "notes": notes,
        "record": {"games": games, "wins": wins,
                   "atk_won": int(pool["atk_won"].sum()), "atk_n": int(pool["atk_n"].sum()),
                   "def_won": int(pool["def_won"].sum()), "def_n": int(pool["def_n"].sum()),
                   "most_played": pool.iloc[0]["map"], "most_played_games": int(pool.iloc[0]["games"])},
        "plan_title": "Habits most worth varying" if self_scout else f"Things to know about {team_name(tid)}",
        "plan": [{"headline": s.headline, "detail": s.detail, "phase": s.phase, "evidence": insight_json(s.evidence),
                  "index": _position(s.evidence, items)}
                 for s in plan],
        "insights": [insight_json(i) for i in items],
        "pool": [{k: (int(v) if k != "map" else v) for k, v in row.items()} for row in pool.to_dict("records")],
        "plants": [_plants(tid, m, scope, items) for m in pool["map"]],
        "rule": f"Ranked by how far each is from the typical team. A tendency is listed only when its 95% range "
                f"doesn't overlap the comparison rate, with at least {MIN_SAMPLE} rounds.",
    }


# ---- Operator profiler ---------------------------------------------------------------------------------

def _round_index(df: pd.DataFrame, index: dict) -> list[int]:
    out = []
    for g, r in zip(df["game_id"], df["round_num"]):
        out.append(index.setdefault((g, int(r)), len(index)))
    return out


@cache
def _player_names() -> dict:
    return load().loadouts.drop_duplicates("player_id").set_index("player_id")["player_name"].to_dict()


def _weapon(w) -> str:
    return "weapon" if w is None or w != w or w == "unknown" else pretty(w)


def _moments(pos: pd.DataFrame) -> pd.DataFrame:
    """Merge a holder's recorded positions into moments (same round and shown time) and say what happened in each.

    A trade puts several events on one spot at one time (the holder's kill and the hit they took), so one dot
    carries every line: "killed novaa with the Operator (150 dmg)", "took 40 from novaa's Vandal".
    """
    if pos.empty:
        return pos.assign(via=[], what=[])
    d = load()
    names = _player_names()
    keys = ["game_id", "round_num", "t"]
    # Group on the time shown (0.1 s): GRID sometimes logs a kill 1 ms after its damage, and the two belong to
    # one moment ("killed X with the Operator (150 damage)"), not two stacked dots. The dot sits at the first
    # position logged in that tick (a cast and a hit can be logged a metre apart).
    pos = pos.sort_values(keys, kind="stable").assign(t=lambda p: p["t"].round(1))
    who = pos[keys + ["player_id"]].drop_duplicates()
    e = d.engagements[keys + ["kind", "actor_id", "target_id", "weapon", "damage"]]
    e = e.assign(t=e["t"].round(1))
    lines: dict[tuple, list[str]] = {}

    def add(key, text):
        lines.setdefault(key, []).append(text)

    out = e.merge(who.rename(columns={"player_id": "actor_id"}), on=keys + ["actor_id"])
    for (g, rn, t, a, tgt), x in out.groupby(keys + ["actor_id", "target_id"], dropna=False):
        dmg = x["damage"].dropna().sum()
        w = _weapon(x["weapon"].dropna().iloc[0] if x["weapon"].notna().any() else None)
        name = names.get(tgt, "an enemy")
        add((g, rn, t, a), f"killed {name} with the {w}" + (f" ({dmg:.0f} damage)" if dmg else "")
            if (x["kind"] == "kill").any() else f"hit {name} for {dmg:.0f} with the {w}")
    inc = e.merge(who.rename(columns={"player_id": "target_id"}), on=keys + ["target_id"])
    for (g, rn, t, tgt, a), x in inc.groupby(keys + ["target_id", "actor_id"], dropna=False):
        dmg = x["damage"].dropna().sum()
        w = _weapon(x["weapon"].dropna().iloc[0] if x["weapon"].notna().any() else None)
        name = names.get(a, "an enemy")
        add((g, rn, t, tgt), f"was killed by {name}'s {w}" if (x["kind"] == "kill").any()
            else f"took {dmg:.0f} from {name}'s {w}")
    c = d.casts[keys + ["player_id", "ability"]]
    c = c.assign(t=c["t"].round(1)).merge(who, on=keys + ["player_id"])
    for (g, rn, t, pid), x in c.groupby(keys + ["player_id"]):
        for ab in x["ability"].unique():
            add((g, rn, t, pid), f"used {pretty(ab)}")
    grouped = (pos.groupby(keys + ["player_id"], sort=False)
               .agg(x=("x", "first"), y=("y", "first"), player_name=("player_name", "first"), agent=("agent", "first"),
                    source=("source", lambda v: sorted(set(v))))
               .reset_index())
    grouped["what"] = [lines.get((g, rn, t, pid), []) for g, rn, t, pid in
                       zip(grouped["game_id"], grouped["round_num"], grouped["t"], grouped["player_id"])]
    return grouped


@lru_cache(maxsize=32)
def operator(scope: Scope) -> dict:
    r = operator_report(scope)
    gun = WEAPONS.get(scope.weapon, scope.weapon.title())
    unit = f"{SIDE_WORD.get(scope.side, '')} rounds".strip()
    if r.n_rounds == 0:
        return {"team": scope.team_id, "name": team_name(scope.team_id), "weapon": scope.weapon, "gun": gun,
                "empty": True}
    rounds_index: dict = {}
    names = {**dict(zip(r.holders["player_id"], r.holders["player_name"])),
             **dict(zip(r.pickups.get("actor_id", []), r.pickups.get("player_name", [])))}
    agents = dict(zip(zip(r.holders["game_id"], r.holders["round_num"], r.holders["player_id"]), r.holders["agent"]))
    per_map = {}
    maps = r.map_table()
    for m in maps["map"]:
        pos = _moments(r.positions[r.positions["map"] == m])
        sl = r.sightlines[r.sightlines["map"] == m]
        pu, pv = _view(m, pos["x"], pos["y"])
        area = nearest_callout(m, pos["x"], pos["y"]) if len(pos) else []
        au, av = _view(m, sl["ax"], sl["ay"])
        tu, tv = _view(m, sl["tx"], sl["ty"])
        per_map[m] = {
            # Distinct rounds (two holders in one round count once), the same count as by_map and the map chips.
            "gun_rounds": int(maps.loc[maps["map"] == m, "gun_rounds"].iloc[0]),
            "rounds": int(maps.loc[maps["map"] == m, "rounds"].iloc[0]),
            # One entry per recorded moment of the holder: via = what GRID logged (shot = dealt damage, hit = took
            # damage, cast = used an ability), what = those events in words.
            "positions": [{"at": [float(a), float(b)], "t": _r(t), "round": ri, "player": p, "agent": ag,
                           "area": ar, "via": src, "what": wh}
                          for a, b, t, ri, p, ag, ar, src, wh in zip(pu, pv, pos["t"], _round_index(pos, rounds_index),
                                                                     pos["player_name"], pos["agent"], area, pos["source"],
                                                                     pos["what"])],
            "kills": [{"from": [float(a), float(b)], "to": [float(c), float(d)], "t": _r(t), "round": ri,
                       "player": names.get(aid, _player_names().get(aid, "teammate")), "victim": _player_names().get(tid),
                       "agent": agents.get((g, rn, aid))}
                      for a, b, c, d, t, ri, aid, tid, g, rn in zip(au, av, tu, tv, sl["t"], _round_index(sl, rounds_index),
                                                                    sl["actor_id"], sl["target_id"], sl["game_id"],
                                                                    sl["round_num"])],
        }
    holders = r.holder_table()
    glance = []
    if r.n_gun_rounds:
        top = holders.groupby("player_name")["rounds"].sum().sort_values(ascending=False)
        main, main_n = top.index[0], int(top.iloc[0])
        ag = holders[holders["player_name"] == main].sort_values("rounds", ascending=False)
        glance.append(f"<b>{main}</b> is the {gun} player: <b>{of(main_n, r.n_gun_rounds, f'{gun} rounds')}</b> "
                      f"({', '.join(f'{a.title()} {n}' for a, n in zip(ag['agent'], ag['rounds']))}).")
        big = maps[maps["rounds"] >= 2 * MIN_SAMPLE].copy()
        if len(big) >= 2:  # most confidently high (Wilson lower bound) vs most confidently low (upper bound)
            b = [wilson(int(k), int(n)) for k, n in zip(big["gun_rounds"], big["rounds"])]
            big["lo_b"], big["hi_b"] = [x[0] for x in b], [x[1] for x in b]
            hi, lo = big.loc[big["lo_b"].idxmax()], big.loc[big["hi_b"].idxmin()]
            if hi["map"] != lo["map"] and hi["lo_b"] > lo["hi_b"]:
                glance.append(f"{gun} usage depends on the map: <b>{hi['map'].title()}</b> "
                              f"{of(int(hi['gun_rounds']), int(hi['rounds']), unit)} vs <b>{lo['map'].title()}</b> "
                              f"{of(int(lo['gun_rounds']), int(lo['rounds']), unit)}.")
        if len(r.pickups):
            n_pick = r.pickups[["game_id", "round_num"]].drop_duplicates().shape[0]
            glance.append(f"The {gun} changed hands mid-round in <b>{n_pick}</b> rounds (fired by a player who "
                          f"didn't buy it: {', '.join(r.pickups['player_name'].value_counts().index[:3])}).")
    else:
        art = "an" if gun[:1].lower() in "aeiou" else "a"
        glance.append(f"{team_name(scope.team_id)} never had {art} {gun} at the end of the buy phase in these "
                      f"{r.n_rounds} rounds.")
    peer = (f"typical {r.league_label} team" if r.league_method == "typical team" else f"all other {r.league_label}")
    lo, hi = wilson(r.n_gun_rounds, r.n_rounds)
    # Survived with it, per gun round (a holder alive at round end with the gun), so it is out of the headline k.
    # r.kept() counts holder-rounds, which double-counts rounds with two holders.
    kept_by_round = r.holders.groupby(["game_id", "round_num"])["kept"].any()
    kept, kept_n = int(kept_by_round.sum()), len(kept_by_round)
    w = r.win_rates("full")
    fb = r.first_shot_buckets()
    aggr = r.aggression_summary() if scope.maps else None
    return {
        "team": scope.team_id, "name": team_name(scope.team_id), "weapon": scope.weapon, "gun": gun,
        "side": scope.side, "unit": unit, "empty": False,
        "rate": {"k": r.n_gun_rounds, "n": r.n_rounds, "rate": _r(pct(r.n_gun_rounds, r.n_rounds), 4),
                 "lo": _r(lo, 4), "hi": _r(hi, 4), "base": _r(r.league_rate, 4), "peers": peer},
        "kept": {"k": kept, "n": kept_n},
        "full_buy": {"with": list(w["with"]), "without": list(w["without"])},
        "first_shot": [{"bucket": b, "rounds": int(n)} for b, n in zip(fb.get("bucket", []), fb.get("rounds", []))],
        "fired_rounds": int(fb["rounds"].sum()) if len(fb) else 0,
        "holders": [{"player": p, "agent": a, "rounds": int(n), "won": int(wn), "kept": int(k)}
                    for p, a, n, wn, k in zip(holders["player_name"], holders["agent"], holders["rounds"],
                                              holders["won"], holders["kept"])],
        "by_map": [{"map": m, "k": int(k), "n": int(n)} for m, k, n in zip(maps["map"], maps["gun_rounds"], maps["rounds"])],
        "glance": glance,
        "aggression": aggr if aggr and aggr.get("median") is not None and aggr["n"] >= MIN_SAMPLE else None,
        "rounds": _round_info(r, rounds_index),
        "maps": per_map,
    }


def _round_info(r, rounds_index: dict) -> list[dict]:
    """Who, against whom, when and how it ended, for every round the payload's dots and kills come from (list
    position = the `round` index used on positions and kills). Holder fields are filled on the Operator page only."""
    tr = r.rounds.set_index(["game_id", "round_num"])
    holders = getattr(r, "holders", None)
    hold = (holders.drop_duplicates(["game_id", "round_num"]).set_index(["game_id", "round_num"]) if holders is not None
            else pd.DataFrame())
    out = [None] * len(rounds_index)
    for (g, rn), i in rounds_index.items():
        row = tr.loc[(g, rn)] if (g, rn) in tr.index else None
        h = hold.loc[(g, rn)] if (g, rn) in hold.index else None
        out[i] = {"game": g, "round_num": int(rn), "map": None if row is None else row["map"],
                  "date": None if row is None else str(row["started_at"])[:10],
                  # full UTC start (ISO, sorts as text): orders two games on one map on the same date
                  "started": None if row is None else str(row["started_at"]),
                  "opponent": None if row is None else team_name(row["opp_id"]),
                  "won": None if row is None else bool(row["won"]),
                  "holder": None if h is None else h["player_name"], "agent": None if h is None else h["agent"]}
    return out


# ---- Utility profiler ----------------------------------------------------------------------------------

def _habits(rep, map_name: str) -> list[dict]:
    h = rep.habits(map_name)
    if h.empty:
        return []
    u, v = _view(map_name, h["x"], h["y"])
    out = []
    for i, row in enumerate(h.itertuples()):
        out.append({"player": row.player_name, "agent": row.agent, "ability": row.ability,
                    "ability_name": pretty(row.ability), "class": row.util_class, "at": [float(u[i]), float(v[i])],
                    "k": int(row.rounds), "n": int(row.rounds_on_agent), "share": _r(row.share, 4),
                    "area": row.area, "strong": bool(row.rounds_on_agent >= MIN_SAMPLE and row.share >= HABIT_MIN_SHARE)})
    out.sort(key=lambda x: (x["strong"], x["share"], x["k"]), reverse=True)
    return out


@lru_cache(maxsize=32)
def utility(scope: UtilityScope) -> dict:
    rep = utility_report(scope)
    unit = f"{SIDE_WORD.get(scope.side, '')} rounds".strip()
    if rep.n_rounds == 0:
        return {"team": scope.team_id, "name": team_name(scope.team_id), "empty": True}
    casts = add_landings(rep.casts)
    landed = replace(rep, casts=casts.assign(x=casts["land_x"].where(casts["land_x"].notna(), casts["x"]),
                                             y=casts["land_y"].where(casts["land_y"].notna(), casts["y"])))
    played = rep.rounds["map"].value_counts()
    per_map = {}
    rounds_index: dict = {}
    for m in played.index:
        c = casts[casts["map"] == m]
        u, v = _view(m, c["x"], c["y"])
        area = nearest_callout(m, c["x"], c["y"]) if len(c) else []
        has_aim = c[["view_x", "view_y"]].notna().all(axis=1).to_numpy()
        norm = np.hypot(c["view_x"].fillna(0), c["view_y"].fillna(0)).replace(0, 1)
        au, av = _view(m, c["x"] + AIM_CM * c["view_x"].fillna(0) / norm, c["y"] + AIM_CM * c["view_y"].fillna(0) / norm)
        has_land = c["land_x"].notna().to_numpy()
        lu, lv = _view(m, c["land_x"].fillna(0), c["land_y"].fillna(0))
        ar = rep.agent_rounds_by_map(m)
        tab = (c.groupby(["player_id", "player_name", "agent", "ability"], observed=True)
               .agg(casts=("event_id", "size"), rounds=("round_key", "nunique")).reset_index())
        per_map[m] = {
            "rounds": int(played[m]),
            "rounds_with_casts": int(c["round_key"].nunique()),
            "casts": [{"at": [float(u[i]), float(v[i])], "t": _r(t), "phase": ph, "round": ri, "player": p, "agent": ag,
                       "ability": ab, "ability_name": pretty(ab), "class": cl, "area": area[i],
                       "aim": [float(au[i]), float(av[i])] if has_aim[i] else None,
                       "land": [float(lu[i]), float(lv[i])] if has_land[i] else None}
                      for i, (t, ph, ri, p, ag, ab, cl) in enumerate(zip(
                          c["t"], c["phase"], _round_index(c, rounds_index), c["player_name"], c["agent"],
                          c["ability"], c["util_class"]))],
            "habits": _habits(rep, m),
            "habits_landing": _habits(landed, m),
            "who": [{"player": p, "agent": a, "ability": b, "ability_name": pretty(b), "casts": int(n), "rounds": int(k),
                     "on_agent": int(ar.get((pid, a), k)),
                     "per_round": _r(int(n) / max(int(ar.get((pid, a), k)), 1), 2)}
                    for pid, p, a, b, n, k in zip(tab["player_id"], tab["player_name"], tab["agent"], tab["ability"],
                                                  tab["casts"], tab["rounds"])],
        }
        per_map[m]["who"].sort(key=lambda x: x["casts"], reverse=True)
        # Everyone who played this map in scope (with the agents and rounds), cast or not, so the page can show the
        # full roster and say who had none of this utility.
        names = _player_names()
        roster: dict[str, dict] = {}
        for (pid, agent), n in sorted(ar.items(), key=lambda kv: -kv[1]):
            e = roster.setdefault(pid, {"player": names.get(pid, pid), "agents": [], "rounds": 0})
            e["agents"].append({"agent": agent, "rounds": int(n)})
            e["rounds"] += int(n)
        per_map[m]["players"] = sorted(roster.values(), key=lambda e: -e["rounds"])
    val = landing_model()["validation"]
    return {"team": scope.team_id, "name": team_name(scope.team_id), "side": scope.side, "unit": unit, "empty": False,
            "classes": list(scope.classes), "phases": list(scope.phases),
            "landing": {"median_model_m": val.get("median_model_m"), "median_cast_m": val.get("median_cast_m")},
            "maps_order": list(played.index), "rounds": _round_info(rep, rounds_index), "maps": per_map}
