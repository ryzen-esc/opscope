// Dashboard · Utility tab: where a team's utility goes, when, and which placements repeat (habit spots). The round
// clock starts in the buy phase (negative time), so pre-round setups play first, then the live round.
import { api } from "./api.js";
import { COLORS, drawMap, el } from "./map.js";
import { TIME } from "./operator.js";
import { esc } from "./overview.js";
import { clockLabel, createTimeline } from "./timeline.js";
import { segment } from "./ui.js";

const CLASSES = [["trap", "Traps"], ["recon", "Recon"], ["smoke", "Smokes"], ["stall", "Stalls"], ["flash", "Flashes"], ["all", "All"]];
const CLASS_LONG = { trap: "traps & setups", recon: "recon", smoke: "smokes", stall: "stalls", flash: "flashes", all: "utility" };
const PHASES = [["both", "Both"], ["buy", "Pre-round"], ["live", "During round"]];
const PALETTE = ["#00aeef", "#f5b43c", "#4fd18b", "#b388eb", "#ff9f68", "#4dd0e1", "#e3e36b", "#f28fb4"];
const OTHER = "#6b7785"; // abilities beyond the top eight share one colour, so every colour on the map means one thing
const BUY_FROM = -30; // the clock starts 30 s before the round (a normal buy phase is ~28.5 s)
const MOMENT = 5;
const MIN_SAMPLE = 8;
const MARKS = "①②③④⑤⑥";
const title = (s) => String(s || "").replace(/\b\w/g, (c) => c.toUpperCase());
const pct = (v) => `${Math.round(v * 100)}%`;
const clampT = (t) => Math.max(BUY_FROM, t);
const when = (c) => (c.phase === "buy" ? `${clockLabel(c.t)} (buy phase)` : clockLabel(c.t));

