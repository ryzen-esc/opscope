from __future__ import annotations

from datetime import datetime, timedelta

"""Synthetic GRID envelope builders for tests. Never put real data (or excerpts) here."""

BASE_TIME = datetime(2026, 1, 1, 0, 0, 0)

def iso(t: datetime) -> str:
    return t.isoformat()


def make_player(pid: str, name: str, *, agent: str = "jett", money: int = 0,
                items: list[str] | None = None, x: float = 0.0, y: float = 0.0, alive: bool = True) -> dict:
    return {
        "id": pid, "name": name, "money": money, "alive": alive,
        "position": {"x": x, "y": y},
        "inventory": {"items": [{"id": i} for i in (items or [])]},
        "character": {"id": agent},
    }


def make_team(tid: str, side: str, players: list[dict]) -> dict:
    # Synthetic per-player loadoutValue: reuse money unless the test sets it
    for p in players:
        p.setdefault("loadoutValue", p.get("money", 0))
    return {"id": tid, "side": side, "players": players}


def make_game(game_id: str, teams: list[dict], *, map_name: str = "ascent",
              seg_sides: dict[str, str] | None = None) -> dict:
    seg = {"teams": [{"id": t["id"], "side": seg_sides.get(t["id"]) if seg_sides else t.get("side")} for t in teams]}
    return {
        "id": game_id,
        "titleVersion": {"name": "patch-1"},
        "map": {"name": map_name, "bounds": {"min": {"x": -1000, "y": -1000}, "max": {"x": 1000, "y": 1000}}},
        "teams": teams,
        "segments": [seg],
    }


def full_state_event(evt_type: str, *, game: dict, occurred_at: datetime, target_id: str | None = None) -> tuple[str, dict]:
    # Wrap the provided game into seriesState (full state) and seriesStateDelta for id detection
    e = {
        "type": evt_type,
        "includesFullState": True,
        "seriesState": {"games": [game]},
        "seriesStateDelta": {"games": [{"id": game.get("id")}]},
        "actor": {},
        "target": {"id": target_id} if target_id else {},
        "action": "",
    }
    return iso(occurred_at), e


def delta_event(evt_type: str, *, game_id: str, occurred_at: datetime, actor: dict | None = None,
                target: dict | None = None, event_id: str | None = None, action: str = "") -> tuple[str, dict]:
    e = {
        "id": event_id or f"{evt_type}-{occurred_at.timestamp()}",
        "type": evt_type,
        "includesFullState": False,
        "seriesState": {},
        "seriesStateDelta": {"games": [{"id": game_id}]},
        "actor": actor or {},
        "target": target or {},
        "action": action,
    }
    return iso(occurred_at), e


def series_started_game(game_id: str, when: datetime) -> tuple[str, dict]:
    return iso(when), {"type": "series-started-game", "actor": {}, "target": {"id": game_id}, "action": ""}


def grid_started_feed(when: datetime) -> tuple[str, dict]:
    return iso(when), {"type": "grid-started-feed", "actor": {}, "target": {}, "action": ""}

