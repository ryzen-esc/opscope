from __future__ import annotations

import math
from datetime import timedelta

import pytest

from opscope.ingest.feed import parse_envelopes
from opscope.ingest.supplement import index_supplement, join_casts
from tests.fixtures import (
    BASE_TIME,
    make_player, make_team, make_game,
    full_state_event, delta_event,
    series_started_game, grid_started_feed,
)


def _round_id(n: int) -> str:
    return f"round-{n}"


def test_side_flips_at_round_13():
    t0 = BASE_TIME
    game_id = "g1"
    # Teams with base sides (half 1): A attack, B defend
    A, B = "A", "B"
    p1 = make_player("p1", "Alpha", agent="brimstone", money=3000)
    p2 = make_player("p2", "Bravo", agent="sova", money=3000)
    team_a = make_team(A, "attacker", [p1])
    team_b = make_team(B, "defender", [p2])

    # Round 12 freeze end reports current segment sides as A atk, B def
    g12 = make_game(game_id, [team_a, team_b], seg_sides={A: "attacker", B: "defender"})
    env = []
    env.append(grid_started_feed(t0))
    env.append(series_started_game(game_id, t0 + timedelta(seconds=1)))
    env.append(delta_event("game-started-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=2),
                           target={"id": _round_id(12)}))
    env.append(full_state_event("round-started-freezetime", game=g12, occurred_at=t0 + timedelta(seconds=3)))
    env.append(full_state_event("round-ended-freezetime", game=g12, occurred_at=t0 + timedelta(seconds=8)))
    # End/win to close round 12
    env.append(delta_event("team-won-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=40),
                           target={"id": _round_id(12)}, actor={"id": A, "stateDelta": {"round": {"winType": "elims"}}}))
    env.append(full_state_event("game-ended-round", game=g12, occurred_at=t0 + timedelta(seconds=42),
                                target_id=_round_id(12)))

    # Round 13 should flip sides in segments
    g13 = make_game(game_id, [team_a, team_b], seg_sides={A: "defender", B: "attacker"})
    env.append(delta_event("game-started-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=60),
                           target={"id": _round_id(13)}))
    env.append(full_state_event("round-started-freezetime", game=g13, occurred_at=t0 + timedelta(seconds=61)))
    env.append(full_state_event("round-ended-freezetime", game=g13, occurred_at=t0 + timedelta(seconds=66)))
    env.append(delta_event("team-won-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=100),
                           target={"id": _round_id(13)}, actor={"id": B, "stateDelta": {"round": {"winType": "elims"}}}))
    env.append(full_state_event("game-ended-round", game=g13, occurred_at=t0 + timedelta(seconds=102),
                                target_id=_round_id(13)))

    rows, _ = parse_envelopes("s1", env)
    r12 = next(r for r in rows["rounds"] if r["round_num"] == 12)
    r13 = next(r for r in rows["rounds"] if r["round_num"] == 13)
    assert r12["atk_team_id"] == A and r12["def_team_id"] == B
    assert r13["atk_team_id"] == B and r13["def_team_id"] == A


