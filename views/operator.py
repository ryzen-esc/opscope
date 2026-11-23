"""Operator profiler page."""
import plotly.express as px
import streamlit as st

from opscope.analytics.operator import SETUP_WINDOW, Scope, operator_report, time_bucket
from opscope.analytics.stats import MIN_SAMPLE, of, pct, wilson
from opscope.ui.cards import insight, map_key, page_header, rate_card
from opscope.ui.filters import sidebar, team_name
from opscope.ui.minimap import BUCKET_COLORS, add_density, add_points_by_bucket, add_sightlines, base_map
from opscope.ui.theme import ACCENT, AMBER, ATTACK, TEXT_DIM, chart, count_axis
from opscope.zones import nearest_callout

WEAPONS = {"Operator": "operator", "Odin": "odin", "Outlaw": "outlaw", "Marshal": "marshal"}


@st.cache_resource(show_spinner="Crunching rounds…")
def report(scope: Scope):
    return operator_report(scope)


f = sidebar()
team = team_name(f["team_id"])
header_slot = st.empty()
weapon_label = st.segmented_control("Weapon", list(WEAPONS), default="Operator", key="weapon") or "Operator"
weapon = WEAPONS[weapon_label]
gun = weapon_label

scope = Scope(team_id=f["team_id"], weapon=weapon, side=f["side"], maps=f["maps"],
              opponents=f["opponents"], patches=f["patches"], events=f["events"])
r = report(scope)
side_txt = {"defender": "defense", "attacker": "attack"}.get(f["side"], "")
unit = f"{side_txt} rounds".strip()
with header_slot.container():
    page_header("Operator profiler", team, f"{weapon_label} · {', '.join(m.title() for m in f['maps']) or 'all maps'} · "
                                            f"{f['side_label'].lower()}")

if r.n_rounds == 0:
    st.info("No rounds match these filters.")
    st.stop()

# ---- headline insights ---------------------------------------------------------------------
holders = r.holder_table()
maps = r.map_table()
if r.n_gun_rounds:
    top = holders.groupby("player_name")["rounds"].sum().sort_values(ascending=False)
    main, main_n = top.index[0], int(top.iloc[0])
    agents = holders[holders["player_name"] == main].sort_values("rounds", ascending=False)
    agent_txt = ", ".join(f"{a.title()} {n}" for a, n in zip(agents["agent"], agents["rounds"]))
    insight(f"<b>{main}</b> is the {gun} player: <b>{of(main_n, r.n_gun_rounds, f'{gun} rounds')}</b> ({agent_txt}).")
    big = maps[maps["rounds"] >= 2 * MIN_SAMPLE].copy()
    if len(big) >= 2:
        # Most confidently high (Wilson lower bound) vs most confidently low (Wilson upper bound).
        bounds = [wilson(int(k), int(n)) for k, n in zip(big["gun_rounds"], big["rounds"])]
        big["lo_b"], big["hi_b"] = [b[0] for b in bounds], [b[1] for b in bounds]
        hi, lo = big.loc[big["lo_b"].idxmax()], big.loc[big["hi_b"].idxmin()]
        if hi["map"] != lo["map"] and hi["lo_b"] > lo["hi_b"]:
            insight(f"{gun} usage depends on the map: <b>{hi['map'].title()}</b> {of(int(hi['gun_rounds']), int(hi['rounds']), unit)} "
                    f"vs <b>{lo['map'].title()}</b> {of(int(lo['gun_rounds']), int(lo['rounds']), unit)}.")
    if len(r.pickups):
        insight(f"The {gun} changed hands mid-round in <b>{r.pickups[['game_id', 'round_num']].drop_duplicates().shape[0]}</b> rounds "
                f"(fired by a player who didn't buy it: {', '.join(r.pickups['player_name'].value_counts().index[:3])}).")
else:
    insight(f"{team} never had a {gun} at the end of the buy phase in these {r.n_rounds} rounds.")

# ---- stat cards ----------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1:
    peer = f"typical {r.league_label} team" if r.league_method == "typical team" else f"all other {r.league_label}"
    rate_card(f"Rounds with {gun}", r.n_gun_rounds, r.n_rounds, unit, league=r.league_share,
              league_label=peer, league_rate=r.league_rate)
with c2:
    w = r.win_rates("full")
    rate_card(f"Full-buy win rate with {gun}", *w["with"], "full buys")
with c3:
    rate_card(f"Full-buy win rate without", *w["without"], "full buys")
with c4:
    k, n = r.kept()
    rate_card(f"Survived with the {gun}", k, n, f"{gun} rounds")

