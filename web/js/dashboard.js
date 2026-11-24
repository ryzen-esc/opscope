// Dashboard frame: tabs (Briefing · Operator · Utility · Map pool), map chips, side, filters drawer, and the
// rail / stage / bottom-strip layout each tab draws into. Tab state lives in the URL (replaceState, no reload).
import { api } from "./api.js";
import { renderBriefing } from "./briefing.js";
import { renderOperator } from "./operator.js";
import { lenisStart, lenisStop } from "./motion.js";
import { esc } from "./overview.js";
import { segment, tooltip } from "./ui.js";

const SOON = '<i class="tsoon">soon</i>';
const TABS = [["briefing", "Briefing"], ["operator", "Operator"], ["utility", `Utility${SOON}`], ["pool", `Map pool${SOON}`]];
const SIDES = [["both", "Both"], ["attacker", "Attack"], ["defender", "Defense"]];
const title = (s) => String(s || "").replace(/\b\w/g, (c) => c.toUpperCase());

export async function renderDashboard(app, { meta, team, filters, params, setParams, navigate }) {
  document.body.classList.add("board");
  lenisStop();
  const tip = tooltip();
  let tab = TABS.some(([k]) => k === params.get("tab")) ? params.get("tab") : "briefing";
  let disposeTab = () => {};
  const nFilters = filters.opponents.length + filters.patches.length + filters.events.length;

  app.innerHTML = `
  <div class="board-wrap">
    <div class="dbar">
      <div id="tabs"></div>
      <span class="dlabel" title="Map and side only narrow what's shown; they don't change any number.">Show</span>
      <div class="mapchips" id="mapchips" role="toolbar" aria-label="Map"></div>
      <div id="sides"></div>
      <button class="fbtn${nFilters ? " active" : ""}" id="fbtn" type="button"
        title="Opponents, event and patch: every number is recomputed for the matches you keep.">Filters${nFilters ? ` <b>${nFilters}</b>` : ""}</button>
    </div>
    <aside class="rail" id="rail" data-lenis-prevent></aside>
    <section class="bstage" id="bstage">
      <svg id="bmap"></svg>
      <div class="hud" id="hud"></div>
      <div class="legend" id="legend"></div>
      <div class="stagenote" id="stagenote"></div>
      <div class="live" id="live" data-lenis-prevent></div>
      <div class="ecard" id="ecard" data-lenis-prevent></div>
      <div class="zoomctl"><button type="button" id="zin" aria-label="Zoom in">+</button><button type="button" id="zout" aria-label="Zoom out">−</button></div>
    </section>
    <footer class="strip" id="strip"></footer>
  </div>
  <aside class="drawer" id="drawer" data-lenis-prevent aria-label="Filters"></aside>`;
  const $ = (s) => app.querySelector(s);
  const ui = {
    rail: $("#rail"), svg: $("#bmap"), hud: $("#hud"), legend: $("#legend"), card: $("#ecard"), strip: $("#strip"), stage: $("#bstage"),
    note: $("#stagenote"), live: $("#live"),
    _map: null, _side: null, _zoom: null,
    onMap(fn) { this._map = fn; }, onSide(fn) { this._side = fn; }, zoom(fn) { this._zoom = fn; },
  };
  let zoomLevel = 1;
  $("#zin").addEventListener("click", () => { zoomLevel = Math.min(4, zoomLevel * 1.4); ui._zoom?.(zoomLevel); });
  $("#zout").addEventListener("click", () => { zoomLevel = Math.max(1, zoomLevel / 1.4); ui._zoom?.(zoomLevel); });

  const [rep, tf] = await Promise.all([api.report(team, filters), api.filters(team)]);

  // ---- map chips: maps this team played, with how many tendencies each has ----
  const perMap = Object.fromEntries(rep.pool.map((p) => [p.map, rep.insights.filter((i) => i.map === p.map).length]));
  const chips = $("#mapchips");
  const setChip = (m) => chips.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("on", b.dataset.m === m);
    if (b.dataset.m === m) chips.scrollTo({ left: b.offsetLeft - chips.offsetWidth / 2 + b.offsetWidth / 2, behavior: "smooth" });
  });
  chips.innerHTML = `<button type="button" data-m="">All maps</button>` + rep.pool.map((p) => `<button type="button" data-m="${p.map}"
    class="${perMap[p.map] ? "has" : ""}" title="${p.games} maps played">${esc(title(p.map))}${perMap[p.map] ? `<sup>${perMap[p.map]}</sup>` : ""}</button>`).join("");
  chips.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { setChip(b.dataset.m); ui._map?.(b.dataset.m); }));
  setChip(params.get("map") || "");

  ui.setSide = segment($("#sides"), SIDES, params.get("side") || "both", (k) => ui._side?.(k), "small");
  ui.setMap = (m) => setChip(m || "");
  const chipBadges = (badges) => chips.querySelectorAll("button[data-m]").forEach((b) => {
    if (!b.dataset.m) return;
    const v = badges ? badges[b.dataset.m] : perMap[b.dataset.m];
    b.querySelector("sup")?.remove();
    if (v) b.insertAdjacentHTML("beforeend", `<sup>${esc(String(v))}</sup>`);
    b.classList.toggle("has", !!v);
  });
  ui.setBadges = chipBadges;

  // When filters are on, say so where the numbers are read, with a way out.
  const fnames = [
    ...filters.opponents.map((id) => `vs ${tf.opponents.find((o) => o.id === id)?.name || id}`),
    ...filters.events.map((e) => e.replace(/^VCT [^-]+ - /, "")),
    ...filters.patches.map((p) => `patch ${p}`),
  ];
  const filterBanner = fnames.length ? `<div class="fbanner"><span><b>Filtered:</b> every number is recomputed for ${esc(fnames.join(", "))}.</span>
    <button type="button" data-clear-filters>Clear</button></div>` : "";
  ui.rail.addEventListener("click", (e) => { if (e.target.closest("[data-clear-filters]")) navigate({ opponents: [], patches: [], events: [] }); });

  // ---- tabs ----
  function showTab(k) {
    disposeTab();
    tip.hide();
    tab = k;
    setParams({ tab: k === "briefing" ? null : k });
    ui.card.classList.remove("in");
    ui.stage.classList.remove("carded");
    ui.note.classList.remove("on");
    ui.legend.innerHTML = "";
    ui._map = ui._side = ui._zoom = null;
    ui.note.classList.remove("amber");
    ui.live.classList.remove("in");
    ui.strip.className = "strip";
    if (k === "operator") {
      ui.rail.scrollTop = 0;
      disposeTab = renderOperator(ui, { team, filters, params: new URLSearchParams(location.search), setParams, tip });
      return;
    }
    if (k === "briefing") {
      ui.setSide(new URLSearchParams(location.search).get("side") || "both");
      ui.legend.innerHTML = `<span><i class="dia" style="--c:var(--def)"></i>Utility habit spot</span><span><i style="--c:transparent;border:2px solid var(--def)"></i>Gun choice, usual area</span>
        <span><i class="zone"></i>Bomb site · their plant count</span><span style="color:var(--faint)">Blue = defense, red = attack</span>`;
      disposeTab = renderBriefing(ui, { rep, params: new URLSearchParams(location.search), setParams, tip, goTab, filterBanner });
    } else {
      const names = { utility: ["Utility profiler", "Step 6: where utility goes, habit spots and landings, on the timeline."],
        pool: ["Map pool", "Step 7: every map with attack and defense win rates."] };
      ui.rail.innerHTML = `<div class="tab-soon"><div><div class="kicker">Next build steps</div><h3>${names[k][0]}</h3><p>${names[k][1]}</p></div></div>`;
      ui.svg.innerHTML = ""; ui.hud.innerHTML = ""; ui.strip.innerHTML = "";
      disposeTab = () => {};
    }
  }
  function goTab(target) {
    const { tab: k, ...rest } = target;
    setParams(rest);
    setTabUI(k);
    showTab(k);
  }
  const setTabUI = segment($("#tabs"), TABS, tab, showTab);

  // ---- filters drawer (opponents, patch, event: they change the analysis, so they refetch) ----
  const drawer = $("#drawer");
  const group = (key, label, opts) => opts.length ? `<h4>${label}</h4>` + opts.map((o) => `<label><input type="checkbox" data-f="${key}" value="${esc(o.v)}"
    ${filters[key].includes(o.v) ? "checked" : ""}>${esc(o.l)}${o.n != null ? `<small>${o.n} rds</small>` : ""}</label>`).join("") : "";
  drawer.innerHTML = `<header><b>Filters</b><button class="fbtn" type="button" id="dclose">Close</button></header>
    <div class="body">
      <p style="color:var(--dim);font-size:13px;margin-top:8px">These change the analysis itself: every rate and comparison is recomputed for the matches you keep.</p>
      ${group("opponents", "Opponents", tf.opponents.map((o) => ({ v: o.id, l: o.name, n: o.rounds })))}
      ${group("events", "Event", tf.events.map((e) => ({ v: e, l: e })))}
      ${group("patches", "Patch", tf.patches.map((p) => ({ v: p, l: `Patch ${p}` })))}
    </div>
    <footer><button type="button" id="dclear">Clear all</button><button type="button" class="apply" id="dapply">Apply</button></footer>`;
  const toggleDrawer = (open) => drawer.classList.toggle("open", open);
  $("#fbtn").addEventListener("click", () => toggleDrawer(!drawer.classList.contains("open")));
  drawer.querySelector("#dclose").addEventListener("click", () => toggleDrawer(false));
  drawer.querySelector("#dclear").addEventListener("click", () => navigate({ opponents: [], patches: [], events: [] }));
  drawer.querySelector("#dapply").addEventListener("click", () => {
    const pick = (k) => [...drawer.querySelectorAll(`input[data-f="${k}"]:checked`)].map((i) => i.value);
    navigate({ opponents: pick("opponents"), patches: pick("patches"), events: pick("events") });
  });

  const onKey = (e) => {
    if (e.target.closest("input, textarea") || !document.getElementById("palette").hidden || e.metaKey || e.ctrlKey) return;
    const i = ["1", "2", "3", "4"].indexOf(e.key);
    if (i >= 0) { setTabUI(TABS[i][0]); showTab(TABS[i][0]); }
  };
  addEventListener("keydown", onKey);

  if (rep.empty) {
    ui.rail.innerHTML = `<p class="empty-note">No games match these filters.</p>`;
  } else showTab(tab);

  return () => {
    disposeTab();
    removeEventListener("keydown", onKey);
    tip.remove();
    document.body.classList.remove("board");
    lenisStart();
  };
}
