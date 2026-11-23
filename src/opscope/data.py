"""Helpers for reading the GRID starter data without decompressing it to disk."""
import csv
import json
import os
from collections.abc import Iterator
from pathlib import Path

from compression import zstd  # Python 3.14+
from dotenv import load_dotenv

load_dotenv()


def data_dir() -> Path:
    path = os.environ.get("STL_DATA_DIR")
    if not path:
        raise RuntimeError("Set STL_DATA_DIR in .env (see .env.example)")
    return Path(path)


def load_series(game: str = "val") -> list[dict]:
    with open(data_dir() / game / "series.csv", newline="") as f:
        return list(csv.DictReader(f))


def series_file(row: dict, game: str = "val") -> Path:
    """Resolve the feed path from a series.csv row (handles bare or prefixed names)."""
    name = row["file"]
    for candidate in (data_dir() / name, data_dir() / game / name):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(name)


def iter_jsonl(path: Path) -> Iterator[dict]:
    """Stream every JSON line from a .jsonl.zst file (GRID envelopes or supplement casts)."""
    with zstd.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def iter_envelopes(path: Path) -> Iterator[tuple[str, dict]]:
    """Yield (occurredAt, event) for every event, keeping the envelope's UTC timestamp."""
    for envelope in iter_jsonl(path):
        occurred_at = envelope.get("occurredAt", "")
        for event in envelope.get("events", []):
            yield occurred_at, event


def iter_events(path: Path) -> Iterator[dict]:
    """Stream every event from a .jsonl.zst feed."""
    for _, event in iter_envelopes(path):
        yield event


def supplement_file(row: dict) -> Path | None:
    """Resolve the ability supplement path from a series.csv row, or None if there is none."""
    name = row.get("ability_supplement") or ""
    if not name:
        return None
    path = data_dir() / name
    return path if path.exists() else None


def load_meta(table: str, title: str = "val") -> list[dict]:
    """Read a meta/*.csv lookup table, filtered to one title."""
    with open(data_dir() / "meta" / f"{table}.csv", newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("title") == title]
