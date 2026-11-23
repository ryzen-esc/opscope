"""Build the parquet cache from every VALORANT series.

    uv run python -m opscope.ingest.build              # build missing series, then consolidate
    uv run python -m opscope.ingest.build --force      # rebuild everything
    uv run python -m opscope.ingest.build --series 2748746 --series 2972877

Output (gitignored, never commit): cache/v{VERSION}/{table}.parquet and cache/v{VERSION}/ingest_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from opscope.data import iter_envelopes, iter_jsonl, load_meta, load_series, series_file, supplement_file
from opscope.ingest.feed import TABLES, parse_envelopes
from opscope.ingest.supplement import index_supplement, join_casts

VERSION = 1
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# GRID merged two maps into game 1 of these series (see the supplement README); drop that game.
MERGED_MAP_GAMES = {("2890334", "1"), ("2890361", "1")}

STR, F, I, B = "string", "float64", "Int64", "boolean"
SCHEMA: dict[str, dict[str, str]] = {
    "games": {"series_id": STR, "game_id": STR, "game_number": I, "session": I, "session_valid": B,
              "map": STR, "patch": STR, "event": STR, "stage": STR, "tier": STR, "low_rate": B,
              "started_at": STR, "team1_id": STR, "team2_id": STR, "team1_score": I, "team2_score": I,
              "winner_team_id": STR, "min_x": F, "min_y": F, "max_x": F, "max_y": F, "rounds_parsed": I},
    "rounds": {"series_id": STR, "game_id": STR, "round_num": I, "start_at": F, "fs_at": F, "fe_at": F,
               "won_at": F, "end_at": F, "plant_at": F, "planter_id": STR, "atk_team_id": STR,
               "def_team_id": STR, "winner_team_id": STR, "win_type": STR, "atk_loadout": F,
               "def_loadout": F, "atk_money": F, "def_money": F, "won_t": F, "plant_t": F, "buy_len": F,
               "played": B},
    "loadouts": {"series_id": STR, "game_id": STR, "round_num": I, "player_id": STR, "player_name": STR,
                 "team_id": STR, "side": STR, "agent": STR, "primary_fe": STR, "sidearm_fe": STR,
                 "shield_fe": STR, "money_fe": F, "loadout_value": F, "primary_end": STR, "alive_end": B},
    "engagements": {"series_id": STR, "event_id": STR, "game_id": STR, "round_num": I, "at": F, "t": F,
                    "phase": STR, "kind": STR, "actor_id": STR, "actor_team_id": STR, "actor_side": STR,
                    "target_id": STR, "target_team_id": STR, "weapon": STR, "damage": F, "headshot": B,
                    "first_kill": B, "ax": F, "ay": F, "tx": F, "ty": F},
    "casts": {"series_id": STR, "event_id": STR, "game_id": STR, "round_num": I, "at": F, "t": F,
              "phase": STR, "player_id": STR, "team_id": STR, "side": STR, "agent": STR, "ability": STR,
              "slot": STR, "x": F, "y": F, "z": F, "view_x": F, "view_y": F, "view_z": F,
              "pos_source": STR, "quality": STR},
    "snapshots": {"series_id": STR, "game_id": STR, "round_num": I, "moment": STR, "player_id": STR,
                  "team_id": STR, "side": STR, "alive": B, "x": F, "y": F},
}


def cache_dir() -> Path:
    return Path(os.environ.get("OPSCOPE_CACHE", PROJECT_ROOT / "cache")) / f"v{VERSION}"


def to_frame(rows: list[dict], table: str) -> pd.DataFrame:
    schema = SCHEMA[table]
    df = pd.DataFrame(rows, columns=list(schema))
    for col, dtype in schema.items():
        if dtype == B:
            df[col] = df[col].map(lambda v: None if v is None or v != v else bool(v))
        df[col] = df[col].astype(dtype)
    return df


def _tier(event: str) -> str:
    return "gc" if "Game Changers" in event else "vct"


def build_series(row: dict, meta_games: list[dict], out: Path) -> dict:
    """Parse one series and write its parts. Runs in a worker process."""
    sid = row["series_id"]
    tables, report = parse_envelopes(sid, iter_envelopes(series_file(row)))

    supp_path = supplement_file(row)
    if supp_path:
        supp = index_supplement(iter_jsonl(supp_path))
        report["casts_supplemented"] = join_casts(tables["casts"], supp)
        report["supplement_records"] = len(supp)

    # Keep only games that meta/games.csv lists (drops rolled-back attempts) and not merged maps.
    meta = {g["game_id"]: g for g in meta_games
            if g["series_id"] == sid and (sid, g["game_number"]) not in MERGED_MAP_GAMES}
    rounds_per_game = Counter(r["game_id"] for r in tables["rounds"] if r["winner_team_id"])
    games = []
    for g in tables["games"]:
        m = meta.get(g["game_id"])
        if m is None:
            report["games_not_in_meta"] += 1
            continue
        g.update(
            game_number=int(m["game_number"]), session=int(m["session"]),
            session_valid=m["session_valid"] == "True", event=row["event"], stage=row["stage"],
            tier=_tier(row["event"]), low_rate=row["event"].startswith("VCT Americas") and "2025" in row["event"],
            started_at=m["started_at"], team1_id=m["team1_id"], team2_id=m["team2_id"],
            team1_score=int(m["team1_score"] or 0), team2_score=int(m["team2_score"] or 0),
            winner_team_id=m["winner_team_id"] or None, rounds_parsed=rounds_per_game[g["game_id"]],
        )
        if g["rounds_parsed"] != g["team1_score"] + g["team2_score"]:
            report["round_count_mismatch"] += 1
            report.setdefault("mismatch_games", []).append(  # type: ignore[arg-type]
                f'{g["game_id"]}:{g["rounds_parsed"]}vs{g["team1_score"] + g["team2_score"]}')
        games.append(g)
    tables["games"] = games
    keep = {g["game_id"] for g in games}
    for table in TABLES:
        if table != "games":
            tables[table] = [r for r in tables[table] if r["game_id"] in keep]

    for table in TABLES:
        path = out / "parts" / table / f"{sid}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        to_frame(tables[table], table).to_parquet(path, index=False)
    report["games_kept"] = len(games)
    return {"series_id": sid, **dict(report)}


def consolidate(out: Path) -> dict[str, int]:
    sizes = {}
    for table in TABLES:
        parts = sorted((out / "parts" / table).glob("*.parquet"))
        frames = [f for f in (pd.read_parquet(p) for p in parts) if len(f)]
        df = pd.concat(frames, ignore_index=True) if frames else to_frame([], table)
        df.to_parquet(out / f"{table}.parquet", index=False)
        sizes[table] = len(df)
    return sizes


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", action="append", help="only these series ids (repeatable)")
    ap.add_argument("--force", action="store_true", help="rebuild series that already have parts")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = ap.parse_args(argv)

    out = cache_dir()
    out.mkdir(parents=True, exist_ok=True)
    rows = load_series("val")
    if args.series:
        rows = [r for r in rows if r["series_id"] in set(args.series)]
    if not args.force:
        done = {p.stem for p in (out / "parts" / "rounds").glob("*.parquet")}
        rows = [r for r in rows if r["series_id"] not in done]
    meta_games = load_meta("games")

    started, results, failures = time.time(), [], []
    print(f"Building {len(rows)} series with {args.workers} workers → {out}")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(build_series, r, meta_games, out): r["series_id"] for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            sid = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:  # keep going; report at the end
                failures.append({"series_id": sid, "error": repr(exc)})
            if i % 50 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)} series ({time.time() - started:.0f}s)")

    sizes = consolidate(out)
    totals = Counter()
    for r in results:
        totals.update({k: v for k, v in r.items() if isinstance(v, int) and not isinstance(v, bool)})
    report = {
        "version": VERSION, "built_series": len(results), "failures": failures, "table_rows": sizes,
        "totals": dict(totals),
        "mismatches": {r["series_id"]: r["mismatch_games"] for r in results if r.get("mismatch_games")},
        "seconds": round(time.time() - started, 1),
    }
    report_path = out / "ingest_report.json"
    if report_path.exists() and not args.force and args.series is None:
        prev = json.loads(report_path.read_text())
        report["previous_built_series"] = prev.get("built_series")
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("built_series", "table_rows", "seconds")}, indent=2))
    print(f"{len(failures)} failures, {len(report['mismatches'])} series with round-count mismatches")


if __name__ == "__main__":
    main()
