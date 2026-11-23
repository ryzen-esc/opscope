"""Scouting report: the one page a coach opens before playing a team (or to scout Cloud9 itself)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from opscope.analytics.antistrat import game_plan
from opscope.analytics.insights import map_pool, plant_sites, team_insights
from opscope.analytics.operator import Scope, _filter_rounds, league_scope, team_rounds
from opscope.analytics.roster import latest_roster, lineups_in, short_event
from opscope.analytics.stats import MIN_SAMPLE, of, pct
from opscope.load import CLOUD9_TEAMS, cohort_label, peer_group
from opscope.ui.cards import insight_card, stat_card, suggestion_card
from opscope.ui.filters import sidebar, team_name
from opscope.ui.minimap import add_spots, base_map
from opscope.zones import sites

CATEGORIES = ["All", "Operator", "Utility", "Attack"]


@st.cache_resource(show_spinner="Building the scouting report…")
def insights_for(scope: Scope):
    return team_insights(scope)


f = sidebar()
tid = f["team_id"]
team = team_name(tid)
scope = Scope(team_id=tid, side=None, maps=f["maps"], opponents=f["opponents"], patches=f["patches"], events=f["events"])
who = "Self-scout" if tid in CLOUD9_TEAMS else "Scouting report"
st.title(f"{who}: {team}")
roster = latest_roster(tid)
if roster:
    scope_events = _filter_rounds(team_rounds(), Scope(team_id=tid, side=None, maps=f["maps"], opponents=f["opponents"],
                                                       patches=f["patches"], events=f["events"]))["event"].unique()
    n_lineups = lineups_in(tid, scope_events)
    note = (f" This data covers **{n_lineups} different lineups**; team-wide rates mix them. Filter by Event "
            f"to focus on one. Tendencies about players who later left are marked and kept out of the game plan."
            if n_lineups > 1 else "")
    st.markdown(f"**Roster as of their last match in the data** ({short_event(roster.event)}, {roster.last_match}): "
                f"{', '.join(roster.names)}.{note}")
_cohorts = _filter_rounds(team_rounds(), Scope(team_id=tid, side=None))["cohort"].dropna().unique()
st.caption(f"Tendencies that stand out from other {peer_group(_cohorts)} teams (each season compared with itself), with the "
           f"sample behind each one. Covers both sides; the Side filter applies to the profiler pages.")

pool = map_pool(scope)
if pool.empty:
    st.info("No games match these filters.")
    st.stop()

# ---- headline numbers ---------------------------------------------------------------------------
games, wins = int(pool["games"].sum()), int(pool["wins"].sum())
atk_w, atk_n = int(pool["atk_won"].sum()), int(pool["atk_n"].sum())
def_w, def_n = int(pool["def_won"].sum()), int(pool["def_n"].sum())
c1, c2, c3, c4 = st.columns(4)
with c1:
    stat_card("Maps won", f"{wins}–{games - wins}", of(wins, games, "maps"))
with c2:
    top = pool.iloc[0]
    stat_card("Most played", top["map"].title(), of(int(top["games"]), games, "maps"))
with c3:
    stat_card("Attack rounds won", f"{pct(atk_w, atk_n):.0%}", of(atk_w, atk_n))
with c4:
    stat_card("Defense rounds won", f"{pct(def_w, def_n):.0%}", of(def_w, def_n))

# ---- game plan ------------------------------------------------------------------------------------
items = insights_for(scope)
self_scout = tid in CLOUD9_TEAMS
plan = game_plan(items, self_scout=self_scout, limit=8)
if self_scout:
    st.subheader("Predictability check")
    st.caption("What an opponent scouting this team would see: the habits most worth varying.")
else:
    st.subheader(f"Game plan vs {team}")
    st.caption("Counters to this team's most unusual tendencies, written from your side. Each one cites its evidence; "
               "treat them as prompts for prep, not orders.")
if plan:
    half = (len(plan) + 1) // 2
    pl, pr = st.columns(2)
    for col, chunk, start in ((pl, plan[:half], 1), (pr, plan[half:], half + 1)):
        with col:
            for n, sug in enumerate(chunk, start):
                suggestion_card(sug, n)
else:
    st.info("Nothing stands out from the league strongly enough to plan around yet.")

# ---- key tendencies -------------------------------------------------------------------------------
st.subheader("Key tendencies")
cat = st.segmented_control("Show", CATEGORIES, default="All", key="report_cat") or "All"
shown = [i for i in items if cat == "All" or i.category == cat][:9]
if not shown:
    st.info("Nothing in this category stands out from the league with enough rounds behind it.")
for row_start in range(0, len(shown), 3):
    cols = st.columns(3)
    for col, ins in zip(cols, shown[row_start:row_start + 3]):
        with col:
            insight_card(ins)
st.caption(f"{len(items)} tendencies found; showing the {len(shown)} furthest from the league. "
           f"A tendency is listed only when its 95% range doesn't overlap the league rate, with at least {MIN_SAMPLE} rounds.")

# ---- map pool -----------------------------------------------------------------------------------
st.subheader("Map pool")
mp = pool.assign(Map=pool["map"].str.title(),
                 Record=[f"{w}–{g - w}" for w, g in zip(pool["wins"], pool["games"])],
                 Attack=[f"{pct(w, n):.0%} ({w}/{n})" for w, n in zip(pool["atk_won"], pool["atk_n"])],
                 Defense=[f"{pct(w, n):.0%} ({w}/{n})" for w, n in zip(pool["def_won"], pool["def_n"])])
mp = mp.rename(columns={"games": "Maps"})
st.dataframe(mp[["Map", "Maps", "Record", "Attack", "Defense"]], hide_index=True, width="stretch")

# ---- one map in detail --------------------------------------------------------------------------
st.subheader("Map breakdown")
map_name = f["maps"][0] if f["maps"] else st.selectbox("Map", list(pool["map"]), format_func=str.title, key="report_map")
left, right = st.columns([3, 2], gap="large")

tr = _filter_rounds(team_rounds(), Scope(team_id=tid, side="attacker", maps=(map_name,), opponents=f["opponents"],
                                         patches=f["patches"], events=f["events"]))
lg_s = league_scope(Scope(team_id=tid, side="attacker", maps=(map_name,), patches=f["patches"], events=f["events"]), tr)
lg = _filter_rounds(team_rounds(), lg_s)
lg_name = f"Other {cohort_label(lg_s.cohorts)} teams' plants"
plants = plant_sites()
keys = ["game_id", "round_num"]
team_pl = tr.merge(plants[keys + ["site"]], on=keys)
lg_pl = lg[lg["team_id"] != tid].merge(plants[keys + ["site"]], on=keys)

with left:
    fig = base_map(map_name, height=560)
    map_sites = sites().get(map_name, [])
    if map_sites:
        sdf = pd.DataFrame(map_sites)
        counts = team_pl["site"].value_counts()
        sdf["label"] = [f"{n}: {int(counts.get(n, 0))} plants" for n in sdf["name"]]
        add_spots(fig, sdf, 600)
    hab = [i for i in items if i.category == "Utility" and i.map == map_name]
    if hab:
        fig.add_trace(go.Scatter(
            x=[i.tags["x"] for i in hab], y=[i.tags["y"] for i in hab], mode="markers+text",
            text=[f"{i.tags['player']}: {i.tags['ability'].replace('-', ' ')}"
                  + (f" ({i.tags['area']})" if i.tags.get("area") else "") for i in hab], textposition="top center",
            textfont=dict(color="#00AEEF", size=11), marker=dict(size=11, color="#00AEEF", symbol="diamond"),
            name="predictable utility", hoverinfo="text"))
    st.plotly_chart(fig, width="stretch", config={"scrollZoom": True, "displaylogo": False})
    st.caption("Rings: bomb sites with this team's plant count. Diamonds: utility this team places more predictably "
               "than a typical player. Sites are found from where teams plant; names match the official callouts.")

with right:
    st.markdown(f"**Where they plant on {map_name.title()}**")
    if len(team_pl) >= 1 and map_sites:
        rows = []
        for s in [x["name"] for x in map_sites]:
            k, n = int((team_pl["site"] == s).sum()), len(team_pl)
            lk, ln = int((lg_pl["site"] == s).sum()), len(lg_pl)
            rows.append({"Site": s, "Team": pct(k, n), "League": pct(lk, ln), "label": f"{k}/{n}"})
        sp = pd.DataFrame(rows)
        figp = go.Figure()
        figp.add_bar(y=sp["Site"], x=sp["Team"], orientation="h", name=team, marker_color="#00AEEF", text=sp["label"])
        figp.add_bar(y=sp["Site"], x=sp["League"], orientation="h", name=lg_name, marker_color="#4a5d73")
        figp.update_layout(height=60 + 60 * len(sp), barmode="group", margin=dict(l=0, r=0, t=0, b=0),
                           xaxis_tickformat=".0%", legend=dict(orientation="h", y=-0.25),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(figp, width="stretch", config={"displayModeBar": False})
        st.caption(f"{len(team_pl)} planted attack rounds out of {len(tr)} attack rounds on {map_name.title()}.")
    else:
        st.caption("No plants recorded for this team on this map.")
    st.markdown(f"**Tendencies on {map_name.title()}**")
    on_map = [i for i in items if i.map == map_name][:5]
    if on_map:
        for ins in on_map:
            insight_card(ins)
    else:
        st.caption("Nothing on this map stands out from the league yet.")
