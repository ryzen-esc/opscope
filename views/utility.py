"""Utility profiler page: where and when a team casts its abilities, and the spots they repeat."""
from dataclasses import replace

import plotly.express as px
import streamlit as st

from opscope.analytics.landing import add_landings, landing_model
from opscope.analytics.stats import MIN_SAMPLE, of
from opscope.analytics.utility import SPOT_RADIUS_CM, UtilityScope, utility_report
from opscope.ui.cards import insight, page_header, stat_card
from opscope.ui.filters import sidebar, team_name
from opscope.ui.minimap import add_points_by_category, add_spots, add_throw_lines, base_map
from opscope.ui.theme import ACCENT, chart, count_axis

CLASSES = {"Traps & setups": ("trap",), "Recon": ("recon",), "Smokes": ("smoke",), "Stalls": ("stall",),
           "Flashes": ("flash",), "All": ()}
PHASES = {"Both": (), "Pre-round setup": ("buy",), "During round": ("live",)}
SPOT_MARKS = "①②③④⑤⑥"


def pretty(ability_id: str) -> str:
    # Capitalize word starts only (.title() would give "Viper'S Pit").
    return " ".join(w[:1].upper() + w[1:] for w in str(ability_id).split("-"))


@st.cache_resource(show_spinner="Crunching utility…")
def report(scope: UtilityScope):
    return utility_report(scope)


f = sidebar()
team = team_name(f["team_id"])
header_slot = st.empty()
c1, c2 = st.columns([3, 2])
with c1:
    cls_label = st.segmented_control("Utility", list(CLASSES), default="Traps & setups", key="util_class") or "All"
with c2:
    phase_label = st.segmented_control("When", list(PHASES), default="Both", key="util_phase") or "Both"

scope = UtilityScope(team_id=f["team_id"], side=f["side"], maps=f["maps"], opponents=f["opponents"],
                     patches=f["patches"], events=f["events"], classes=CLASSES[cls_label], phases=PHASES[phase_label])
r = report(scope)
side_txt = {"defender": "defense", "attacker": "attack"}.get(f["side"], "")
unit = f"{side_txt} rounds".strip()
with header_slot.container():
    page_header("Utility profiler", team, f"{cls_label} · {', '.join(m.title() for m in f['maps']) or 'pick a map below'} · "
                                          f"{f['side_label'].lower()} · {phase_label.lower()}")

if r.n_rounds == 0:
    st.info("No rounds match these filters.")
    st.stop()

# ---- map choice ------------------------------------------------------------------------------
if f["maps"]:
    map_name = f["maps"][0]
else:
    played = r.rounds["map"].value_counts()
    map_name = st.selectbox("Map", list(played.index), format_func=lambda m: f"{m.title()} ({played[m]} {unit})",
                            key="util_map")
map_rounds = int((r.rounds["map"] == map_name).sum())

# ---- cast spot vs estimated landing ------------------------------------------------------------
all_casts = add_landings(r.casts)
modeled = all_casts["land_x"].notna() & (all_casts["map"] == map_name)
VIEWS = ["Where they stand", "Where it lands (est.)"]
view = (st.segmented_control("Show", VIEWS, default=VIEWS[0], key="util_view") or VIEWS[0]) if modeled.any() else VIEWS[0]
landing_view = view == VIEWS[1]
if landing_view:
    # Damaging thrown utility moves to its estimated landing; everything else stays at the cast spot.
    has = all_casts["land_x"].notna()
    all_casts = all_casts.assign(cast_x=all_casts["x"], cast_y=all_casts["y"],
                                 x=all_casts["land_x"].where(has, all_casts["x"]),
                                 y=all_casts["land_y"].where(has, all_casts["y"]))
    r = replace(r, casts=all_casts)  # habits below are then found on landing spots
casts = all_casts[all_casts["map"] == map_name]

agents = sorted(casts["agent"].dropna().unique())
# Keyed by class + map so the selection resets when those change (a stale selection would hide agents).
pick = st.multiselect("Agents", agents, default=agents, format_func=str.title,
                      key=f"util_agents_{cls_label}_{phase_label}_{map_name}_{f['team_id']}_{f['side']}") if agents else []
casts = casts[casts["agent"].isin(pick)] if pick else casts.iloc[0:0]

# ---- habits (repeat spots) -------------------------------------------------------------------
habits = r.habits(map_name)
if not habits.empty:
    habits = habits[habits["agent"].isin(pick)]
strong = (habits[(habits["rounds_on_agent"] >= MIN_SAMPLE) & (habits["share"] >= 0.4)]
          .sort_values(["share", "rounds"], ascending=False).head(5).reset_index(drop=True)) if not habits.empty else habits
if not strong.empty:
    areas = strong["area"] if "area" in strong else [None] * len(strong)
    strong["label"] = [f"{SPOT_MARKS[i]} {a}" if a else SPOT_MARKS[i] for i, a in enumerate(areas)]
    strong["mark"] = [SPOT_MARKS[i] for i in range(len(strong))]
