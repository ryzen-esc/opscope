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


def iter_events(path: Path) -> Iterator[dict]:
    """Stream every event from a .jsonl.zst feed."""
    with zstd.open(path, "rt") as f:
        for line in f:
            for event in json.loads(line).get("events", []):
                yield event
