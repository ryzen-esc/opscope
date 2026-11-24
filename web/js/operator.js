// Dashboard · Operator tab: who holds the gun, how often against the typical team, and where the holder is as the
// round plays out. The timeline drives the map: dots are moments GRID recorded the holder (shots, hits taken,
// ability casts), lines are kills with the gun (ring at the shooter, ✕ at the victim).
import { api } from "./api.js";
import { evidenceBar } from "./evidence.js";
import { COLORS, drawMap, el } from "./map.js";
import { countUp } from "./motion.js";
import { esc } from "./overview.js";
import { clockLabel, createTimeline } from "./timeline.js";
import { segment } from "./ui.js";

const WEAPONS = [["operator", "Operator"], ["odin", "Odin"], ["outlaw", "Outlaw"], ["marshal", "Marshal"]];
// Time in round as a cool-to-warm ramp (red stays reserved for kills and attack).
export const TIME = [
  { from: 0, to: 20, label: "0–20s", color: "#8be4ff" },
  { from: 20, to: 40, label: "20–40s", color: "#2f9cff" },
  { from: 40, to: 60, label: "40–60s", color: "#8a7dff" },
  { from: 60, to: 999, label: "60s+", color: "#d46bff" },
];
const timeColor = (t) => (TIME.find((b) => t < b.to) || TIME[3]).color;
const title = (s) => String(s || "").replace(/\b\w/g, (c) => c.toUpperCase());
const pct = (v) => `${Math.round(v * 100)}%`;
const MOMENT = 5; // seconds a dot stays visible in Moment mode
const MIN_SAMPLE = 8;