for _, h in strong.head(3).iterrows():
    where = f" near <b>{h['area']}</b>" if h.get("area") else ""
    insight(f"{h['mark']} <b>{h['player_name']}</b> ({h['agent'].title()}) puts <b>{pretty(h['ability'])}</b> in the same spot{where} "
            f"(±{SPOT_RADIUS_CM // 100} m) in <b>{of(int(h['rounds']), int(h['rounds_on_agent']), unit + ' on ' + h['agent'].title())}</b> "
            f"on {map_name.title()}.")
if strong.empty and not casts.empty:
    insight(f"No placement on {map_name.title()} repeats in at least 40% of rounds (with {MIN_SAMPLE}+ rounds). "
            f"This team varies its {cls_label.lower()} here.")

# ---- cards -----------------------------------------------------------------------------------
k1, k2, k3 = st.columns(3)
rounds_with = casts["round_key"].nunique()
with k1:
    stat_card(f"{cls_label} casts on {map_name.title()}", f"{len(casts)}", f"across {of(rounds_with, map_rounds, unit)}")
with k2:
    pre = int((casts["phase"] == "buy").sum())
    stat_card("Placed before the round starts", f"{pre / len(casts):.0%}" if len(casts) else "—",
              of(pre, len(casts), "casts"), "buy-phase setups are the most predictable")
with k3:
    top = casts["ability"].value_counts()
    stat_card("Most used", pretty(top.index[0]) if len(top) else "—",
              of(int(top.iloc[0]), len(casts), "casts") if len(top) else "", None)

# ---- map + tables ----------------------------------------------------------------------------
left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Where it goes")
    default_arrows = landing_view or cls_label in ("Smokes", "Flashes", "Recon", "Stalls")
    t1, t2 = st.columns(2)
    with t1:
        arrows = st.toggle("Throw lines" if landing_view else "Aim direction", value=default_arrows,
                           help="From the caster to the estimated landing" if landing_view
                           else "Line from the caster in the direction they were aiming.")
    with t2:
        show_spots = st.toggle("Habit spots", value=True)
    fig = base_map(map_name)
    if not casts.empty:
        tmp = casts.assign(name=casts["player_name"], ability_name=casts["ability"].map(pretty),
                           time=casts["t"].round(0).astype("Int64").astype(str) + "s")
        if landing_view and arrows:
            add_throw_lines(fig, tmp[tmp["land_x"].notna()])
        add_points_by_category(fig, tmp, "ability_name", ["name", "ability_name", "phase", "time"],
                               arrows=arrows and not landing_view)
    if show_spots and not strong.empty:
        add_spots(fig, strong, SPOT_RADIUS_CM)
    chart(fig, interactive=True)
    if landing_view:
        val = landing_model()["validation"]
        n_est = int(casts["land_x"].notna().sum())
        st.caption(f"Estimated landings for damaging utility ({n_est} of {len(casts)} casts here): mollies, nanoswarms, "
                   f"shock darts and similar. They're placed along the aim, at the distance that ability usually travels "
                   f"for that aim angle, learned from who it later damaged. On held-out matches the typical miss is "
                   f"{val['median_model_m']} m, against {val['median_cast_m']} m for the cast spot. Other utility stays "
                   f"at the cast spot.")
    else:
        st.caption("Dots are where the player stood when casting, from the ability supplement (in VCT Americas 2025, "
                   "recorded once a second, a moving player can be a few metres off). GRID doesn't record where utility "
                   "lands, so thrown utility shows the aim direction instead. Rings mark spots reused in many rounds.")

with right:
    st.subheader("Who uses what")
    if not casts.empty:
        mtab = (casts.groupby(["player_name", "agent", "ability"], observed=True)
                .agg(casts=("event_id", "size"), rounds=("round_key", "nunique")).reset_index())
        ar = r.agent_rounds_by_map(map_name)
        pid = casts.drop_duplicates("player_name").set_index("player_name")["player_id"]
        mtab["on_agent"] = [int(ar.get((pid[p], a), n)) for p, a, n in zip(mtab["player_name"], mtab["agent"], mtab["rounds"])]
        mtab["Used in"] = [of(n, d, "rds") for n, d in zip(mtab["rounds"], mtab["on_agent"])]
        mtab["Per round"] = (mtab["casts"] / mtab["on_agent"]).round(2)
        show = mtab.sort_values("casts", ascending=False).rename(columns={"player_name": "Player", "agent": "Agent",
                                                                           "ability": "Ability", "casts": "Casts"})
        show["Agent"] = show["Agent"].str.title()
        show["Ability"] = show["Ability"].map(pretty)
        st.dataframe(show[["Player", "Agent", "Ability", "Casts", "Used in", "Per round"]], hide_index=True,
                     width="stretch", height=min(420, 38 + 35 * len(show)))
    st.subheader("When it's used")
    if not casts.empty:
        window = casts.assign(window=casts["phase"].map({"buy": "buy phase"}).fillna(casts["bucket"].astype(str)))
        tim = window.groupby("window").size().reindex(["buy phase", "0–20s", "20–40s", "40–60s", "60s+"], fill_value=0)
        figt = px.bar(tim.reset_index(name="casts"), x="window", y="casts", text="casts",
                      color_discrete_sequence=[ACCENT])
        figt.update_layout(height=250, xaxis_title=None, yaxis=dict(title="casts", **count_axis(tim.max())))
        chart(figt)
        st.caption("Time after the buy phase ends. Pre-round setups (buy phase) are shown separately.")
