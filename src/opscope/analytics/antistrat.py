"""Turn scouting insights into suggestions a coach can act on.

Two modes:
- Opponent: "Game plan vs X". Each tendency becomes a counter, written from Cloud9's side (their defense is
  your attack and vice versa).
- Self-scout: "Predictability check". Each tendency is something opponents scouting Cloud9 will also see.

Suggestions are deliberately rule-based and short: every one cites the insight (and sample) it came from,
so a coach can judge it rather than trust a black box. They are prompts for prep, not orders.
"""
from __future__ import annotations

from dataclasses import dataclass

from opscope.analytics.insights import Insight, pretty

YOUR_SIDE = {"defender": "attack", "attacker": "defense"}  # their side -> the side you play against it
YOU_VERB = {"defender": "attack", "attacker": "defend"}     # "...when you attack/defend Lotus"


@dataclass
class Suggestion:
    headline: str   # short imperative, HTML allowed
    detail: str     # one sentence of how/why, HTML allowed
    evidence: Insight

    @property
    def phase(self) -> str:
        return YOUR_SIDE.get(self.evidence.side, "")


def _near(tags: dict) -> str:
    return f" near <b>{tags['area']}</b>" if tags.get("area") else ""


def counter(ins: Insight) -> Suggestion | None:
    """Opponent mode: what to do against this tendency."""
    t, m = ins.tags, ins.map.title()
    you = YOU_VERB.get(ins.side, "")
    if ins.category == "Operator":
        gun = t.get("label", "Operator")
        if t.get("direction") == "more":
            if t.get("weapon") == "odin":
                how = ("Don't cross smokes there without cutting the angle; wall or flash it first."
                       if ins.side == "defender" else
                       "Don't hold tight angles just behind your smokes there; the Odin sprays through them.")
                return Suggestion(f"Expect Odin spam{_near(t)} when you {you} {m}",
                                  f"They bring an Odin in {ins.sample}. {how}", ins)
            who = f" ({t['player']})" if t.get("player") else ""
            return Suggestion(
                f"Respect the {gun}{who}{_near(t)} when you {you} {m}",
                f"It's bought in {ins.sample} ({ins.peers}: {ins.league_rate:.0%}). Don't dry-peek that angle: "
                f"flash or smoke it before taking space, or hit away from it.", ins)
        if ins.side == "defender":
            return Suggestion(
                f"Long angles are cheaper when you attack {m}",
                f"Their defense rarely has a {gun} ({ins.sample}, {ins.peers}: {ins.league_rate:.0%}), "
                f"so rifles can take long duels with less risk.", ins)
        return Suggestion(
            f"Hold long angles with confidence when you defend {m}",
            f"They rarely bring a {gun} on attack ({ins.sample}, {ins.peers}: {ins.league_rate:.0%}).", ins)

    if ins.category == "Attack":
        site = t.get("site", "that site")
        return Suggestion(
            f"Lean toward <b>{site}</b> when you defend {m}",
            f"Their attacks end on {site} in {ins.sample} ({ins.peers}: {ins.league_rate:.0%}). Shade an extra player "
            f"or your stall utility there, and plan the retake for {site}.", ins)

    if ins.category == "Utility":
        who, ability, cls = t.get("player", "They"), pretty(t.get("ability", "utility")), t.get("util_class")
        where = _near(t)
        if cls == "trap":
            return Suggestion(f"Clear {who}'s {ability}{where} when you {you} {m}",
                              f"It's in the same spot in {ins.sample}. Shoot it or use utility on it before you walk through, "
                              f"or take a different path.", ins)
        if cls == "recon":
            return Suggestion(f"Expect {who}'s {ability}{where} when you {you} {m}",
                              f"Same spot in {ins.sample}. Play an off-angle or break line of sight early so it reveals nothing.", ins)
        if cls == "smoke":
            return Suggestion(f"Read their round from {who}'s {ability}{where} on {m}",
                              f"It's thrown from the same spot in {ins.sample}. When you see it, you know the setup is starting; "
                              f"have utility ready to punish it.", ins)
        return Suggestion(f"Expect {who}'s {ability}{where} when you {you} {m}",
                          f"Same spot in {ins.sample}. Pre-position away from it instead of reacting.", ins)
    return None


def warning(ins: Insight) -> Suggestion:
    """Self-scout mode: opponents scouting us will see the same thing."""
    t, m = ins.tags, ins.map.title()
    side = {"attacker": "attack", "defender": "defense"}.get(ins.side, "")
    if ins.category == "Utility":
        head = f"{t.get('player', 'A player')}'s {pretty(t.get('ability', 'utility'))}{_near(t)} on {m} {side} is predictable"
        tip = "Have a second spot ready for the rounds that matter."
    elif ins.category == "Attack":
        head = f"Attacks on {m} end on <b>{t.get('site')}</b> unusually often"
        tip = "A team that scouts this can stack it; mix in more of the other site."
    elif t.get("direction") == "more":
        head = f"The {t.get('label', 'Operator')}{_near(t)} on {m} {side} is easy to expect"
        tip = "Rotate the setup spot so opponents can't pre-clear it."
    else:
        head = f"Opponents know you rarely buy the {t.get('label', 'Operator')} on {m} {side}"
        tip = "Expect them to take long duels; a surprise buy can punish it."
    return Suggestion(head, f"{ins.sample}" + (f" ({ins.peers}: {ins.league_rate:.0%})" if ins.league_rate is not None else "")
                      + f". {tip}", ins)


def game_plan(insights: list[Insight], self_scout: bool, limit: int = 8,
              include_departed: bool = False) -> list[Suggestion]:
    """Best-first suggestions, at most one per (map, side, category) so one map can't fill the list.

    Insights about players no longer on the team's latest roster are skipped unless asked for: their
    tendencies are real but may not apply to the team you'll actually face.
    """
    out, seen = [], set()
    for ins in insights:
        if ins.departed and not include_departed:
            continue
        key = (ins.map, ins.side, ins.category, ins.tags.get("ability"))
        if key in seen:
            continue
        s = warning(ins) if self_scout else counter(ins)
        if s:
            out.append(s)
            seen.add(key)
        if len(out) >= limit:
            break
    return out