export function renderUtility(ui, { team, filters, params, setParams, tip, filterBanner = "" }) {
  const st = {
    cls: params.get("classes") || "trap", phase: params.get("phase") || "both", side: params.get("side") || "defender",
    map: params.get("map") || "", view: params.get("uview") === "land" ? "land" : "cast",
    aim: params.has("aim") ? params.get("aim") === "1" : null, // null = the default for this utility type
    spots: params.get("spots") !== "0", hidden: new Set(), round: null, focusHabit: null,
    players: new Set(params.getAll("player")), // empty = the whole team
  };
  if (st.side === "both" && !params.get("side")) st.side = "defender";
  // Thrown utility only shows where it was aimed (GRID doesn't record landings), so aim lines start on for it.
  const aimOn = () => (st.aim != null ? st.aim : !["trap", "all"].includes(st.cls));
  let data = null, map = null, geo = null, tl = null, layer = null, token = 0, alive = true, order = [], rank = new Map(), colors = {}, abilAll = [];
  ui.setSide(st.side);
  const live = new AbortController();

  async function load() {
    const t = ++token;
    ui.rail.innerHTML = `<div class="rail-loading">Crunching ${esc(CLASS_LONG[st.cls])}…</div>`;
    let d;
    try {
      d = await api.utility(team, { side: st.side, classes: st.cls === "all" ? [] : [st.cls],
        phases: st.phase === "both" ? [] : [st.phase], ...filters });
    } catch (e) { if (t === token) ui.rail.innerHTML = `<p class="empty-note">Couldn't load: ${esc(e.message)}</p>`; return; }
    if (t !== token || !alive) return;
    data = d;
    if (d.empty || !d.maps_order.length) {
      ui.rail.innerHTML = `<div class="op-head"><div id="ucls"></div><div id="uphase" style="margin-top:8px"></div></div>
        ${filterBanner}<p class="empty-note">No rounds match these filters.</p>`;
      controls();
      return;
    }
    if (!st.map || !d.maps[st.map]) st.map = d.maps_order[0];
    ui.setMap(st.map);
    ui.setBadges(Object.fromEntries(Object.entries(d.maps).map(([m, x]) => [m, x.casts.length ? `${x.casts.length}` : ""])));
    await showMap();
  }

  function controls() {
    segment(ui.rail.querySelector("#ucls"), CLASSES, st.cls, (k) => {
      st.cls = k; st.aim = null; setParams({ classes: k === "trap" ? null : k, aim: null }); load();
    }, "small wide");
    segment(ui.rail.querySelector("#uphase"), PHASES, st.phase, (k) => { st.phase = k; setParams({ phase: k === "both" ? null : k }); load(); }, "small wide");
  }

  const m = () => data.maps[st.map];
  const mine = (x) => !st.players.size || st.players.has(x.player);
  const visibleCasts = () => m().casts.filter((c) => mine(c) && !st.hidden.has(c.ability));
  const habitsNow = () => {
    const list = st.view === "land" ? m().habits_landing : m().habits;
    return list.filter((h) => h.strong && mine(h) && !st.hidden.has(h.ability)).slice(0, 5);
  };
  /** Everyone who played this map (most rounds first), with their agents and how many of the selected casts they made. */
  const playersHere = () => {
    const casts = countBy(m().casts, (c) => c.player);
    const list = (m().players || []).map((p) => ({ player: p.player, agents: p.agents.map((a) => a.agent), n: casts[p.player] || 0 }));
    for (const [player, n] of Object.entries(casts)) if (!list.some((p) => p.player === player)) list.push({ player, agents: [], n });
    return list.sort((a, b) => (b.n > 0) - (a.n > 0) || b.n - a.n);
  };
  function togglePlayer(name) {
    if (name == null) st.players.clear();
    else if (st.players.has(name)) st.players.delete(name);
    else st.players.add(name);
    setParams({ player: [...st.players] });
    st.focusHabit = null;
    renderRail(); renderLegend(); renderHud(); drawLayers();
    if (st.round != null && !order.includes(st.round)) watchRound(null); else renderNav();
  }

  // ---- rail ----
  function renderRail() {
    const mm = m(), casts = visibleCasts();
    const pre = casts.filter((c) => c.phase === "buy").length;
    const byAb = countBy(casts, (c) => c.ability_name);
    const top = Object.entries(byAb).sort((a, b) => b[1] - a[1])[0];
    const rounds = new Set(casts.map((c) => c.round)).size;
    const buckets = [["buy phase", (c) => c.phase === "buy"], ...TIME.map((b) => [b.label, (c) => c.phase !== "buy" && c.t >= b.from && c.t < b.to])];
    const tim = buckets.map(([l, f]) => [l, casts.filter(f).length]);
    const tmax = Math.max(1, ...tim.map((x) => x[1]));
    const hab = habitsNow();
    const modeled = mm.casts.some((c) => c.land);
    const unit = data.unit;
    const who = mm.who.filter((w) => mine(w) && !st.hidden.has(w.ability));
    const plist = playersHere();
    ui.rail.innerHTML = `
      <div class="op-head"><div id="ucls"></div><div id="uphase" style="margin-top:8px"></div>
        ${modeled ? `<div id="uview" style="margin-top:8px"></div>` : ""}
        <div class="toggles"><label><input type="checkbox" id="taim" ${aimOn() ? "checked" : ""}> Aim direction</label>
          <label><input type="checkbox" id="tspots" ${st.spots ? "checked" : ""}> Habit spots</label></div>
        <div class="pchips" role="group" aria-label="Players"><button type="button" data-p="" class="${st.players.size ? "" : "on"}">Whole team</button>${
          plist.map((p) => p.n ? `<button type="button" data-p="${esc(p.player)}" class="${st.players.has(p.player) ? "on" : ""}"
            title="${p.n} casts on ${esc(p.agents.map(title).join(", "))}">${esc(p.player)} <small>${esc(p.agents.map(title).join(", "))}</small></button>`
            : `<button type="button" class="none" disabled title="Played ${esc(p.agents.map(title).join(", "))} on ${esc(title(st.map))}: no ${esc(CLASS_LONG[st.cls])} recorded">
              ${esc(p.player)} <small>${esc(p.agents.map(title).join(", "))} · no ${esc(CLASS_LONG[st.cls])} here</small></button>`).join("")}</div></div>
      ${filterBanner}
      <section class="blk">
        <div class="k">${esc(title(CLASS_LONG[st.cls]))} · ${esc(title(st.map))} · ${esc(unit)} · ${st.players.size ? esc([...st.players].join(", ")) : esc(data.name)}</div>
        <h4 style="margin-top:12px">Habits <span>same spot within 4 m, in 40%+ of rounds on the agent</span></h4>
        ${hab.length ? `<ol class="habits">${hab.map((h, i) => `<li data-h="${i}" class="${st.focusHabit === i ? "on" : ""}">
          <span class="hmk">${MARKS[i]}</span><span><b>${esc(h.player)}</b> (${esc(title(h.agent))}) puts <b>${esc(h.ability_name)}</b> in the same spot${
            h.area ? ` near <b>${esc(h.area)}</b>` : ""} in <b>${h.k} of ${h.n}</b> ${esc(unit)} on ${esc(title(h.agent))}.</span></li>`).join("")}</ol>`
          : `<p class="glance">No placement on ${esc(title(st.map))} repeats in at least 40% of rounds (with ${MIN_SAMPLE}+ rounds on the agent).
             ${st.players.size ? "They vary" : "This team varies"} ${st.players.size ? "their" : "its"} ${esc(CLASS_LONG[st.cls])} here.</p>`}
        <p class="hint">A habit is the player's own repeat rate. The scouting report also compares it with the typical player, and flags it
          only when it's clearly more predictable.</p>
      </section>
      <section class="blk two">
        <div><h4>Casts here</h4><p class="wr"><b>${casts.length}</b> <span>in ${rounds} of ${mm.rounds} ${esc(unit)}</span></p></div>
        <div><h4>Before the round starts</h4><p class="wr"><b>${casts.length ? pct(pre / casts.length) : "—"}</b> <span>${pre} of ${casts.length}</span></p></div>
        <div style="grid-column:1/-1"><h4>Most used</h4><p class="wr"><b style="font-size:20px">${top ? esc(top[0]) : "—"}</b> <span>${top ? `${top[1]} of ${casts.length} casts` : ""}</span></p></div>
      </section>
      <section class="blk">
        <h4>When it's used <span>buy phase, then time after it ends</span></h4>
        <div class="fs five">${tim.map(([l, n], i) => `<div><span class="col" style="height:${(n / tmax) * 100}%;background:${i ? TIME[i - 1].color : COLORS.amb}"></span>
          <b>${n}</b><small>${esc(l)}</small></div>`).join("")}</div>
      </section>
      <section class="blk">
        <h4>Who uses what</h4>
        <table class="who"><thead><tr><th>Player</th><th>Ability</th><th>Casts</th><th>Used in</th><th>/rd</th></tr></thead>
          <tbody>${who.map((w) => `<tr><td><button type="button" class="pl" data-p="${esc(w.player)}" title="Show only ${esc(w.player)}">${esc(w.player)}</button> <small>${esc(title(w.agent))}</small></td><td><i style="--c:${colors[w.ability] || "#888"}"></i>${esc(w.ability_name)}</td>
            <td>${w.casts}</td><td>${w.rounds} of ${w.on_agent}</td><td>${w.per_round}</td></tr>`).join("") || `<tr><td colspan="5">No casts.</td></tr>`}</tbody></table>
        <p class="hint">"Used in" counts rounds the player was on that agent. Click a name to show only that player.</p>
      </section>
      ${st.view === "land" ? `<section class="blk"><p class="hint" style="margin:0">Landing spots are estimates for damaging utility (mollies, nanoswarms,
        shock darts…): placed along the aim at the distance that ability usually travels for that angle. On held-out matches the typical miss is
        ${data.landing.median_model_m} m, against ${data.landing.median_cast_m} m for the cast spot. Other utility stays at the cast spot.</p></section>` : ""}`;
    controls();
    if (modeled) segment(ui.rail.querySelector("#uview"), [["cast", "Cast spot"], ["land", "Landing (est.)"]], st.view, (k) => {
      st.view = k; st.focusHabit = null; setParams({ uview: k === "land" ? "land" : null }); renderRail(); drawLayers();
    }, "small wide");
    ui.rail.querySelector("#taim").addEventListener("change", (e) => { st.aim = e.target.checked; setParams({ aim: st.aim ? 1 : null }); drawLayers(); });
    ui.rail.querySelector("#tspots").addEventListener("change", (e) => { st.spots = e.target.checked; setParams({ spots: st.spots ? null : 0 }); drawLayers(); });
    ui.rail.querySelectorAll(".habits li").forEach((li) => li.addEventListener("click", () => focusHabit(+li.dataset.h)));
    ui.rail.querySelectorAll(".pchips button, .who .pl").forEach((b) => b.addEventListener("click", () => togglePlayer(b.dataset.p || null)));
  }

  function countBy(xs, f) { const o = {}; for (const x of xs) o[f(x)] = (o[f(x)] || 0) + 1; return o; }

  // ---- map ----
  async function showMap() {
    const t = token;
    geo = await api.map(st.map);
    if (t !== token || !alive) return;
    const mm = m();
    abilAll = Object.entries(countBy(mm.casts, (c) => c.ability)).sort((a, b) => b[1] - a[1]).map((x) => x[0]);
    colors = Object.fromEntries(abilAll.map((a, i) => [a, i < PALETTE.length ? PALETTE[i] : OTHER]));
    for (const a of [...st.hidden]) if (!abilAll.includes(a)) st.hidden.delete(a);
    const here = new Set(mm.casts.map((c) => c.player));
    for (const p of [...st.players]) if (!here.has(p)) st.players.delete(p); // a player who didn't play this map
    setParams({ player: [...st.players] });
    st.round = null; st.focusHabit = null;
    tip.hide();
    map = drawMap(ui.svg, geo, { floor: "#0f1924" });
    map.drawIn(900);
    renderRail();
    renderHud();
    renderLegend();
    drawLayers();
    ui.live.innerHTML = `<div class="rnav" id="rnav"></div><div class="lbody" id="lbody"></div>`;
    renderNav();
    ui.note.classList.remove("amber");
    ui.note.textContent = mm.casts.length ? "" : `No ${CLASS_LONG[st.cls]} recorded on ${title(st.map)} with these filters.`;
    ui.note.classList.toggle("on", !mm.casts.length);
    const tmax = Math.min(150, Math.max(100, Math.ceil(Math.max(0, ...mm.casts.map((c) => c.t)) / 10) * 10));
    tl?.destroy();
    tl = createTimeline(ui.strip, { min: BUY_FROM, max: tmax, start: BUY_FROM,
      segments: [{ from: BUY_FROM, to: 0, label: "Buy phase", color: COLORS.amb }, ...TIME.map((b) => ({ ...b, to: Math.min(b.to, tmax) }))],
      ticks: [], onTime: draw });
    if (mm.casts.length) setTimeout(() => alive && tl?.play(), 900);
  }

  function renderHud() {
    const mm = m(), casts = mm.casts.filter(mine);
    const side = data.side === "attacker" ? "attack" : data.side === "defender" ? "defense" : "both sides";
    ui.hud.innerHTML = `<b>${esc(title(st.map))}</b><span>${esc(CLASS_LONG[st.cls])} · ${esc(side)}${st.players.size ? ` · ${esc([...st.players].join(", "))}` : ""} ·
      ${casts.length} casts in ${new Set(casts.map((c) => c.round)).size} of ${mm.rounds} rounds</span>`;
  }

  function renderLegend() {
    const abil = abilAll.filter((a) => m().casts.some((c) => c.ability === a && mine(c)));
    const counts = countBy(m().casts.filter(mine), (c) => c.ability);
    const top = abil.slice(0, PALETTE.length), rest = abil.slice(PALETTE.length);
    const name = (a) => m().casts.find((c) => c.ability === a).ability_name;
    const restOff = rest.length && rest.every((a) => st.hidden.has(a));
    ui.legend.innerHTML = `<span style="color:var(--ink)" title="Where the player stood when casting (or the estimated landing in Landing view). Click an ability to hide or show it.">Dot = a cast · click to hide:</span>`
      + top.map((a) => `<button type="button" class="lg-ab${st.hidden.has(a) ? " off" : ""}" data-ab="${a}"><i style="--c:${colors[a]}"></i>${
        esc(name(a))} <small>${counts[a]}</small></button>`).join("")
      + (rest.length ? `<button type="button" class="lg-ab${restOff ? " off" : ""}" data-rest="1" title="${esc(rest.map(name).join(", "))}">
        <i style="--c:${OTHER}"></i>${rest.length} other abilit${rest.length === 1 ? "y" : "ies"} <small>${rest.reduce((n, a) => n + counts[a], 0)}</small></button>` : "");
    ui.legend.querySelectorAll(".lg-ab").forEach((b) => b.addEventListener("click", () => {
      const group = b.dataset.rest ? rest : [b.dataset.ab];
      const hide = !group.every((a) => st.hidden.has(a));
      for (const a of group) hide ? st.hidden.add(a) : st.hidden.delete(a);
      b.classList.toggle("off", hide);
      st.focusHabit = null;
      renderRail(); drawLayers();
    }));
  }

  /** (Re)build the cast dots, aim / throw lines and habit rings for the current view. */
  function drawLayers() {
    if (!map) return;
    map.layers.data.replaceChildren(); map.layers.under.replaceChildren(); map.layers.top.replaceChildren();
    // The rounds behind what's shown, oldest first: "Round 3 of 6" means the third of those.
    order = [...new Set(visibleCasts().map((c) => c.round))].sort((a, b) => {
      const ra = data.rounds[a], rb = data.rounds[b];
      return (ra.started || "").localeCompare(rb.started || "") || ra.game.localeCompare(rb.game) || ra.round_num - rb.round_num;
    });
    rank = new Map(order.map((r, i) => [r, i + 1]));
    layer = { dots: [], path: el("polyline", { fill: "none", stroke: "#fff", "stroke-opacity": .55, "stroke-width": 1.3, "stroke-dasharray": "4 4",
      "vector-effect": "non-scaling-stroke", points: "" }, map.layers.under) };
    for (const c of visibleCasts()) {
      const land = st.view === "land" && c.land;
      const at = land ? c.land : c.at, col = colors[c.ability];
      const g = el("g", { opacity: 0, class: "dot" }, map.layers.data);
      if (land) el("line", { x1: c.at[0], y1: c.at[1], x2: c.land[0], y2: c.land[1], stroke: col, "stroke-opacity": .45, "stroke-width": 1,
        "stroke-dasharray": "3 3", "vector-effect": "non-scaling-stroke" }, g);
      else if (aimOn() && c.aim) el("line", { x1: c.at[0], y1: c.at[1], x2: c.aim[0], y2: c.aim[1], stroke: col, "stroke-opacity": .5,
        "stroke-width": 1, "vector-effect": "non-scaling-stroke" }, g);
      el("circle", { cx: at[0], cy: at[1], r: 11, fill: col, opacity: .1 }, g);
      const core = el("circle", { cx: at[0], cy: at[1], r: 4, fill: col, stroke: COLORS.bg, "stroke-width": 1, "vector-effect": "non-scaling-stroke" }, g);
      core.addEventListener("mouseenter", (e) => {
        tip.show(e, `<b>${esc(c.player)}</b> (${esc(title(c.agent))}) used <b>${esc(c.ability_name)}</b> at ${esc(when(c))}${c.area ? ` near <b>${esc(c.area)}</b>` : ""}
          ${land ? `<br><span style="color:var(--dim)">Estimated landing; cast from the start of the dashed line.</span>` : ""}
          <div class="tip-round">${esc(roundLabel(c.round))}</div>${st.round == null ? `<div class="tip-hint">Click to watch this round</div>` : ""}`);
        if (st.round == null) highlight(c.round);
      });
      core.addEventListener("mousemove", (e) => tip.move(e));
      core.addEventListener("mouseleave", () => { tip.hide(); if (st.round == null) highlight(null); });
      core.addEventListener("click", () => watchRound(c.round));
      layer.dots.push({ g, c, at, shown: -1 });
    }
    if (st.spots) {
      const r = 4 * (geo.units_per_m || 7);
      habitsNow().forEach((h, i) => {
        const g = el("g", { class: `hring${st.focusHabit === i ? " on" : ""}` }, map.layers.top);
        el("circle", { cx: h.at[0], cy: h.at[1], r, fill: "rgba(255,255,255,.04)", stroke: "#fff", "stroke-width": 1.4, "stroke-dasharray": "4 3",
          "vector-effect": "non-scaling-stroke" }, g);
        const t = el("text", { x: h.at[0] + r * .75, y: h.at[1] - r * .75, fill: "#fff", "font-size": 16, "font-weight": 700, stroke: COLORS.bg,
          "stroke-width": 3, "paint-order": "stroke" }, g);
        t.textContent = MARKS[i];
        g.addEventListener("mouseenter", (e) => tip.show(e, `${MARKS[i]} <b>${esc(h.player)}</b>'s ${esc(h.ability_name)}${h.area ? ` near <b>${esc(h.area)}</b>` : ""}:
          same spot (within 4 m) in <b>${h.k} of ${h.n}</b> rounds on ${esc(title(h.agent))}`));
        g.addEventListener("mousemove", (e) => tip.move(e));
        g.addEventListener("mouseleave", () => tip.hide());
        g.addEventListener("click", () => focusHabit(i));
      });
    }
    if (tl) draw(tl.time, tl.mode);
  }

  function focusHabit(i) {
    const h = habitsNow()[i];
    if (!h) return;
    st.focusHabit = st.focusHabit === i ? null : i;
    ui.rail.querySelectorAll(".habits li").forEach((li) => li.classList.toggle("on", +li.dataset.h === st.focusHabit));
    map.layers.top.querySelectorAll(".hring").forEach((g, j) => g.classList.toggle("on", j === st.focusHabit));
    map.focus(st.focusHabit == null ? null : h.at, st.focusHabit == null ? 1 : 1.8, 900);
  }

  // ---- rounds ----
  function roundLabel(i) {
    const r = data.rounds[i];
    if (!r) return "";
    return `Round ${rank.get(i) ?? "?"} of ${order.length} here · map round ${r.round_num} vs ${r.opponent}, ${r.date}${r.won == null ? "" : r.won ? " · won" : " · lost"}`;
  }
  function highlight(i) {
    for (const d of layer.dots) d.g.classList.toggle("dim", i != null && d.c.round !== i);
    trace(i, tl ? tl.time : Infinity);
  }
  function trace(i, t) {
    if (i == null) { layer.path.setAttribute("points", ""); return; }
    layer.path.setAttribute("points", layer.dots.filter((d) => d.c.round === i && clampT(d.c.t) <= t).sort((a, b) => a.c.t - b.c.t)
      .map((d) => d.at.join(",")).join(" "));
  }
  function watchRound(i) {
    st.round = i;
    renderNav();
    for (const d of layer.dots) d.g.classList.remove("dim");
    if (i == null) { trace(null); tl?.set(tl.time); return; }
    tl?.pause(); tl?.set(BUY_FROM);
    setTimeout(() => alive && st.round === i && tl?.play(), 250);
  }
  function step(dir) {
    if (!order.length) return;
    const pos = st.round == null ? -1 : order.indexOf(st.round);
    watchRound(order[(pos + dir + order.length) % order.length]);
  }
  function renderNav() {
    const nav = ui.live.querySelector("#rnav");
    if (!nav) return;
    if (st.round == null) {
      nav.innerHTML = `<span><b>${order.length}</b> round${order.length === 1 ? "" : "s"} overlaid by time in round</span>
        ${order.length ? `<button type="button" data-act="watch">Watch one round ›</button>` : ""}`;
    } else {
      const r = data.rounds[st.round];
      nav.innerHTML = `<div class="rstep"><button type="button" data-act="prev" aria-label="Previous round">‹</button>
        <b>Round ${rank.get(st.round)} of ${order.length}</b><button type="button" data-act="next" aria-label="Next round">›</button>
        <button type="button" data-act="all" class="rall">All rounds ✕</button></div>
        <div class="rsub">map round ${r.round_num} vs ${esc(r.opponent)} · ${esc(r.date)} · <span class="${r.won ? "won" : "lost"}">${r.won ? "won" : "lost"}</span></div>`;
    }
  }
  ui.live.addEventListener("click", (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (act === "watch" || act === "next") step(1);
    else if (act === "prev") step(-1);
    else if (act === "all") watchRound(null);
  }, { signal: live.signal });
  addEventListener("keydown", (e) => {
    if (e.target.closest?.("input, textarea") || !document.getElementById("palette").hidden) return;
    if (e.key === "]") step(1);
    else if (e.key === "[") step(-1);
    else if (e.key === "Escape" && st.round != null) watchRound(null);
  }, { signal: live.signal });

  // ---- what the clock shows ----
  function draw(t, mode) {
    if (!layer || !data) return;
    const only = st.round;
    let n = 0;
    const rounds = new Set(), byAb = {};
    for (const d of layer.dots) {
      const ct = clampT(d.c.t), age = t - ct;
      const on = (only == null || d.c.round === only) && age >= 0 && (mode === "build" || age <= MOMENT);
      const op = !on ? 0 : mode === "build" ? 1 : 1 - (age / MOMENT) * 0.85;
      if (op !== d.shown) { d.g.setAttribute("opacity", op); d.shown = op; }
      if (on) { n++; rounds.add(d.c.round); byAb[d.c.ability_name] = (byAb[d.c.ability_name] || 0) + 1; }
    }
    if (only != null) trace(only, t);
    const body = ui.live.querySelector("#lbody");
    if (body) body.innerHTML = only != null ? story(only, t) : summary(t, mode, n, rounds, byAb);
    ui.live.classList.toggle("in", !!m().casts.length);
    ui.stage.classList.toggle("carded", !!m().casts.length);
  }

  function summary(t, mode, n, rounds, byAb) {
    const top = Object.entries(byAb).sort((a, b) => b[1] - a[1]).slice(0, 4);
    const span = mode === "build" ? `by ${clockLabel(t)}` : `${clockLabel(t - MOMENT)}–${clockLabel(t)}`;
    return `<div class="k">Utility out ${span}${t < 0 ? " · buy phase" : ""}</div>
      <div class="seen"><b>${n}</b> cast${n === 1 ? "" : "s"} in <b>${rounds.size}</b> of ${m().rounds} rounds</div>
      ${top.length ? `<ol>${top.map(([a, k]) => `<li><span>${esc(a)}</span><span class="mbar"><i style="width:${(k / Math.max(1, n)) * 100}%"></i></span>
        <span>${k}</span></li>`).join("")}</ol>` : `<p>Nothing cast yet.</p>`}
      <p class="fine">Dots are where the player stood when casting, from the ability supplement (in VCT Americas 2025 recorded once a second, so a
        moving player can be a few metres off). GRID doesn't record where utility lands: turn on Aim direction, or Landing (est.) for damaging utility.</p>`;
  }

  function story(i, t) {
    const ev = m().casts.filter((c) => c.round === i && mine(c) && !st.hidden.has(c.ability)).sort((a, b) => a.t - b.t);
    return `<div class="k">Utility in this round</div><ol class="rstory">${ev.map((c) => `
      <li class="${clampT(c.t) <= t ? "past" : ""}${clampT(c.t) <= t && t - clampT(c.t) < 2 ? " now" : ""}"><span class="st">${clockLabel(c.t)}</span>
        <span><b>${esc(c.player)}</b> · ${esc(c.ability_name)}${c.area ? ` · ${esc(c.area)}` : ""}</span></li>`).join("")}</ol>
      <p class="fine">Negative times are the buy phase. [ and ] step rounds.</p>`;
  }

  function pickMap(name) {
    if (!name || !data?.maps[name]) return;
    st.map = name;
    setParams({ map: name });
    ui.setMap(name);
    showMap();
  }
  ui.onMap((name) => {
    if (!name && data) { name = data.maps_order[0]; ui.setMap(name); }
    pickMap(name);
  });
  ui.onSide((side) => { st.side = side; setParams({ side }); load(); });
  ui.zoom((f) => map?.focus(f > 1 ? [map.base[0] + map.base[2] / 2, map.base[1] + map.base[3] / 2] : null, f, 400));

  load();
  return () => {
    alive = false; live.abort(); tl?.destroy(); tl = null;
    ui.live.classList.remove("in"); ui.live.innerHTML = ""; ui.stage.classList.remove("carded"); ui.setBadges(null);
    ui.note.classList.remove("on");
  };
}