# ---- map + side panels ---------------------------------------------------------------------
left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Where they set up")
    if f["maps"]:
        map_name = f["maps"][0]
    else:
        gun_maps = maps[maps["gun_rounds"] > 0].sort_values("gun_rounds", ascending=False)
        options = list(gun_maps["map"]) or list(maps["map"])
        map_name = st.selectbox("Map", options, format_func=str.title, key="op_map")
    pos = r.positions[r.positions["map"] == map_name]
    sight = r.sightlines[r.sightlines["map"] == map_name]
    bucket_names = list(BUCKET_COLORS)
    ctl1, ctl2 = st.columns([3, 1])
    with ctl1:
        buckets = st.multiselect("Time in round", bucket_names, default=bucket_names[:2], key="op_buckets") or bucket_names
    with ctl2:
        show_lines = st.toggle("Kill lines", value=True)
    shown = pos[pos["bucket"].isin(buckets)]
    # Kill lines follow the same time windows as the dots, so every line starts where the holder was seen.
    sight = sight[time_bucket(sight["t"]).isin(buckets)]
    gun_rounds_map = int(r.holders["map"].eq(map_name).sum())
    seen_rounds = shown[["game_id", "round_num"]].drop_duplicates().shape[0]
    holder_names = shown["player_name"].value_counts()
    who = " and ".join(f"<b>{n}</b>" for n in holder_names.index[:2]) or "the holder"
    map_key(
        [f'<span style="color:{ACCENT}">●</span> Dots: where {who} stood with the {gun} when they shot, got hit '
         f"or used an ability (colour = time in round)",
         f'<span style="color:{ATTACK}">◯—✕</span> Lines: their {gun} kills, shooter to victim',
         f"<b>{gun_rounds_map}</b> {gun} round{'' if gun_rounds_map == 1 else 's'} on {map_name.title()} · "
         f"{len(shown)} moments in {seen_rounds} of them"])
    if 0 < gun_rounds_map < MIN_SAMPLE:
        plural = gun_rounds_map != 1
        insight(f"Only <b>{gun_rounds_map} {gun} round{'s' if plural else ''}</b> on {map_name.title()} "
                f"match{'' if plural else 'es'} these filters: too few to read a setup. Clear the Opponents filter "
                f"or pick another map.", AMBER)
    fig = base_map(map_name)
    add_density(fig, shown, map_name)
    if show_lines and not sight.empty:
        names = {**dict(zip(r.holders["player_id"], r.holders["player_name"])),
                 **dict(zip(r.pickups.get("actor_id", []), r.pickups.get("player_name", [])))}
        hover = [f"{names.get(a, 'teammate')}: {gun} kill at {t:.0f}s" for a, t in zip(sight["actor_id"], sight["t"])]
        add_sightlines(fig, sight, name=f"{gun} kills", hover=hover)
    if not shown.empty:
        tmp = shown.assign(time=shown["t"].round(0).astype(int).astype(str) + "s", via=shown["source"],
                           area=nearest_callout(map_name, shown["x"], shown["y"]))
        add_points_by_bucket(fig, tmp, ["player_name", "agent", "area", "time", "via"])
    fig.update_layout(legend_title_text="Seen at ")
    chart(fig, interactive=True)
    st.caption(f"GRID records a position only when a player shoots, gets hit or uses an ability, so quiet moments leave "
               f"gaps. The shaded glow is where the dots cluster. Positions are ±1–4 m. Showing {len(sight)} "
               f"{gun} kills in the chosen time windows.")
    if seen_rounds:
        areas = shown.assign(area=nearest_callout(map_name, shown["x"], shown["y"])).dropna(subset=["area"])
        per_area = areas.drop_duplicates(["game_id", "round_num", "area"])["area"].value_counts().head(3)
        if len(per_area):
            parts = ", ".join(f"<b>{a}</b> ({of(int(k), seen_rounds, 'rounds')})" for a, k in per_area.items())
            insight(f"Where the {gun} holder shows up in these time windows: {parts}.")
    a = r.aggression_summary() if f["maps"] else None
    if a and a["median"] is not None and a["n"] >= MIN_SAMPLE:
        style = "aggressive" if a["percentile"] >= 0.6 else "passive" if a["percentile"] <= 0.4 else "typical"
        insight(f"Early setup on {map_name.title()} (first {SETUP_WINDOW:.0f}s): <b>{style}</b>. The median position is "
                f"further forward than <b>{a['percentile']:.0%}</b> of other teams' {gun} setups "
                f"(seen in {of(a['n'], gun_rounds_map, f'{gun} rounds')}).")

with right:
    st.subheader("Who holds it")
    if not holders.empty:
        hv = holders.assign(label=holders["player_name"] + " · " + holders["agent"].str.title())
        figh = px.bar(hv.head(8), x="rounds", y="label", orientation="h", text="rounds",
                      color_discrete_sequence=[ACCENT])
        rows = min(len(hv), 8)
        figh.update_layout(height=60 + 30 * rows, yaxis=dict(autorange="reversed", title=None),
                           xaxis=dict(title=f"{gun} rounds", **count_axis(hv["rounds"].head(8).max())))
        figh.update_traces(width=0.7)
        chart(figh)
    st.subheader("When it fires")
    fb = r.first_shot_buckets()
    if fb["rounds"].sum():
        figt = px.bar(fb, x="bucket", y="rounds", text="rounds", color="bucket",
                      color_discrete_map=BUCKET_COLORS)
        figt.update_layout(height=230, showlegend=False, xaxis_title="first shot after buy phase",
                           yaxis=dict(title="rounds", **count_axis(fb["rounds"].max())))
        chart(figt)
        st.caption(f"{gun} fired in {of(int(fb['rounds'].sum()), r.n_gun_rounds, f'{gun} rounds')}.")
    else:
        st.caption(f"The {gun} never fired in these rounds.")

if f["maps"]:
    st.stop()  # the per-map comparison only makes sense across several maps
st.subheader(f"{gun} rate by map")
mt = maps.assign(label=lambda x: x["map"].str.title(),
                 text=lambda x: x["gun_rounds"].astype(str) + "/" + x["rounds"].astype(str))
figm = px.bar(mt, x="label", y="share", text="text", color_discrete_sequence=[ACCENT])
league_rate = r.league_rate
figm.add_hline(y=league_rate, line_dash="dot", line_color=TEXT_DIM,
               annotation_text=f"{peer} {league_rate:.0%}", annotation_font_color=TEXT_DIM)
figm.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), yaxis_tickformat=".0%", yaxis_title=f"{unit} with {gun}",
                   xaxis_title=None)
chart(figm)
st.caption(f"Bar labels show rounds with the gun / rounds played. The dotted line is the typical other {r.league_label} "
           f"team (the median of each team's own rate, so one extreme team can't move it), with the same side, patch "
           f"and event filters.")