function wilson(k, n) {
  if (!n) return [0, 0];
  const z = 1.96, p = k / n, d = 1 + z * z / n, c = (p + z * z / (2 * n)) / d, h = (z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d;
  return [Math.max(0, c - h), Math.min(1, c + h)];
}

export function renderOperator(ui, { team, filters, params, setParams, tip }) {
  const st = { weapon: params.get("weapon") || "operator", side: params.get("side") || "defender", map: params.get("map") || "" };
  if (st.side === "both" && !params.get("side")) st.side = "defender";
  let data = null, map = null, tl = null, layer = null, token = 0, alive = true;
  ui.setSide(st.side);

  async function load() {
    const t = ++token;
    ui.rail.innerHTML = `<div class="rail-loading">Crunching ${esc(WEAPONS.find((w) => w[0] === st.weapon)[1])} rounds…</div>`;
    let d;
    try { d = await api.operator(team, { weapon: st.weapon, side: st.side, ...filters }); }
    catch (e) { if (t === token) ui.rail.innerHTML = `<p class="empty-note">Couldn't load: ${esc(e.message)}</p>`; return; }
    if (t !== token || !alive) return;
    data = d;
    if (d.empty) {
      ui.rail.innerHTML = `<div class="op-head" id="weapons"></div><p class="empty-note">No rounds match these filters.</p>`;
      weaponSeg();
      return;
    }
    const best = [...d.by_map].sort((a, b) => b.k - a.k || b.n - a.n)[0]?.map;
    if (!st.map || !d.by_map.some((m) => m.map === st.map)) st.map = best;
    ui.setMap(st.map);
    ui.setBadges(Object.fromEntries(d.by_map.map((m) => [m.map, m.k ? `${m.k}` : ""])));
    renderRail();
    await showMap();
  }

  function weaponSeg() {
    segment(ui.rail.querySelector("#weapons"), WEAPONS, st.weapon, (k) => { st.weapon = k; setParams({ weapon: k === "operator" ? null : k }); load(); }, "small wide");
  }

  // ---- the rail: the evidence, one block at a time ----
  function renderRail() {
    const d = data, r = d.rate, side = d.side === "attacker" ? "attack" : d.side === "defender" ? "defense" : "all";
    const m = d.maps[st.map] || { gun_rounds: 0, rounds: 0 };
    const maxShare = Math.max(0.5, ...d.by_map.map((x) => (x.n ? x.k / x.n : 0)));
    const holders = d.holders.slice(0, 6), maxH = Math.max(1, ...holders.map((h) => h.rounds));
    const fsMax = Math.max(1, ...d.first_shot.map((b) => b.rounds));
    const wr = (k, n) => `<b>${n ? pct(k / n) : "—"}</b> <span>${k} of ${n}</span>`;
    ui.rail.innerHTML = `
      <div class="op-head"><div id="weapons"></div></div>
      <section class="blk">
        <div class="k">${esc(d.gun)} · ${esc(side)} rounds · ${esc(d.name)}</div>
        <div class="bigrow"><span class="big" id="opbig">${pct(r.rate)}</span>
          <span class="of"><b>${r.k}</b> of <b>${r.n}</b> ${esc(d.unit)} with the ${esc(d.gun)}<br><span class="peer">${esc(r.peers)}: ${pct(r.base)}</span></span></div>
        <div id="opbar"></div>
        <p class="glance">${d.glance[0] || ""}</p>
      </section>
      <section class="blk">
        <h4>Rate by map <span>click to view</span></h4>
        <ul class="bymap">${d.by_map.map((x) => `<li data-m="${x.map}" class="${x.map === st.map ? "on" : ""}">
          <span>${esc(title(x.map))}</span>
          <span class="mbar"><i style="width:${x.n ? (x.k / x.n / maxShare) * 100 : 0}%"></i><em style="left:${(r.base / maxShare) * 100}%"></em></span>
          <span>${x.k}/${x.n}</span></li>`).join("")}</ul>
        <p class="hint">Tick: ${esc(r.peers)} (${pct(r.base)}, all maps, same side and filters).</p>
        ${d.glance.slice(1).map((g) => `<p class="glance">${g}</p>`).join("")}
      </section>
      <section class="blk">
        <h4>Who holds it</h4>
        <ul class="holders">${holders.map((h) => `<li><span>${esc(h.player)} <small>${esc(title(h.agent))}</small></span>
          <span class="mbar"><i style="width:${(h.rounds / maxH) * 100}%"></i></span><span>${h.rounds}</span></li>`).join("") || "<li>Nobody in these rounds.</li>"}</ul>
      </section>
      <section class="blk">
        <h4>When it first fires <span>${d.fired_rounds} of ${r.k} ${esc(d.gun)} rounds</span></h4>
        <div class="fs">${d.first_shot.map((b, i) => `<div><span class="col" style="height:${(b.rounds / fsMax) * 100}%;background:${TIME[i].color}"></span>
          <b>${b.rounds}</b><small>${esc(b.bucket)}</small></div>`).join("")}</div>
      </section>
      <section class="blk two">
        <div><h4>Full buys won with it</h4><p class="wr">${wr(...d.full_buy.with)}</p><div id="wwith"></div></div>
        <div><h4>Full buys won without</h4><p class="wr">${wr(...d.full_buy.without)}</p><div id="wwithout"></div></div>
        <p class="hint" style="grid-column:1/-1">Bands are 95% ranges: where they overlap, the gun makes no clear difference.</p>
      </section>
      <section class="blk">
        <h4>Survived with it</h4><p class="wr">${wr(d.kept.k, d.kept.n)} <span>${esc(d.gun)} rounds (it carries into the next round)</span></p>
        ${d.aggression ? `<h4 style="margin-top:14px">Early setup (first 30 s)</h4><p class="glance">Median position further forward than
          <b>${pct(d.aggression.percentile)}</b> of other teams' ${esc(d.gun)} setups on this map (seen in ${d.aggression.n} rounds).</p>` : ""}
      </section>`;
    weaponSeg();
    const bar = evidenceBar({ ...r, k: r.k, n: r.n }, { side: d.side === "attacker" ? "attacker" : "defender", baseLabel: "typical" });
    ui.rail.querySelector("#opbar").appendChild(bar.node);
    bar.play(100);
    countUp(ui.rail.querySelector("#opbig"), r.rate * 100, { fmt: (v) => `${Math.round(v)}%`, ms: 900 });
    for (const [id, [k, n]] of [["#wwith", d.full_buy.with], ["#wwithout", d.full_buy.without]]) {
      const [lo, hi] = wilson(k, n);
      if (n) ui.rail.querySelector(id).appendChild(evidenceBar({ k, n, rate: k / n, lo, hi, base: null }, { labels: false }).node);
    }
    ui.rail.querySelectorAll(".bymap li").forEach((li) => li.addEventListener("click", () => pickMap(li.dataset.m)));
  }

  // ---- the map, driven by the timeline ----
  async function showMap() {
    const t = token;
    const geo = await api.map(st.map);
    if (t !== token || !alive) return;
    const m = data.maps[st.map] || { positions: [], kills: [], gun_rounds: 0, rounds: 0 };
    tip.hide(); // the dot under the pointer is about to go
    map = drawMap(ui.svg, geo, { floor: "#0f1924" });
    map.drawIn(900);
    const side = data.side === "attacker" ? "attack" : data.side === "defender" ? "defense" : "both sides";
    ui.hud.innerHTML = `<b>${esc(title(st.map))}</b><span>${esc(data.gun)} · ${esc(side)} · ${m.gun_rounds} of ${m.rounds} rounds with it</span>`;
    ui.legend.innerHTML = TIME.map((b) => `<span><i style="--c:${b.color}"></i>${b.label}</span>`).join("")
      + `<span><i style="--c:transparent;border:2px solid ${COLORS.atk}"></i>${esc(data.gun)} kill: shooter → ✕ victim</span>`;
    layer = { dots: [], kills: [] };
    for (const p of m.positions) {
      const g = el("g", { opacity: 0, class: "dot" }, map.layers.data);
      el("circle", { cx: p.at[0], cy: p.at[1], r: 15, fill: timeColor(p.t), opacity: .1 }, g);
      const core = el("circle", { cx: p.at[0], cy: p.at[1], r: 4.5, fill: timeColor(p.t), stroke: COLORS.bg, "stroke-width": 1,
        "vector-effect": "non-scaling-stroke" }, g);
      core.addEventListener("mouseenter", (e) => tip.show(e, `<b>${esc(p.player)}</b> (${esc(title(p.agent))}) · ${clockLabel(p.t)}<br>
        ${p.area ? `near <b>${esc(p.area)}</b> · ` : ""}${esc(p.via)} · round ${p.round + 1}`));
      core.addEventListener("mousemove", (e) => tip.move(e));
      core.addEventListener("mouseleave", () => tip.hide());
      layer.dots.push({ g, p, shown: -1 });
    }
    for (const k of m.kills) {
      const g = el("g", { opacity: 0 }, map.layers.top);
      const ln = el("line", { x1: k.from[0], y1: k.from[1], x2: k.to[0], y2: k.to[1], stroke: COLORS.atk, "stroke-width": 1.6,
        "vector-effect": "non-scaling-stroke", pathLength: 1, "stroke-dasharray": "1 1", "stroke-dashoffset": 1 }, g);
      el("circle", { cx: k.from[0], cy: k.from[1], r: 9, fill: "none", stroke: COLORS.atk, "stroke-width": 1.8, "vector-effect": "non-scaling-stroke" }, g);
      const x = el("path", { d: `M${k.to[0] - 7} ${k.to[1] - 7}L${k.to[0] + 7} ${k.to[1] + 7}M${k.to[0] + 7} ${k.to[1] - 7}L${k.to[0] - 7} ${k.to[1] + 7}`,
        stroke: COLORS.atk, "stroke-width": 2, "vector-effect": "non-scaling-stroke", opacity: 0 }, g);
      layer.kills.push({ g, ln, x, k });
    }
    note(m);
    // The clock: up to 100 s, or the latest moment if the gun is still out later.
    const tmax = Math.min(150, Math.max(100, Math.ceil(Math.max(0, ...m.positions.map((p) => p.t), ...m.kills.map((k) => k.t)) / 10) * 10));
    tl?.destroy();
    tl = createTimeline(ui.strip, { min: 0, max: tmax, start: 0, segments: TIME.map((b) => ({ ...b, to: Math.min(b.to, tmax) })),
      ticks: m.kills.map((k) => k.t), onTime: draw });
    if (m.positions.length || m.kills.length) setTimeout(() => alive && tl?.play(), 900);
  }

  function note(m) {
    let msg = "";
    if (!m.gun_rounds) msg = `No ${data.gun} on ${title(st.map)}: 0 of ${m.rounds} ${data.unit}. That absence is the finding.`;
    else if (m.gun_rounds < MIN_SAMPLE) msg = `Only ${m.gun_rounds} ${data.gun} round${m.gun_rounds === 1 ? "" : "s"} here: too few to read a setup.`;
    ui.note.textContent = msg;
    ui.note.classList.toggle("on", !!msg);
    ui.note.classList.toggle("amber", !!msg);
  }

  // ---- what the timeline shows at time t ----
  function draw(t, mode) {
    if (!layer) return;
    const m = data.maps[st.map];
    const seen = new Set(), areas = new Map();
    for (const d of layer.dots) {
      const age = t - d.p.t;
      const on = age >= 0 && (mode === "build" || age <= MOMENT);
      const op = !on ? 0 : mode === "build" ? 1 : 1 - (age / MOMENT) * 0.85;
      if (op !== d.shown) { d.g.setAttribute("opacity", op); d.shown = op; }
      if (on) {
        seen.add(d.p.round);
        if (d.p.area) { if (!areas.has(d.p.area)) areas.set(d.p.area, new Set()); areas.get(d.p.area).add(d.p.round); }
      }
    }
    let kills = 0;
    for (const k of layer.kills) {
      const age = t - k.k.t;
      const visible = age >= 0 && (mode === "build" || age <= MOMENT);
      const q = Math.max(0, Math.min(1, age / 1.2));
      k.g.setAttribute("opacity", visible ? (mode === "build" ? 1 : 1 - (age / MOMENT) * 0.7) : 0);
      k.ln.setAttribute("stroke-dashoffset", 1 - q);
      k.x.setAttribute("opacity", q >= 1 ? 1 : 0);
      if (visible && q >= 1) kills++;
    }
    const top = [...areas.entries()].map(([a, s]) => [a, s.size]).sort((a, b) => b[1] - a[1]).slice(0, 3);
    const span = mode === "build" ? `by ${clockLabel(t)}` : `${clockLabel(Math.max(0, t - MOMENT))}–${clockLabel(t)}`;
    ui.live.innerHTML = m.gun_rounds ? `
      <div class="k">Where the holder is · ${span}</div>
      <div class="seen"><b>${seen.size}</b> of ${m.gun_rounds} ${esc(data.gun)} rounds seen · <b>${kills}</b> kill${kills === 1 ? "" : "s"}</div>
      ${top.length ? `<ol>${top.map(([a, n]) => `<li><span>${esc(a)}</span><span class="mbar"><i style="width:${(n / Math.max(1, seen.size)) * 100}%"></i></span>
        <span>${n} of ${seen.size}</span></li>`).join("")}</ol>` : `<p>No recorded moments yet.</p>`}
      <p class="fine">GRID records a position only when the holder shoots, gets hit or uses an ability (±1–4 m), so quiet rounds leave gaps.</p>` : "";
    ui.live.classList.toggle("in", !!m.gun_rounds);
    ui.stage.classList.toggle("carded", !!m.gun_rounds);
  }

  function pickMap(name) {
    if (!name || !data) return;
    st.map = name;
    setParams({ map: name });
    ui.setMap(name);
    ui.rail.querySelectorAll(".bymap li").forEach((li) => li.classList.toggle("on", li.dataset.m === name));
    renderRail();
    showMap();
  }

  ui.onMap((name) => {
    if (!name && data) { // "All maps" makes no sense for a map of positions: go back to the busiest map
      name = [...data.by_map].sort((a, b) => b.k - a.k || b.n - a.n)[0]?.map;
      ui.setMap(name);
    }
    pickMap(name);
  });
  ui.onSide((side) => { st.side = side; setParams({ side }); load(); });
  ui.zoom((f) => map?.focus(f > 1 ? [(map.base[0] + map.base[2] / 2), (map.base[1] + map.base[3] / 2)] : null, f, 400));

  load();
  return () => { alive = false; tl?.destroy(); tl = null; ui.live.classList.remove("in"); ui.stage.classList.remove("carded"); ui.setBadges(null); };
}
