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
    keep = set(games["game_id"])
    game_cols = games[["game_id", "map", "patch", "tier", "event"]]

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