def test_round_time_and_buy_phase_negative_t_and_buy_len():
    t0 = BASE_TIME
    game_id = "g2"
    A, B = "A", "B"
    # Build simple game
    pA = make_player("pa", "Alpha", agent="sova", money=2000, x=0, y=0)
    pB = make_player("pb", "Bravo", agent="viper", money=2000, x=10, y=10)
    team_a = make_team(A, "attacker", [pA])
    team_b = make_team(B, "defender", [pB])
    game = make_game(game_id, [team_a, team_b], seg_sides={A: "attacker", B: "defender"})

    env = []
    env.append(grid_started_feed(t0))
    env.append(series_started_game(game_id, t0 + timedelta(seconds=1)))
    env.append(delta_event("game-started-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=2),
                           target={"id": _round_id(1)}))
    # Freeze start full state
    fs_at = t0 + timedelta(seconds=3)
    env.append(full_state_event("round-started-freezetime", game=game, occurred_at=fs_at))
    # Buy phase cast before freeze end (t should be negative)
    buy_cast_at = t0 + timedelta(seconds=5)
    env.append(delta_event("player-used-ability", game_id=game_id, occurred_at=buy_cast_at,
                           actor={"id": "pa", "state": {"teamId": A, "side": "attacker", "game": {"position": {"x": 0, "y": 0}}}},
                           target={"id": "sova.recon-bolt"}, event_id="E-buy"))
    # Freeze end full state
    fe_at = t0 + timedelta(seconds=10)
    env.append(full_state_event("round-ended-freezetime", game=game, occurred_at=fe_at))
    # Live cast after FE (t should be positive)
    live_cast_at = t0 + timedelta(seconds=15)
    env.append(delta_event("player-used-ability", game_id=game_id, occurred_at=live_cast_at,
                           actor={"id": "pa", "state": {"teamId": A, "side": "attacker", "game": {"position": {"x": 1, "y": 1}}}},
                           target={"id": "sova.recon-bolt"}, event_id="E-live"))
    # Win/end
    env.append(delta_event("team-won-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=30),
                           target={"id": _round_id(1)}, actor={"id": A, "stateDelta": {"round": {"winType": "elims"}}}))
    env.append(full_state_event("game-ended-round", game=game, occurred_at=t0 + timedelta(seconds=32),
                                target_id=_round_id(1)))

    rows, _ = parse_envelopes("s2", env)
    rounds = rows["rounds"]
    r1 = next(r for r in rounds if r["round_num"] == 1)
    assert math.isclose(r1["buy_len"], (fe_at - fs_at).total_seconds(), rel_tol=0, abs_tol=1e-6)

    casts = sorted(rows["casts"], key=lambda c: c["event_id"])  # E-buy then E-live
    t_buy = next(c for c in casts if c["event_id"] == "E-buy")["t"]
    t_live = next(c for c in casts if c["event_id"] == "E-live")["t"]
    assert t_buy < 0  # negative in buy phase
    assert t_live > 0  # positive in live


def test_operator_detected_at_freeze_end_and_round_end():
    t0 = BASE_TIME
    game_id = "g3"
    A, B = "A", "B"
    # p1 has an Operator at FE; p2 gets an Operator by round end
    p1 = make_player("p1", "Opper", items=["operator"], money=4700)
    p2 = make_player("p2", "Rifle", items=["vandal"], money=2900)
    team_a = make_team(A, "attacker", [p1])
    team_b = make_team(B, "defender", [p2])

    game_fe = make_game(game_id, [team_a, team_b], seg_sides={A: "attacker", B: "defender"})
    # At round end, p2's inventory changes to Operator
    p2_end = make_player("p2", "Rifle", items=["operator"], money=0)
    team_b_end = make_team(B, "defender", [p2_end])
    game_end = make_game(game_id, [team_a, team_b_end], seg_sides={A: "attacker", B: "defender"})

    env = []
    env.append(series_started_game(game_id, t0))
    env.append(delta_event("game-started-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=1),
                           target={"id": _round_id(1)}))
    env.append(full_state_event("round-started-freezetime", game=game_fe, occurred_at=t0 + timedelta(seconds=2)))
    env.append(full_state_event("round-ended-freezetime", game=game_fe, occurred_at=t0 + timedelta(seconds=6)))
    env.append(delta_event("team-won-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=25),
                           target={"id": _round_id(1)}, actor={"id": A, "stateDelta": {"round": {"winType": "elims"}}}))
    env.append(full_state_event("game-ended-round", game=game_end, occurred_at=t0 + timedelta(seconds=26),
                                target_id=_round_id(1)))

    rows, _ = parse_envelopes("s3", env)
    # Freeze-end loadouts should show p1 primary_fe operator
    loads = rows["loadouts"]
    r_load_p1 = next(l for l in loads if l["player_id"] == "p1")
    assert r_load_p1["primary_fe"] == "operator"
    # Round end should reflect p2 having operator now
    r_load_p2 = next(l for l in loads if l["player_id"] == "p2")
    assert r_load_p2["primary_end"] == "operator"


