"""Join the ability supplement (precise 3D cast position + aim) onto GRID casts.

See $STL_DATA_DIR/val-ability-supplements/README.md for the quality flags.
"""
from __future__ import annotations

from collections.abc import Iterable


def _frame_for(record: dict) -> dict | None:
    """Best available position/view frame for a supplement record."""
    quality = record.get("quality")
    if quality == "missing_both":
        return None
    if quality == "gap_exceeded":
        # The interpolation spans a death or round break; use whichever frame is closer to the cast.
        frames = [f for f in (record.get("frame_before"), record.get("frame_after")) if f]
        return min(frames, key=lambda f: abs(f.get("offset_ms") or 0), default=None)
    return record.get("interpolated")


def index_supplement(records: Iterable[dict]) -> dict[str, dict]:
    """grid_event_id -> fields to overwrite on the cast row. Casts not in GRID are dropped."""
    out = {}
    for rec in records:
        if not rec.get("in_grid") or not rec.get("grid_event_id"):
            continue
        frame = _frame_for(rec)
        row = {"slot": rec.get("slot"), "quality": rec.get("quality")}
        if frame and frame.get("position"):
            pos, view = frame["position"], frame.get("view") or {}
            row.update(x=pos.get("x"), y=pos.get("y"), z=pos.get("z"),
                       view_x=view.get("x"), view_y=view.get("y"), view_z=view.get("z"),
                       pos_source="supplement")
        out[rec["grid_event_id"]] = row
    return out


def join_casts(casts: list[dict], supplement: dict[str, dict]) -> int:
    """Overwrite cast rows in place with supplement data. Returns how many matched."""
    matched = 0
    for cast in casts:
        extra = supplement.get(cast["event_id"])
        if extra:
            cast.update(extra)
            matched += 1
    return matched
