"""Operator (and Odin / Outlaw / Marshal) profiler.

Who buys the big gun, how often, where they set up, when they shoot, whether the gun changes hands,
and whether it wins rounds. Every number comes with the sample it was computed from.

Notes on the data (see CLAUDE.md):
- Ownership comes from the freeze-end inventory (what was bought or carried into the round).
- GRID positions are periodic samples (~1-4 m error), so setups are shown as points/densities, never exact angles.
- Mid-round pickups are not recorded; a "pickup" is inferred when a player who did not own the gun at
  freeze end deals damage with it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

import numpy as np
import pandas as pd

from opscope.analytics.stats import typical_rate
from opscope.load import Dataset, load, peer_group
from opscope.maps import aggression

TIME_BUCKETS = [(-1e9, 20, "0–20s"), (20, 40, "20–40s"), (40, 60, "40–60s"), (60, 1e9, "60s+")]
BUY_CLASSES = ["pistol", "eco", "half", "full"]


def time_bucket(t: pd.Series) -> pd.Series:
    edges = [-np.inf, 20, 40, 60, np.inf]
    labels = [b[2] for b in TIME_BUCKETS]
    return pd.cut(t, bins=edges, labels=labels, right=False)


def buy_class(loadout: pd.Series, round_num: pd.Series) -> pd.Series:
    out = np.select([loadout < 6000, loadout < 18000], ["eco", "half"], default="full")
    out = np.where(round_num.isin([1, 13]), "pistol", out)
    return pd.Series(out, index=loadout.index, dtype="string")


@cache
def team_rounds() -> pd.DataFrame:
    """One row per (played round, team) from that team's point of view."""
    r = load().rounds
    r = r[r["played"].fillna(False)]
    common = ["series_id", "game_id", "round_num", "map", "patch", "event", "tier", "season", "cohort", "started_at",
              "winner_team_id", "won_t", "plant_t"]
    atk = r[common + ["atk_team_id", "def_team_id", "atk_loadout"]].set_axis(common + ["team_id", "opp_id", "loadout"], axis=1)
    atk["side"] = "attacker"
    dfn = r[common + ["def_team_id", "atk_team_id", "def_loadout"]].set_axis(common + ["team_id", "opp_id", "loadout"], axis=1)
    dfn["side"] = "defender"
    tr = pd.concat([atk, dfn], ignore_index=True)
    tr["won"] = tr["winner_team_id"] == tr["team_id"]
    tr["buy"] = buy_class(tr["loadout"], tr["round_num"])
    return tr


@cache
def positions() -> pd.DataFrame:
    """Every live-round (player, position, t) we know of: shots, hits taken and ability casts."""
    d = load()
    e = d.engagements[(d.engagements["phase"] == "live") & (d.engagements["t"] > 0)]
    keys = ["game_id", "round_num", "t"]
    shots = e[keys + ["actor_id", "ax", "ay"]].set_axis(keys + ["player_id", "x", "y"], axis=1).assign(source="shot")
    hits = e[keys + ["target_id", "tx", "ty"]].set_axis(keys + ["player_id", "x", "y"], axis=1).assign(source="hit")
    c = d.casts[(d.casts["phase"] == "live") & (d.casts["t"] > 0)]
    casts = c[keys + ["player_id", "x", "y"]].assign(source="cast")
    return pd.concat([shots, hits, casts], ignore_index=True).dropna(subset=["x", "y"])


@dataclass(frozen=True)
class Scope:
    """What the coach has filtered to. Empty tuples mean 'all'."""
    team_id: str
    weapon: str = "operator"
    side: str | None = "defender"
    maps: tuple[str, ...] = ()
    opponents: tuple[str, ...] = ()
    patches: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    players: tuple[str, ...] = ()
    cohorts: tuple[str, ...] = ()  # tier-season, e.g. ("vct-2025",); set for league comparisons

    def league(self) -> "Scope":
        """Same map/side/patch/event/cohort context, but every team."""
        return Scope(team_id="", weapon=self.weapon, side=self.side, maps=self.maps,
                     patches=self.patches, events=self.events, cohorts=self.cohorts)


def season_weighted_rate(team_rows: pd.DataFrame, league_rows: pd.DataFrame, flag: str,
                         min_rounds: int | None = None) -> tuple[float, str]:
    """Comparison rate for a team whose rounds may span several seasons (cohorts).

    Each season is compared only with that season: the typical other team's rate is found per cohort, then
    weighted by how many of the team's rows fall in that cohort. `league_rows` must hold other teams' rows with
    `cohort`, `team_id` and a boolean `flag` column.
    """
    weights = team_rows["cohort"].value_counts()
    acc = total = 0.0
    methods = set()
    for cohort, w in weights.items():
        lg = league_rows[league_rows["cohort"] == cohort]
        if lg.empty:
            continue
        per_team = lg.groupby("team_id")[flag].agg(["sum", "size"])
        kwargs = {"min_rounds": min_rounds} if min_rounds is not None else {}
        rate, method = typical_rate(per_team["sum"], per_team["size"], **kwargs)
        acc += w * rate
        total += w
        methods.add(method)
    if not total:
        return 0.0, "all rounds"
    return acc / total, ("typical team" if methods == {"typical team"} else "all rounds")