def test_rollback_undo_kill_and_undo_round():
    t0 = BASE_TIME
    game_id = "g4"
    A, B = "A", "B"

    # Minimal game for FE so that engagements get phase/live
    pA = make_player("pa", "Alpha", x=0, y=0)
    pB = make_player("pb", "Bravo", x=5, y=5)
    team_a = make_team(A, "attacker", [pA])
    team_b = make_team(B, "defender", [pB])
    game = make_game(game_id, [team_a, team_b], seg_sides={A: "attacker", B: "defender"})

    env = []
    env.append(series_started_game(game_id, t0))
    # Round 1
    env.append(delta_event("game-started-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=1),
                           target={"id": _round_id(1)}))
    env.append(full_state_event("round-started-freezetime", game=game, occurred_at=t0 + timedelta(seconds=2)))
    env.append(full_state_event("round-ended-freezetime", game=game, occurred_at=t0 + timedelta(seconds=4)))

    # A kills B (create one engagement row)
    kill_at = t0 + timedelta(seconds=10)
    kill_actor = {"id": "pa", "state": {"teamId": A, "side": "attacker", "game": {"position": {"x": 0, "y": 0}}},
                  "stateDelta": {"round": {"weaponKills": {"vandal": 1}, "firstKill": True}}}
    kill_target = {"id": "pb", "state": {"teamId": B, "side": "defender", "game": {"position": {"x": 5, "y": 5}}}}
    env.append(delta_event("player-killed-player", game_id=game_id, occurred_at=kill_at,
                           actor=kill_actor, target=kill_target, event_id="K1"))

    # Roll back the kill
    env.append(delta_event("player-!killed-player", game_id=game_id, occurred_at=kill_at + timedelta(milliseconds=500),
                           actor={"id": "pa"}, target={"id": "pb"}, action="!undo"))

    # Now roll back the entire round start (drops round + any rows within)
    env.append(delta_event("game-!started-round", game_id=game_id, occurred_at=t0 + timedelta(seconds=20),
                           target={"id": _round_id(1)}, action="!undo"))

    rows, report = parse_envelopes("s4", env)

    # Kill should be undone: no engagements
    assert rows["engagements"] == []
    # Round should be undone: no rounds/loadouts/snapshots either
    assert rows["rounds"] == []
    assert rows["loadouts"] == []
    assert rows["snapshots"] == []
    # And an applied rollback was recorded at least twice
    assert report["rollback_applied"] >= 2


def test_supplement_casts_join_by_event_id():
    # Build a simple cast row with GRID-provided x/y and an event id
    casts = [{
        "series_id": "s5", "event_id": "E1", "game_id": "g5", "round_num": 1,
        "at": BASE_TIME.timestamp(), "phase": "live",
        "player_id": "p1", "team_id": "A", "side": "attacker", "agent": "sova",
        "ability": "sova.recon-bolt",
        "x": 0.0, "y": 0.0, "z": None,
        "view_x": None, "view_y": None, "view_z": None,
        "pos_source": "grid", "quality": None, "slot": None,
    }]

    # A synthetic supplement that references the same grid_event_id and has high quality with precise 3D
    supplement_records = [{
        "grid_event_id": "E1", "in_grid": True, "slot": "e", "quality": "ok",
        "interpolated": {"position": {"x": 12.3, "y": 45.6, "z": 1.2}, "view": {"x": 1.0, "y": 2.0, "z": 3.0}},
    }]

    sup_index = index_supplement(supplement_records)
    matched = join_casts(casts, sup_index)
    assert matched == 1
    cast = casts[0]
    assert cast["pos_source"] == "supplement"
    assert cast["x"] == pytest.approx(12.3)
    assert cast["y"] == pytest.approx(45.6)
    assert cast["z"] == pytest.approx(1.2)
    assert cast["view_x"] == pytest.approx(1.0)
    assert cast["slot"] == "e"


# ---- Added in review (Claude Code): the cases that bit us on real data ----------------------------

