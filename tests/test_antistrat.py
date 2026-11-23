"""Tests for turning insights into game-plan suggestions (hand-made insights, no data)."""
import re

from opscope.analytics.antistrat import counter, game_plan, warning
from opscope.analytics.insights import Insight


def plain(html: str) -> str:
    return re.sub("<[^>]+>", "", html)


def ins(category, side="defender", map_name="lotus", score=1.0, **tags):
    return Insight(category=category, map=map_name, side=side, text="", k=12, n=20, unit="rounds",
                   league=(20, 100), score=score, tags=tags)


def test_their_defense_becomes_your_attack_and_vice_versa():
    op = counter(ins("Operator", side="defender", weapon="operator", label="Operator", direction="more",
                     player="OXY", area="A Main"))
    assert "when you attack Lotus" in plain(op.headline) and "A Main" in plain(op.headline) and "OXY" in op.headline
    plant = counter(ins("Attack", side="attacker", site="B site", direction="more"))
    assert "when you defend Lotus" in plain(plant.headline) and "B site" in plain(plant.headline)


def test_odin_advice_depends_on_side():
    vs_def = counter(ins("Operator", side="defender", weapon="odin", label="Odin", direction="more"))
    vs_atk = counter(ins("Operator", side="attacker", weapon="odin", label="Odin", direction="more"))
    assert "cross smokes" in vs_def.detail and "behind your smokes" in vs_atk.detail


def test_rarely_buys_the_gun_means_long_angles_are_safer():
    s = counter(ins("Operator", side="defender", weapon="operator", label="Operator", direction="less"))
    assert "Long angles" in s.headline and "12 of 20 rounds" in s.detail and "other teams: 20%" in s.detail


def test_utility_counters_by_class():
    base = dict(player="neT", ability="sonic-sensor", area="B Site")
    assert "Clear" in counter(ins("Utility", util_class="trap", **base)).headline
    assert "Expect" in counter(ins("Utility", util_class="recon", **base)).headline
    assert "Read their round" in counter(ins("Utility", util_class="smoke", **base)).headline
    assert "Sonic Sensor" in counter(ins("Utility", util_class="trap", **base)).headline


def test_every_suggestion_cites_its_sample():
    for s in game_plan([ins("Attack", side="attacker", site="A site"),
                        ins("Utility", util_class="trap", player="x", ability="trapwire")], self_scout=False):
        assert "12 of 20 rounds" in s.detail


def test_game_plan_keeps_order_and_one_per_map_side_category():
    items = [ins("Attack", side="attacker", site="A site", score=0.9),
             ins("Attack", side="attacker", site="B site", score=0.5),   # same map/side/category: dropped
             ins("Attack", side="attacker", site="A site", map_name="haven", score=0.4)]
    plan = game_plan(items, self_scout=False)
    assert [plain(s.headline) for s in plan] == ["Lean toward A site when you defend Lotus",
                                                 "Lean toward A site when you defend Haven"]


def test_self_scout_turns_tendencies_into_warnings():
    w = warning(ins("Utility", side="attacker", util_class="trap", player="Xeppaa", ability="shear", area="A Main"))
    assert "predictable" in w.headline and "Xeppaa" in w.headline and "12 of 20" in w.detail


def test_game_plan_skips_former_players_unless_asked():
    gone = ins("Utility", util_class="trap", player="FNS", ability="nanoswarm", score=0.9)
    gone.departed = "not on the roster after Stage 1 2025"
    here = ins("Utility", util_class="trap", player="Ethan", ability="trapwire", map_name="haven", score=0.5)
    assert [s.evidence.tags["player"] for s in game_plan([gone, here], self_scout=False)] == ["Ethan"]
    assert len(game_plan([gone, here], self_scout=False, include_departed=True)) == 2


def test_suggestions_name_the_comparison_group():
    i = ins("Attack", side="attacker", site="B site")
    i.peers = "other VCT 2025 teams"
    assert "other VCT 2025 teams: 20%" in counter(i).detail