def league_scope(s: Scope, team_rows: pd.DataFrame, **overrides) -> Scope:
    """The league to compare a team with: every *other* team in the same tier and season as the team's rounds.

    VCT 2025 and Game Changers 2025/2026 play on different patches and at different levels, so mixing them
    would compare a team with a meta it never played in.
    """
    cohorts = tuple(sorted(team_rows["cohort"].dropna().unique()))
    base = s.league()
    return Scope(**{**base.__dict__, "cohorts": cohorts, **overrides})


def _filter_rounds(tr: pd.DataFrame, s: Scope) -> pd.DataFrame:
    m = pd.Series(True, index=tr.index)
    if s.team_id:
        m &= tr["team_id"] == s.team_id
    if s.side:
        m &= tr["side"] == s.side
    if s.maps:
        m &= tr["map"].isin(s.maps)
    if s.opponents:
        m &= tr["opp_id"].isin(s.opponents)
    if s.patches:
        m &= tr["patch"].isin(s.patches)
    if s.events:
        m &= tr["event"].isin(s.events)
    if s.cohorts:
        m &= tr["cohort"].isin(s.cohorts)
    return tr[m]


@dataclass
class OperatorReport:
    scope: Scope
    rounds: pd.DataFrame            # team rounds in scope, with has_gun flag
    holders: pd.DataFrame           # one row per (round, holder)
    positions: pd.DataFrame         # every known live position of the holder
    setups: pd.DataFrame            # first position per holder-round within SETUP_WINDOW
    sightlines: pd.DataFrame        # gun kills: shooter -> victim
    shots: pd.DataFrame             # every live gun engagement by the team
    pickups: pd.DataFrame           # rounds where a non-owner fired the gun
    league_share: tuple[int, int] = (0, 0)
    league_aggression: np.ndarray = field(default_factory=lambda: np.array([]))
    league_label: str = "league"     # e.g. "VCT 2025": who the team is compared with
    league_rate: float = 0.0         # comparison rate: typical team (median), or pooled if too few teams
    league_method: str = "all rounds"

    # ---- headline numbers -----------------------------------------------------------------
    @property
    def n_rounds(self) -> int:
        return len(self.rounds)

    @property
    def n_gun_rounds(self) -> int:
        return int(self.rounds["has_gun"].sum())

    def holder_table(self) -> pd.DataFrame:
        if self.holders.empty:
            return pd.DataFrame(columns=["player_name", "agent", "rounds", "won", "kept"])
        h = self.holders
        t = (h.groupby(["player_name", "agent"], observed=True)
             .agg(rounds=("round_num", "size"), won=("won", "sum"), kept=("kept", "sum"))
             .reset_index().sort_values("rounds", ascending=False))
        return t

    def map_table(self) -> pd.DataFrame:
        r = self.rounds
        t = r.groupby("map").agg(rounds=("has_gun", "size"), gun_rounds=("has_gun", "sum")).reset_index()
        t["share"] = t["gun_rounds"] / t["rounds"]
        return t.sort_values("rounds", ascending=False)

    def win_rates(self, buy: str = "full") -> dict[str, tuple[int, int]]:
        r = self.rounds[self.rounds["buy"] == buy]
        with_gun, without = r[r["has_gun"]], r[~r["has_gun"]]
        return {"with": (int(with_gun["won"].sum()), len(with_gun)),
                "without": (int(without["won"].sum()), len(without))}

    def first_shot_buckets(self) -> pd.DataFrame:
        """When the gun first fires, in rounds where the team had it at the end of the buy phase.

        Pickup rounds (someone fired a gun the team didn't buy) are excluded, so the count is out of the same
        gun rounds the caption names.
        """
        gun_rounds = self.rounds.loc[self.rounds["has_gun"], ["game_id", "round_num"]]
        shots = self.shots.merge(gun_rounds, on=["game_id", "round_num"]) if not self.shots.empty else self.shots
        if shots.empty:
            return pd.DataFrame(columns=["bucket", "rounds"])
        first = shots.groupby(["game_id", "round_num"])["t"].min()
        b = time_bucket(first).value_counts().reindex([x[2] for x in TIME_BUCKETS], fill_value=0)
        return b.rename_axis("bucket").reset_index(name="rounds")

    def kept(self) -> tuple[int, int]:
        """Holder survived with the gun (it carries into next round), out of holder-rounds."""
        return int(self.holders["kept"].sum()), len(self.holders)

    def aggression_summary(self) -> dict:
        a = self.setups["aggression"].dropna().astype(float) if not self.setups.empty else pd.Series(dtype=float)
        lg = self.league_aggression
        if a.empty or len(lg) == 0:
            return {"median": None, "league_median": None, "percentile": None, "n": len(a)}
        med = float(a.median())
        return {"median": med, "league_median": float(np.median(lg)),
                "percentile": float((lg < med).mean()), "n": len(a)}