def _round(env, game, game_id, n, start, *, kill_id=None, finish=True):
    """Append one round: start, freeze start/end, optional kill, optional win + end."""
    env.append(delta_event("game-started-round", game_id=game_id, occurred_at=start, target={"id": _round_id(n)}))
    env.append(full_state_event("round-started-freezetime", game=game, occurred_at=start + timedelta(seconds=1)))
    env.append(full_state_event("round-ended-freezetime", game=game, occurred_at=start + timedelta(seconds=30)))
    if kill_id:
        env.append(delta_event(
            "player-killed-player", game_id=game_id, occurred_at=start + timedelta(seconds=45), event_id=kill_id,
            actor={"id": "pa", "state": {"teamId": "A", "side": "attacker", "game": {"position": {"x": 0, "y": 0}}},
                   "stateDelta": {"round": {"weaponKills": {"operator": 1}}}},
            target={"id": "pb", "state": {"teamId": "B", "side": "defender", "game": {"position": {"x": 5, "y": 5}}}}))
    if finish:
        env.append(delta_event("team-won-round", game_id=game_id, occurred_at=start + timedelta(seconds=60),
                               target={"id": _round_id(n)}, actor={"id": "A", "stateDelta": {"round": {"winType": "x"}}}))
        env.append(full_state_event("game-ended-round", game=game, occurred_at=start + timedelta(seconds=61),
                                    target_id=_round_id(n)))


def test_rollback_then_replay_keeps_only_the_replayed_round():
    """GRID undoes a round newest-first with new event ids, then the round is replayed.

    On real data this produced an extra round in 35 games until the parser learned to undo.
    """
    t0, game_id = BASE_TIME, "g6"
    old = make_game(game_id, [make_team("A", "attacker", [make_player("pa", "Alpha", items=["operator"])]),
                              make_team("B", "defender", [make_player("pb", "Bravo", items=["vandal"])])])
    new = make_game(game_id, [make_team("A", "attacker", [make_player("pa", "Alpha", items=["phantom"])]),
                              make_team("B", "defender", [make_player("pb", "Bravo", items=["vandal"])])])
    env = [series_started_game(game_id, t0)]
    _round(env, old, game_id, 1, t0 + timedelta(seconds=1), kill_id="K-old", finish=False)
    undo_at = t0 + timedelta(seconds=120)
    for etype, actor, target in [  # newest first, like GRID
        ("player-!killed-player", {"id": "pa"}, {"id": "pb"}),
        ("round-!ended-freezetime", {}, {}),
        ("round-!started-freezetime", {}, {}),
        ("game-!started-round", {}, {"id": _round_id(1)}),
    ]:
        env.append(delta_event(etype, game_id=game_id, occurred_at=undo_at, actor=actor, target=target,
                               action="!" + etype.split("-!")[1].split("-")[0]))
    _round(env, new, game_id, 1, t0 + timedelta(seconds=130), kill_id="K-new")

    rows, report = parse_envelopes("s6", env)
    assert [r["round_num"] for r in rows["rounds"]] == [1]
    assert rows["rounds"][0]["winner_team_id"] == "A" and rows["rounds"][0]["played"]
    assert [e["event_id"] for e in rows["engagements"]] == ["K-new"]
    pa = [l for l in rows["loadouts"] if l["player_id"] == "pa"]
    assert [l["primary_fe"] for l in pa] == ["phantom"]  # the rolled-back Op buy is gone
    assert report["rollback_applied"] == 4 and report.get("rollback_unmatched", 0) == 0


def test_rolled_back_game_is_dropped_entirely():
    t0 = BASE_TIME
    game = make_game("g-old", [make_team("A", "attacker", [make_player("pa", "Alpha")]),
                               make_team("B", "defender", [make_player("pb", "Bravo")])])
    env = [series_started_game("g-old", t0)]
    _round(env, game, "g-old", 1, t0 + timedelta(seconds=1))
    env.append((env[-1][0], {"type": "series-!started-game", "action": "!started",
                             "actor": {}, "target": {"id": "g-old"}}))
    rows, report = parse_envelopes("s7", env)
    assert rows["rounds"] == [] and rows["games"] == [] and rows["loadouts"] == []
    assert report["rolled_back_games"] == 1


