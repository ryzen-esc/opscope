"""Parse one GRID VALORANT series feed into tidy rows.

One streaming pass. Full-state events (round start, freeze start/end, plant, round end) give
loadouts, sides and position snapshots; player events give engagements and ability casts.
Times are stored as UTC epoch seconds; `t` (seconds since freeze end) is filled in after the pass,
because buy-phase events happen before their round's freeze end is known.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime

from opscope.taxonomy import primary_weapon, shield, sidearm

TABLES = ("games", "rounds", "loadouts", "engagements", "casts", "snapshots")


def ts(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def _round_num(round_id: str) -> int | None:
    # GRID round ids look like "round-7"
    try:
        return int(round_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return None


def _pos(state: dict | None) -> tuple[float | None, float | None]:
    p = ((state or {}).get("game") or {}).get("position") or {}
    return p.get("x"), p.get("y")


class SeriesParser:
    def __init__(self, series_id: str):
        self.series_id = series_id
        self.rows: dict[str, list[dict]] = {t: [] for t in TABLES}
        self.report: Counter = Counter()
        self.rolled_back_games: set[str] = set()
        self.game_id: str | None = None
        self.round_num: dict[str, int] = {}          # game_id -> current round number
        self.round_closed: dict[str, bool] = {}      # game_id -> current round already ended
        self.rounds: dict[tuple[str, int], dict] = {}
        self.games: dict[str, dict] = {}
        self.agents: dict[tuple[str, str], str] = {}  # (game_id, player_id) -> agent
        self.teams: dict[tuple[str, str], str] = {}   # (game_id, player_id) -> team_id
        self.session = 0
        # GRID rollbacks ("!" actions) undo earlier events newest-first, with new event ids.
        # Each handled event pushes an undo record keyed by (type, actor id, target id).
        self.undo_stack: list[tuple[tuple, dict]] = []
        self._touched: list[tuple[dict, dict]] = []   # (row, old values) changed in place by a handler

    # ---- helpers -------------------------------------------------------------------------
    def _game_state(self, event: dict) -> dict | None:
        games = (event.get("seriesState") or {}).get("games") or []
        if not games:
            return None
        if self.game_id:
            for g in games:
                if g.get("id") == self.game_id:
                    return g
        return games[-1]

    def _event_game_id(self, event: dict) -> str | None:
        for g in (event.get("seriesStateDelta") or {}).get("games") or []:
            if g.get("id"):
                return g["id"]
        return self.game_id

    def _round(self, game_id: str, num: int) -> dict:
        key = (game_id, num)
        if key not in self.rounds:
            self.rounds[key] = {
                "series_id": self.series_id, "game_id": game_id, "round_num": num,
                "start_at": None, "fs_at": None, "fe_at": None, "won_at": None, "end_at": None,
                "plant_at": None, "planter_id": None, "atk_team_id": None, "def_team_id": None,
                "winner_team_id": None, "win_type": None,
                "atk_loadout": None, "def_loadout": None, "atk_money": None, "def_money": None,
            }
        return self.rounds[key]

    def _register_game(self, game: dict) -> None:
        gid = game.get("id")
        if not gid or gid in self.games:
            return
        m = game.get("map") or {}
        b = m.get("bounds") or {}
        self.games[gid] = {
            "series_id": self.series_id, "game_id": gid, "session": self.session,
            "map": m.get("name"), "patch": (game.get("titleVersion") or {}).get("name"),
            "min_x": (b.get("min") or {}).get("x"), "min_y": (b.get("min") or {}).get("y"),
            "max_x": (b.get("max") or {}).get("x"), "max_y": (b.get("max") or {}).get("y"),
        }

    def _snapshot(self, game: dict, gid: str, num: int, moment: str) -> None:
        for team in game.get("teams") or []:
            for p in team.get("players") or []:
                pos = p.get("position") or {}
                agent = (p.get("character") or {}).get("id")
                if agent:
                    self.agents[(gid, p.get("id"))] = agent
                self.rows["snapshots"].append({
                    "series_id": self.series_id, "game_id": gid, "round_num": num, "moment": moment,
                    "player_id": p.get("id"), "team_id": team.get("id"), "side": team.get("side"),
                    "alive": p.get("alive"), "x": pos.get("x"), "y": pos.get("y"),
                })

    def _phase(self, gid: str, num: int) -> str:
        if self.round_closed.get(gid):
            return "post"
        return "live" if self.rounds.get((gid, num), {}).get("fe_at") is not None else "buy"

    # ---- main loop -----------------------------------------------------------------------
    def feed(self, envelopes: Iterable[tuple[str, dict]]) -> None:
        for occurred_at, event in envelopes:
            self.handle(ts(occurred_at) if occurred_at else None, event)

    def handle(self, at: float | None, e: dict) -> None:
        etype = e.get("type", "")
        self.report["events"] += 1
        action = e.get("action") or ""
        if action.startswith("!"):
            self.report[f"rollback:{etype}"] += 1
            if etype == "series-!started-game":
                self._drop_game((e.get("target") or {}).get("id"))
            elif etype.replace("-!", "-", 1) in _HANDLERS:
                self._undo(e)
            return

        if etype == "grid-started-feed":
            self.session += 1
            return
        if etype == "series-started-game":
            self.game_id = (e.get("target") or {}).get("id")
            if self.game_id in self.rolled_back_games:
                self.report["restarted_same_game_id"] += 1
            g = self._game_state(e)
            if g:
                self._register_game(g)
            return

        if e.get("includesFullState"):
            g = self._game_state(e)
            if g:
                self._register_game(g)
                self.game_id = self.game_id or g.get("id")

        handler = _HANDLERS.get(etype)
        if handler:
            before = self._capture(e)
            handler(self, at, e)
            before["touched"], self._touched = self._touched, []
            self.undo_stack.append((self._key(etype, e), before))

    # ---- rollback support ----------------------------------------------------------------
    def _drop_game(self, gid: str | None) -> None:
        """A cancelled map start: drop everything recorded for that attempt.

        Dropping rows now (instead of filtering the id at the end) means a restart that reuses the same
        game id is kept.
        """
        if not gid:
            return
        self.rolled_back_games.add(gid)
        for rows in self.rows.values():
            for row in rows:
                if row.get("game_id") == gid:
                    row["_drop"] = True
        for key in [k for k in self.rounds if k[0] == gid]:
            del self.rounds[key]
        self.games.pop(gid, None)
        self.round_num.pop(gid, None)
        self.round_closed.pop(gid, None)
        if self.game_id == gid:
            self.game_id = None

    @staticmethod
    def _key(etype: str, e: dict) -> tuple:
        return etype, (e.get("actor") or {}).get("id"), (e.get("target") or {}).get("id")

    def _capture(self, e: dict) -> dict:
        """State a handler may change, so the event can be undone later."""
        gid = self.game_id
        keys = {(gid, self.round_num.get(gid or ""))}
        target_round = _round_num((e.get("target") or {}).get("id", ""))
        if target_round is not None:
            keys.add((gid, target_round))
        return {
            "lens": {t: len(rows) for t, rows in self.rows.items()},
            "round_num": dict(self.round_num), "round_closed": dict(self.round_closed),
            "rounds": {k: (dict(self.rounds[k]) if k in self.rounds else None) for k in keys},
        }

    def _undo(self, e: dict) -> None:
        key = self._key(e["type"].replace("-!", "-", 1), e)
        for i in range(len(self.undo_stack) - 1, -1, -1):
            if self.undo_stack[i][0] == key:
                if i != len(self.undo_stack) - 1:
                    self.report["rollback_out_of_order"] += 1
                _, before = self.undo_stack.pop(i)
                break
        else:
            self.report["rollback_unmatched"] += 1
            return
        for table, n in before["lens"].items():
            for row in self.rows[table][n:]:
                row["_drop"] = True
        # Restore round state only for the game(s) this event touched, so an out-of-order undo can't rewind
        # unrelated games. (GRID undoes newest-first, where this is the same as restoring everything.)
        for gid in {k[0] for k in before["rounds"]}:
            for current, saved in ((self.round_num, before["round_num"]), (self.round_closed, before["round_closed"])):
                if gid in saved:
                    current[gid] = saved[gid]
                else:
                    current.pop(gid, None)
        for k, saved in before["rounds"].items():
            if saved is None:
                self.rounds.pop(k, None)
            else:
                self.rounds[k] = saved
        for row, old in before["touched"]:
            row.update(old)
        self.report["rollback_applied"] += 1

    # ---- round structure -----------------------------------------------------------------
    def on_round_start(self, at, e):
        gid = self.game_id
        num = _round_num((e.get("target") or {}).get("id", ""))
        if gid is None or num is None:
            return
        self.round_num[gid] = num
        self.round_closed[gid] = False
        self._round(gid, num)["start_at"] = at

    def on_freeze_start(self, at, e):
        gid, num = self.game_id, self.round_num.get(self.game_id or "")
        if gid is None or num is None:
            return
        self._round(gid, num)["fs_at"] = at
        g = self._game_state(e)
        if g:
            self._snapshot(g, gid, num, "fs")

    def on_freeze_end(self, at, e):
        gid, num = self.game_id, self.round_num.get(self.game_id or "")
        g = self._game_state(e)
        if gid is None or num is None or g is None:
            return
        r = self._round(gid, num)
        r["fe_at"] = at
        # Side per round comes from the current round segment (game-level sides can lag at halftime).
        seg_sides = {}
        segs = g.get("segments") or []
        if segs:
            seg_sides = {t.get("id"): t.get("side") for t in segs[-1].get("teams") or []}
        for team in g.get("teams") or []:
            tid = team.get("id")
            side = seg_sides.get(tid) or team.get("side")
            loadout = sum((p.get("loadoutValue") or 0) for p in team.get("players") or [])
            money = sum((p.get("money") or 0) for p in team.get("players") or [])
            prefix = "atk" if side == "attacker" else "def" if side == "defender" else None
            if prefix:
                r[f"{prefix}_team_id"] = tid
                r[f"{prefix}_loadout"] = loadout
                r[f"{prefix}_money"] = money
            for p in team.get("players") or []:
                pid = p.get("id")
                items = [i.get("id") for i in (p.get("inventory") or {}).get("items") or []]
                agent = (p.get("character") or {}).get("id")
                self.agents[(gid, pid)] = agent
                self.teams[(gid, pid)] = tid
                self.rows["loadouts"].append({
                    "series_id": self.series_id, "game_id": gid, "round_num": num,
                    "player_id": pid, "player_name": p.get("name"), "team_id": tid, "side": side,
                    "agent": agent, "primary_fe": primary_weapon(items), "sidearm_fe": sidearm(items),
                    "shield_fe": shield(items), "money_fe": p.get("money"),
                    "loadout_value": p.get("loadoutValue"),
                    "primary_end": None, "alive_end": None,
                })
        self._snapshot(g, gid, num, "fe")

    def on_plant(self, at, e):
        gid, num = self.game_id, self.round_num.get(self.game_id or "")
        if gid is None or num is None:
            return
        r = self._round(gid, num)
        if r["plant_at"] is None:
            r["plant_at"] = at
            r["planter_id"] = (e.get("actor") or {}).get("id")
            g = self._game_state(e)
            if g:
                self._snapshot(g, gid, num, "plant")

    def on_round_won(self, at, e):
        gid = self.game_id
        num = _round_num((e.get("target") or {}).get("id", "")) or self.round_num.get(gid or "")
        if gid is None or num is None:
            return
        r = self._round(gid, num)
        actor = e.get("actor") or {}
        r["winner_team_id"] = actor.get("id")
        r["won_at"] = at
        r["win_type"] = ((actor.get("stateDelta") or {}).get("round") or {}).get("winType")

    def on_round_end(self, at, e):
        gid = self.game_id
        num = _round_num((e.get("target") or {}).get("id", "")) or self.round_num.get(gid or "")
        g = self._game_state(e)
        if gid is None or num is None:
            return
        self._round(gid, num)["end_at"] = at
        self.round_closed[gid] = True
        if g is None:
            return
        end = {}
        for team in g.get("teams") or []:
            for p in team.get("players") or []:
                items = [i.get("id") for i in (p.get("inventory") or {}).get("items") or []]
                end[p.get("id")] = (primary_weapon(items), p.get("alive"))
        for row in reversed(self.rows["loadouts"]):
            if row["game_id"] != gid or row["round_num"] != num:
                break
            if row["player_id"] in end and not row.get("_drop"):
                self._touched.append((row, {"primary_end": row["primary_end"], "alive_end": row["alive_end"]}))
                row["primary_end"], row["alive_end"] = end[row["player_id"]]

    # ---- player events -------------------------------------------------------------------
    def _ctx(self, e: dict) -> tuple[str | None, int | None]:
        gid = self._event_game_id(e)
        return gid, self.round_num.get(gid or "")

    def on_damage(self, at, e):
        gid, num = self._ctx(e)
        actor, target = e.get("actor") or {}, e.get("target") or {}
        delta = ((actor.get("stateDelta") or {}).get("round") or {})
        sources = delta.get("damageDealtSources") or []
        targets = delta.get("damageDealtTargets") or []
        weapon = (sources[0].get("source") or {}).get("name") if sources else None
        self._engagement("dmg", at, gid, num, e, weapon, delta.get("damageDealt"),
                         any((t.get("target") or {}).get("name") == "head" for t in targets), None)

    def on_kill(self, at, e):
        gid, num = self._ctx(e)
        delta = (((e.get("actor") or {}).get("stateDelta") or {}).get("round") or {})
        kills = delta.get("weaponKills") or {}
        weapon = next(iter(kills), None)
        self._engagement("kill", at, gid, num, e, weapon, None, None, bool(delta.get("firstKill")))

    def _engagement(self, kind, at, gid, num, e, weapon, damage, headshot, first_kill):
        actor, target = e.get("actor") or {}, e.get("target") or {}
        a_state, t_state = actor.get("state") or {}, target.get("state") or {}
        ax, ay = _pos(a_state)
        tx, ty = _pos(t_state)
        self.rows["engagements"].append({
            "series_id": self.series_id, "event_id": e.get("id"), "game_id": gid, "round_num": num,
            "at": at, "phase": self._phase(gid, num), "kind": kind,
            "actor_id": actor.get("id"), "actor_team_id": a_state.get("teamId"), "actor_side": a_state.get("side"),
            "target_id": target.get("id"), "target_team_id": t_state.get("teamId"),
            "weapon": weapon, "damage": damage, "headshot": headshot, "first_kill": first_kill,
            "ax": ax, "ay": ay, "tx": tx, "ty": ty,
        })

    def on_ability(self, at, e):
        gid, num = self._ctx(e)
        actor = e.get("actor") or {}
        state = actor.get("state") or {}
        x, y = _pos(state)
        pid = actor.get("id")
        self.rows["casts"].append({
            "series_id": self.series_id, "event_id": e.get("id"), "game_id": gid, "round_num": num,
            "at": at, "phase": self._phase(gid, num),
            "player_id": pid, "team_id": state.get("teamId"), "side": state.get("side"),
            "agent": self.agents.get((gid, pid)), "ability": (e.get("target") or {}).get("id"),
            "x": x, "y": y, "z": None, "view_x": None, "view_y": None, "view_z": None,
            "pos_source": "grid", "quality": None, "slot": None,
        })

    # ---- finish --------------------------------------------------------------------------
    def finish(self) -> dict[str, list[dict]]:
        dropped: set[str] = set()  # cancelled attempts were already dropped by _drop_game
        for table in self.rows:
            self.rows[table] = [r for r in self.rows[table] if not r.get("_drop")]
        rounds = [r for r in self.rounds.values() if r["game_id"] not in dropped]
        for r in rounds:
            # Restored/replayed games contain bookkeeping rounds with no winner or no live time.
            live = r["winner_team_id"] is not None and r["fe_at"] is not None and r["won_at"] is not None
            r["played"] = live and (r["won_at"] - r["fe_at"]) > 3
        fe = {(r["game_id"], r["round_num"]): r["fe_at"] for r in rounds}
        for r in rounds:
            base = r["fe_at"]
            r["won_t"] = r["won_at"] - base if base and r["won_at"] else None
            r["plant_t"] = r["plant_at"] - base if base and r["plant_at"] else None
            r["buy_len"] = base - r["fs_at"] if base and r["fs_at"] else None
        for table in ("engagements", "casts"):
            for row in self.rows[table]:
                base = fe.get((row["game_id"], row["round_num"]))
                row["t"] = row["at"] - base if base and row["at"] else None
        for row in self.rows["casts"]:
            if row["agent"] is None:
                row["agent"] = self.agents.get((row["game_id"], row["player_id"]))
        out = {"games": [g for g in self.games.values() if g["game_id"] not in dropped], "rounds": rounds}
        for table in ("loadouts", "engagements", "casts", "snapshots"):
            out[table] = [row for row in self.rows[table] if row["game_id"] not in dropped]
        self.report["rolled_back_games"] = len(self.rolled_back_games)
        return out


_HANDLERS = {
    "game-started-round": SeriesParser.on_round_start,
    "round-started-freezetime": SeriesParser.on_freeze_start,
    "round-ended-freezetime": SeriesParser.on_freeze_end,
    "player-completed-plantBomb": SeriesParser.on_plant,
    "team-won-round": SeriesParser.on_round_won,
    "game-ended-round": SeriesParser.on_round_end,
    "player-damaged-player": SeriesParser.on_damage,
    "player-killed-player": SeriesParser.on_kill,
    "player-used-ability": SeriesParser.on_ability,
}


def parse_envelopes(series_id: str, envelopes: Iterable[tuple[str, dict]]) -> tuple[dict[str, list[dict]], Counter]:
    parser = SeriesParser(series_id)
    parser.feed(envelopes)
    return parser.finish(), parser.report