def _holders(d: Dataset, tr: pd.DataFrame, weapon: str) -> pd.DataFrame:
    lo = d.loadouts[d.loadouts["primary_fe"] == weapon]
    cols = ["game_id", "round_num", "team_id", "player_id", "player_name", "agent", "primary_end", "alive_end"]
    h = tr.merge(lo[cols], on=["game_id", "round_num", "team_id"], how="inner")
    h["kept"] = (h["primary_end"] == weapon) & h["alive_end"].fillna(False)
    return h


SETUP_WINDOW = 30.0  # seconds after the buy phase that count as "early setup"
_POS_COLS = ["game_id", "round_num", "player_id", "player_name", "agent", "map", "won", "x", "y", "t",
             "source", "aggression", "bucket"]


def _holder_positions(h: pd.DataFrame) -> pd.DataFrame:
    """Every known live position of the gun holder in their gun rounds."""
    if h.empty:
        return pd.DataFrame(columns=_POS_COLS)
    keys = ["game_id", "round_num", "player_id"]
    m = h[keys + ["player_name", "agent", "map", "won"]].merge(positions(), on=keys, how="inner")
    if m.empty:
        return pd.DataFrame(columns=_POS_COLS)
    m["aggression"] = np.nan
    for map_name, idx in m.groupby("map").groups.items():
        m.loc[idx, "aggression"] = aggression(map_name, m.loc[idx, "x"], m.loc[idx, "y"])
    m["bucket"] = time_bucket(m["t"])
    return m.reset_index(drop=True)


def _setups(pos: pd.DataFrame) -> pd.DataFrame:
    """First position per gun round inside the early-setup window (coverage is partial by design)."""
    early = pos[pos["t"] <= SETUP_WINDOW]
    if early.empty:
        return early
    return early.loc[early.groupby(["game_id", "round_num", "player_id"])["t"].idxmin()].reset_index(drop=True)


def operator_report(s: Scope) -> OperatorReport:
    if not s.team_id:
        raise ValueError("operator_report needs a team_id; league context is computed inside it")
    d = load()
    tr_all = team_rounds()
    tr = _filter_rounds(tr_all, s).copy()
    h = _holders(d, tr, s.weapon)
    if s.players:
        h = h[h["player_id"].isin(s.players)]
    gun_keys = set(zip(h["game_id"], h["round_num"]))
    tr["has_gun"] = [k in gun_keys for k in zip(tr["game_id"], tr["round_num"])]

    # Every live engagement the team made with the gun in scope rounds.
    e = d.engagements
    e = e[(e["weapon"] == s.weapon) & (e["phase"] == "live") & (e["actor_team_id"] == s.team_id)]
    e = e.merge(tr[["game_id", "round_num", "won"]], on=["game_id", "round_num"], how="inner")
    owners = set(zip(h["game_id"], h["round_num"], h["player_id"]))
    # Explicit bool dtype: an empty list would become an object column and break the ~mask below.
    e = e.assign(owner=np.array([k in owners for k in zip(e["game_id"], e["round_num"], e["actor_id"])], dtype=bool))
    names = d.loadouts.drop_duplicates("player_id").set_index("player_id")["player_name"]
    pickups = (e[~e["owner"]].groupby(["game_id", "round_num", "actor_id"]).size()
               .reset_index(name="shots").assign(player_name=lambda x: x["actor_id"].map(names)))
    sight = e[e["kind"] == "kill"].dropna(subset=["ax", "ay", "tx", "ty"])

    # League context: share of team-rounds with the gun, and setup aggression, same map/side/patch.
    lg = league_scope(s, tr)
    lg_tr = _filter_rounds(tr_all, lg)
    lg_tr = lg_tr[lg_tr["team_id"] != s.team_id]  # the league is everyone else
    lg_h = _holders(d, lg_tr, s.weapon)
    lg_share = (len(set(zip(lg_h["game_id"], lg_h["round_num"], lg_h["team_id"]))), len(lg_tr))
    lg_keys = set(zip(lg_h["game_id"], lg_h["round_num"], lg_h["team_id"]))
    lg_flag = lg_tr.assign(has=np.array([k in lg_keys for k in zip(lg_tr["game_id"], lg_tr["round_num"], lg_tr["team_id"])],
                                        dtype=bool))
    lg_rate, lg_method = season_weighted_rate(tr, lg_flag, "has")
    lg_setups = _setups(_holder_positions(lg_h[lg_h["team_id"] != s.team_id])) if s.maps else pd.DataFrame()
    lg_aggr = lg_setups["aggression"].dropna().to_numpy(float) if not lg_setups.empty else np.array([])

    pos = _holder_positions(h)
    return OperatorReport(scope=s, rounds=tr, holders=h, positions=pos, setups=_setups(pos), sightlines=sight,
                          shots=e, pickups=pickups, league_share=lg_share, league_aggression=lg_aggr,
                          league_label=peer_group(lg.cohorts), league_rate=lg_rate, league_method=lg_method)