def test_supplement_skips_casts_not_in_grid_and_handles_quality_flags():
    def cast(eid):
        return {"event_id": eid, "x": 1.0, "y": 1.0, "z": None, "view_x": None, "view_y": None, "view_z": None,
                "pos_source": "grid", "quality": None, "slot": None}

    frame = lambda off, x: {"offset_ms": off, "position": {"x": x, "y": 0, "z": 0}, "view": {"x": 1, "y": 0, "z": 0}}
    records = [
        # between-rounds cast: not in GRID, must be ignored
        {"grid_event_id": None, "in_grid": False, "quality": "ok", "interpolated": frame(0, 99)},
        # caster died right after casting: use the closer frame (+40 ms), not the interpolation
        {"grid_event_id": "GAP", "in_grid": True, "quality": "gap_exceeded", "slot": "ABILITY_1",
         "frame_before": frame(-900, 10), "frame_after": frame(40, 20), "interpolated": frame(0, 15)},
        # no movement frames at all: keep GRID's own position but record the quality
        {"grid_event_id": "NONE", "in_grid": True, "quality": "missing_both", "slot": "GRENADE", "interpolated": None},
    ]
    casts = [cast("GAP"), cast("NONE"), cast("UNMATCHED")]
    assert join_casts(casts, index_supplement(records)) == 2
    gap, none, unmatched = casts
    assert gap["x"] == 20 and gap["pos_source"] == "supplement"
    assert none["x"] == 1.0 and none["pos_source"] == "grid" and none["quality"] == "missing_both"
    assert unmatched["pos_source"] == "grid" and unmatched["quality"] is None


def test_restart_under_the_same_game_id_keeps_the_replay():
    """A cancelled map start drops that attempt; a restart reusing the same id must survive."""
    t0 = BASE_TIME
    game = make_game("g-same", [make_team("A", "attacker", [make_player("pa", "Alpha", items=["operator"])]),
                                make_team("B", "defender", [make_player("pb", "Bravo")])])
    env = [series_started_game("g-same", t0)]
    _round(env, game, "g-same", 1, t0 + timedelta(seconds=1), kill_id="K-first")
    env.append((env[-1][0], {"type": "series-!started-game", "action": "!started", "actor": {}, "target": {"id": "g-same"}}))
    env.append(series_started_game("g-same", t0 + timedelta(seconds=300)))
    _round(env, game, "g-same", 1, t0 + timedelta(seconds=301), kill_id="K-replay")
    rows, report = parse_envelopes("s8", env)
    assert [e["event_id"] for e in rows["engagements"]] == ["K-replay"]
    assert len(rows["rounds"]) == 1 and len(rows["games"]) == 1
    assert report["restarted_same_game_id"] == 1


def test_out_of_order_undo_does_not_rewind_other_games():
    """Undoing an old event of game 1 must not reset game 2's current round."""
    t0 = BASE_TIME
    g1 = make_game("g1", [make_team("A", "attacker", [make_player("pa", "Alpha")]), make_team("B", "defender", [make_player("pb", "Bravo")])])
    g2 = make_game("g2", [make_team("A", "attacker", [make_player("pa", "Alpha")]), make_team("B", "defender", [make_player("pb", "Bravo")])])
    env = [series_started_game("g1", t0)]
    _round(env, g1, "g1", 1, t0 + timedelta(seconds=1), kill_id="K1")
    env.append(series_started_game("g2", t0 + timedelta(seconds=100)))
    _round(env, g2, "g2", 1, t0 + timedelta(seconds=101), finish=False)
    # A late correction of game 1's kill (not the newest event)...
    env.append(delta_event("player-!killed-player", game_id="g1", occurred_at=t0 + timedelta(seconds=140),
                           actor={"id": "pa"}, target={"id": "pb"}, action="!killed"))
    # ...then game 2 continues: this kill must still land in g2 round 1
    env.append(delta_event("player-killed-player", game_id="g2", occurred_at=t0 + timedelta(seconds=150), event_id="K2",
                           actor={"id": "pa", "state": {"teamId": "A", "side": "attacker", "game": {"position": {"x": 0, "y": 0}}},
                                  "stateDelta": {"round": {"weaponKills": {"vandal": 1}}}},
                           target={"id": "pb", "state": {"teamId": "B", "side": "defender", "game": {"position": {"x": 1, "y": 1}}}}))
    rows, report = parse_envelopes("s9", env)
    kills = {e["event_id"]: (e["game_id"], e["round_num"]) for e in rows["engagements"]}
    assert "K1" not in kills and kills["K2"] == ("g2", 1)
    assert report["rollback_out_of_order"] == 1
