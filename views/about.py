"""How it works: what the numbers mean, where they come from, and where they stop being reliable."""
import json

import streamlit as st

from opscope.analytics.landing import landing_model
from opscope.analytics.stats import MIN_SAMPLE
from opscope.analytics.utility import SPOT_RADIUS_CM
from opscope.ingest.build import cache_dir
from opscope.ui.cards import stat_card
from opscope.zones import SITE_RADIUS_CM

st.title("How it works")
st.markdown("OpScope reads every recorded event of professional VALORANT matches and turns them into "
            "scouting a coach can check: **every number shows the rounds behind it**, and every tendency is "
            "compared with other teams in the same tier and season.")

report_path = cache_dir() / "ingest_report.json"
rep = json.loads(report_path.read_text()) if report_path.exists() else {}
rows, totals = rep.get("table_rows", {}), rep.get("totals", {})
if rows:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_card("Series read", f"{rep.get('built_series', 0):,}", f"{totals.get('events', 0):,} events")
    with c2:
        stat_card("Rounds", f"{rows.get('rounds', 0):,}", f"{rows.get('games', 0):,} maps, all matching official scores")
    with c3:
        stat_card("Ability casts", f"{rows.get('casts', 0):,}",
                  f"{totals.get('casts_supplemented', 0) / max(rows.get('casts', 1), 1):.1%} with precise positions")
    with c4:
        stat_card("Corrections applied", f"{totals.get('rollback_applied', 0):,}",
                  f"undone events, incl. {totals.get('rolled_back_games', 0)} cancelled map starts")

st.header("Reading a card")
st.markdown(f"""
- **"48 of 64 rounds"** is the evidence: how often it happened and out of how many chances.
- **Typical team** ("typical VCT 2025 team", etc.) is the median of every other team's own rate in the **same tier and season**, on the same map and side. Tiers and seasons play different metas, so they aren't mixed (a team that played two seasons is compared season by season), and using the median means one extreme team can't move it.
- **Rosters:** each team's latest roster in the data is shown on the report. Tendencies about players who later left are marked and left out of the game plan.
- **95% range** is how far the true rate could plausibly be from what we saw, given the sample (a Wilson interval).
  Small samples give wide ranges.
- A **tendency** is only listed when that range does not overlap the league rate, and it needs at least
  {MIN_SAMPLE} rounds. Percentages on fewer rounds are hidden ("too few to call").
- Tendencies are **ranked** by the gap between the range and the league rate, so the top cards are both unusual
  and well supported.
""")

st.header("Where each feature comes from")
with st.expander("Operator profiler", expanded=True):
    st.markdown("""
- **Who has the gun:** the inventory at the end of the buy phase, for every player in every round.
  "Survived with it" uses the inventory at round end.
- **Changing hands:** pickups aren't recorded, so a pickup is inferred when someone who didn't buy the gun
  deals damage with it.
- **Where it sits:** GRID records a player's position only when they shoot, get hit or use an ability, about
  ±1–4 m. Quiet rounds leave gaps, so the map shows a density of every recorded position, filtered by time in
  the round, and always says how many rounds it covers.
- **Setup style:** the first position in the first 30 s, scored from 0 (defender spawn) to 1 (attacker spawn)
  and compared with every other team's setups on that map.
- **Win rate** is compared only within full buys, so eco rounds don't skew it.
""")
with st.expander("Utility profiler"):
    st.markdown(f"""
- **Position:** where the player stood when casting, from the ability supplement, which interpolates
  movement samples taken 5 times a second (once a second in VCT Americas 2025, so a moving player can be a
  few metres off there). **Where utility lands is not recorded**, so thrown utility shows the aim direction instead.
- **Habit spots:** casts within {SPOT_RADIUS_CM // 100} m of each other count as the same spot. A habit is
  counted in *rounds the player was on that agent*, so a rarely played agent can't look like a strong habit.
- **Compared with a typical player:** some utility is always placed the same way (a Viper wall lineup), so a
  habit only becomes a tendency when it is more predictable than the median player with the same ability on
  the same map and side.
""")
with st.expander("Estimated landing spots"):
    try:
        lm = landing_model()
        v = lm["validation"]
        st.markdown(f"""
GRID doesn't record where utility lands, but **damaging** utility leaves evidence: the players it hurts were
standing where it landed.

1. Each molly, nanoswarm, shock dart or similar cast is paired with the damage that same player later did with
   that ability in the round ({lm['pairs']:,} casts). The victims' median position stands in for the landing.
2. Utility lands along the aim (the typical sideways miss is 2–3 m), so the model is just *how far along the aim
   this ability lands for this aim angle* (the median, in 5° bins).
3. Checked on {v['test_series']} matches held out from fitting ({v['test_casts']:,} casts): the typical miss is
   **{v['median_model_m']} m**, against **{v['median_cast_m']} m** for the cast spot and {v['median_fixed_m']} m for
   a fixed distance. The victims' spread inside the area limits how small this check can go.

Estimates are shown only for the {len(lm['model'])} abilities this improves. Smokes, alarmbots, cameras and the like
deal no damage, so they can't be checked, and they stay at the cast spot. **Turrets** do deal damage, but at range:
the players a turret hits stand about 23 m from where it was placed, so their positions say where the enemies were,
not where the turret was. A turret is placed right next to Killjoy, so its cast spot is already a good position.
""")
        st.dataframe(
            [{"Ability": a.replace("-", " ").title(), "Test casts": s["n"], "Miss with cast spot (m)": s["cast"],
              "Miss with estimate (m)": s["model"]} for a, s in sorted(v["abilities"].items())],
            hide_index=True, width="stretch")
    except Exception as exc:  # missing cache etc.: the rest of the page still works
        st.caption(f"Landing model not available yet ({exc}).")
with st.expander("Sites and named areas"):
    st.markdown(f"""
- **Bomb sites** are found by clustering about 29,000 plant positions; sites come out 3–7 m wide.
- **Names** (A Site, B Main, Mid Courtyard…) come from the community API at valorant-api.com, which uses the
  same coordinates as GRID: on all 13 maps, every site matched its official callout within 20 m.
- A position is named after the nearest callout point, and anything within {SITE_RADIUS_CM // 100} m of a site
  centre is named after the site. **The letter (A/B/C/Mid) is reliable; the exact area is a best guess near
  borders**, because each callout is a single point.
""")
with st.expander("Game plan and predictability check"):
    st.markdown("""
- Each ranked tendency becomes one short suggestion, written from your side: their defense is your attack.
- For Cloud9's own rosters, the same tendencies become a **predictability check**: what an opponent scouting
  Cloud9 would see.
- The suggestions follow simple, readable rules and always cite the evidence. They are prompts for preparation,
  not orders.
""")

st.header("Limits worth knowing")
st.markdown("""
- **Landing spots are estimates**, and only for damaging utility. There is **no continuous movement**: positions exist only at events.
- **Rosters change.** Cloud9 (VCT Americas 2025) and Cloud9 GC (Game Changers NA 2026) are separate teams here.
- **Buy types** are by total team loadout: eco under 6,000; full buy at 18,000 and up; rounds 1 and 13 are pistols.
- **The data covers 2025–2026 events** in the hackathon set. Matches GRID didn't record aren't included.
""")

st.header("Built with")
st.markdown("Python 3.14, pandas, Plotly and Streamlit, built in **PyCharm** with **Junie** and **JetBrains AI "
            "Assistant**, and **Claude Code**. Match data © GRID and Riot Games; this project is not endorsed by Riot Games.")
