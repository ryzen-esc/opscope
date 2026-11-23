"""Load the parquet cache as pandas DataFrames with names attached.

Build the cache first: `uv run python -m opscope.ingest.build`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import pandas as pd

from opscope.data import load_meta
from opscope.ingest.build import cache_dir
from opscope.taxonomy import WEAPON_GROUP, util_class

CLOUD9_TEAMS = {"79": "Cloud9 (VCT 2025)", "3429": "Cloud9 GC (2026)"}
TIER_NAMES = {"vct": "VCT", "gc": "Game Changers"}


def cohort_label(cohorts) -> str:
    """('vct-2025',) -> 'VCT 2025'; ('gc-2025', 'gc-2026') -> 'Game Changers 2025–2026'."""
    cohorts = sorted(set(cohorts))
    if not cohorts:
        return "league"
    tiers = sorted({c.split("-")[0] for c in cohorts})
    years = sorted({c.split("-")[1] for c in cohorts})
    tier = " + ".join(TIER_NAMES.get(t, t) for t in tiers)
    return f"{tier} {years[0]}" + (f"–{years[-1]}" if len(years) > 1 else "")


@dataclass(frozen=True)
class Dataset:
    games: pd.DataFrame
    rounds: pd.DataFrame
    loadouts: pd.DataFrame
    engagements: pd.DataFrame
    casts: pd.DataFrame
    snapshots: pd.DataFrame
    teams: pd.DataFrame
    players: pd.DataFrame


def _read(table: str) -> pd.DataFrame:
    path = cache_dir() / f"{table}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing. Run: uv run python -m opscope.ingest.build")
    return pd.read_parquet(path)


@cache
def load() -> Dataset:
    games = _read("games")
    # A cohort is tier + season (e.g. "vct-2025"): teams are only compared with teams in the same cohort,
    # because tiers and years play on different patches and metas.
    games["season"] = games["started_at"].str[:4].astype("string")
    games["cohort"] = (games["tier"] + "-" + games["season"]).astype("string")
    keep = set(games["game_id"])
    game_cols = games[["game_id", "map", "patch", "tier", "event", "season", "cohort", "started_at"]]

    def scoped(table: str) -> pd.DataFrame:
        df = _read(table)
        return df[df["game_id"].isin(keep)].merge(game_cols, on="game_id", how="left")

    teams = pd.DataFrame(load_meta("teams"))[["team_id", "name", "other_names"]].astype("string")
    players = pd.DataFrame(load_meta("players"))[["player_id", "name", "latest_team_name"]].astype("string")

    casts = scoped("casts")
    casts["util_class"] = casts["ability"].map(util_class).astype("string")
    engagements = scoped("engagements")
    engagements["weapon_group"] = engagements["weapon"].map(lambda w: WEAPON_GROUP.get(w, "ability")).astype("string")

    return Dataset(
        games=games, rounds=scoped("rounds"), loadouts=scoped("loadouts"),
        engagements=engagements, casts=casts, snapshots=scoped("snapshots"),
        teams=teams, players=players,
    )
