// Dashboard · Briefing tab: every tendency in a ranked list, on the map, with its evidence card and where the team
// plants on the map in view.
import { api } from "./api.js";
import { evidenceBar } from "./evidence.js";
import { COLORS, drawMap, el, findingAt } from "./map.js";
import { countUp } from "./motion.js";
import { esc } from "./overview.js";
import { oneOf } from "./ui.js";

const title = (s) => String(s || "").replace(/\b\w/g, (c) => c.toUpperCase());
const pct = (v) => `${Math.round(v * 100)}%`;
const sideCls = (s) => (s === "attacker" ? "atk" : "def");
const sideWord = (s) => (s === "attacker" ? "Attack" : "Defense");
const plain = (h) => String(h || "").replace(/<[^>]+>/g, "");

/** What to do about it, without repeating the finding: the tip alone for a self-scout, the action plus why for an
 * opponent. */
function adviceText(advice, ev, selfScout) {
  const detail = plain(advice.detail);
  const tip = detail.startsWith(ev.sample) ? detail.split(". ").slice(1).join(". ") : detail;
  return selfScout ? esc(tip) : `<b>${advice.headline}.</b> ${esc(tip)}`;
}

export function renderBriefing(ui, { rep, params, setParams, goTab, tip, filterBanner = "" }) {
  const disposers = [];
  const cats = [["All", "All"], ["Operator", "Gun choice"], ["Utility", "Utility habit"], ["Attack", "Plant site"]];
  // URL values are checked on read (a hand-edited link, or a sel kept from before the filters changed).
  const st = { cat: oneOf(params.get("cat"), cats, "All"), sel: null,
    map: oneOf(params.get("map"), rep.pool.map((p) => p.map), ""), side: oneOf(params.get("side"), ["attacker", "defender"], "both") };
  // Each plan item names its finding's exact position in the list (several findings can share map, side and counts).
  const planAt = new Map(rep.plan.map((p, j) => [p.index, j]).filter(([i]) => i >= 0));
  const items = rep.insights.map((ev, i) => {
    const plan = planAt.has(i) ? planAt.get(i) : -1;
    return { ev, i, advice: plan >= 0 ? rep.plan[plan] : null, plan: plan >= 0 ? plan + 1 : null };
  });
  if (/^\d+$/.test(params.get("sel") || "") && +params.get("sel") < items.length) st.sel = +params.get("sel");
  const rank = (i) => `#${i + 1}`;
  const planTag = (n) => `Plan ${String(n).padStart(2, "0")}`;
  let map = null, mapName = null, token = 0;

  const visible = () => items.filter(({ ev }) => (st.cat === "All" || ev.category === st.cat)
    && (!st.map || ev.map === st.map) && (st.side === "both" || ev.side === st.side));

  // ---- rail ----
  const r = rep.record;
  ui.rail.innerHTML = `
    <div class="rail-head"><div class="k">${rep.self_scout ? "Self-scout" : "Opponent dossier"} · ${esc(rep.peers)}</div>
      <h2>${esc(rep.name)}</h2>
      <div class="nums"><span><b>${r.wins}–${r.games - r.wins}</b>maps</span>
        <span><b style="color:var(--atk)">${pct(r.atk_won / r.atk_n)}</b>atk rounds</span>
        <span><b style="color:var(--def)">${pct(r.def_won / r.def_n)}</b>def rounds</span></div></div>
    ${filterBanner}
    <div class="cats" id="cats"></div>
    <div class="listhelp" id="listhelp"></div>
    <ol class="items" id="items"></ol>
    <p class="rail-foot">${esc(rep.rule)}</p>`;
  const catsEl = ui.rail.querySelector("#cats"), listEl = ui.rail.querySelector("#items");

  function renderCats() {
    const base = items.filter(({ ev }) => (!st.map || ev.map === st.map) && (st.side === "both" || ev.side === st.side));
    catsEl.innerHTML = cats.map(([key, label]) => {
      const n = key === "All" ? base.length : base.filter(({ ev }) => ev.category === key).length;
      return `<button type="button" data-cat="${key}" class="${st.cat === key ? "on" : ""}">${key === "All" ? "All" : esc(label)}<span>${n}</span></button>`;
    }).join("");
    catsEl.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      st.cat = b.dataset.cat; setParams({ cat: st.cat === "All" ? null : st.cat }); renderCats(); renderList(); drawLayers();
    }));
  }

  function renderHelp(vis) {
    const narrowed = [st.map && title(st.map), st.side !== "both" && sideWord(st.side), st.cat !== "All" && cats.find((c) => c[0] === st.cat)[1]]
      .filter(Boolean);
    ui.rail.querySelector("#listhelp").innerHTML = `
      <div><b>${vis.length}</b> of ${items.length} tendencies${narrowed.length ? ` · ${esc(narrowed.join(" · "))}` : ""}</div>
      <div><b>#</b> rank: #1 is the most unusual and best supported. Ranks don't change when you narrow the list.
        <span class="plan-tag">Plan 01</span> = its number in the overview's ${rep.self_scout ? "list of habits to vary" : "game plan"}.</div>`;
  }

  function renderList() {
    const vis = visible();
    renderHelp(vis);
    if (!vis.length) {
      listEl.innerHTML = `<li class="empty-note">Nothing ${st.map ? `on ${esc(title(st.map))}` : "here"} differs from the typical
        ${esc(rep.peers)} team by enough to be sure (a tendency needs its 95% range clear of the typical rate, with 8+ rounds).</li>`;
      return;
    }
    listEl.innerHTML = vis.map(({ ev, i }) => `
      <li class="item ${sideCls(ev.side)}${st.sel === i ? " on" : ""}" data-i="${i}" tabindex="0">
        <div class="i" title="Rank ${i + 1} of ${items.length}">${rank(i)}</div>
        <div class="t">${ev.text}</div>
        <div class="meta"><span class="chip ${sideCls(ev.side)}">${ev.side === "attacker" ? "ATK" : "DEF"}</span>${esc(ev.label)} · ${esc(title(ev.map))} · ${ev.k}/${ev.n}${
          items[i].plan ? `<span class="plan-tag">${planTag(items[i].plan)}</span>` : ""}</div>
        ${ev.departed ? `<div class="departed">${esc(ev.departed)}</div>` : ""}
        <div class="eb"></div></li>`).join("");
    listEl.querySelectorAll(".item").forEach((li) => {
      const ev = items[+li.dataset.i].ev;
      const b = evidenceBar(ev, { side: ev.side, labels: false });
      li.querySelector(".eb").appendChild(b.node);
      li.addEventListener("click", () => select(+li.dataset.i));
      li.addEventListener("keydown", (e) => { if (e.key === "Enter") select(+li.dataset.i); });
    });
  }

  // ---- map ----
  async function showMap(name) {
    const t = ++token;
    const geo = await api.map(name);
    if (t !== token) return null;
    if (mapName !== name) {
      tip.hide();
      map = drawMap(ui.svg, geo, { floor: "#111c28" });
      mapName = name;
      map.drawIn(1000);
      ui.hud.innerHTML = `<b>${esc(title(name))}</b><span>${rep.plants.find((p) => p.map === name)?.planted ?? 0} plants · ${
        items.filter(({ ev }) => ev.map === name).length} tendencies</span>`;
      renderStrip(name);
    }
    return map;
  }

  function drawLayers() {
    if (!map) return;
    map.layers.data.innerHTML = "";
    const plants = rep.plants.find((p) => p.map === mapName);
    for (const s of map.geo.sites || []) {
      const row = plants?.sites.find((x) => x.site === s.name);
      if (!row) continue;
      const t = el("text", { x: s.at[0], y: s.at[1] + 30, fill: COLORS.amb, "font-size": 12, "font-family": "JetBrains Mono, monospace",
        "text-anchor": "middle", opacity: .8, stroke: COLORS.bg, "stroke-width": 3, "paint-order": "stroke" }, map.layers.data);
      t.textContent = `${row.k} plant${row.k === 1 ? "" : "s"}`;
    }
    for (const it of visible()) {
      const { ev, i } = it;
      if (ev.map !== mapName || ev.category === "Attack") continue;
      const at = findingAt(map.geo, ev);
      if (!at) continue;
      const color = ev.side === "attacker" ? COLORS.atk : COLORS.def;
      const g = el("g", { class: "marker", transform: `translate(${at[0]} ${at[1]})`, tabindex: 0 }, map.layers.data);
      if (ev.category === "Utility") el("rect", { class: "mk", x: -7, y: -7, width: 14, height: 14, transform: "rotate(45)", fill: color,
        stroke: COLORS.bg, "stroke-width": 1.5, "vector-effect": "non-scaling-stroke" }, g);
      else {
        el("circle", { class: "mk", r: 11, fill: "none", stroke: color, "stroke-width": 2, "vector-effect": "non-scaling-stroke" }, g);
        el("circle", { r: 3.5, fill: color }, g);
      }
      el("circle", { r: 20, fill: "transparent" }, g); // a bigger hit area
      g.addEventListener("click", () => select(i));
      g.addEventListener("mouseenter", (e) => tip.show(e, `<b>${rank(i)}</b> ${esc(plain(ev.text).slice(0, 140))}…`));
      g.addEventListener("mousemove", (e) => tip.move(e));
      g.addEventListener("mouseleave", () => tip.hide());
    }
  }

  function renderStrip(name) {
    const p = rep.plants.find((x) => x.map === name);
    if (!p || !p.sites.length) {
      ui.strip.innerHTML = `<div class="ttl">Where they plant<b>${esc(title(name))}</b></div><p class="note">No plants recorded for this team on this map.</p>`;
      return;
    }
    ui.strip.innerHTML = `<div class="ttl">Where they plant<b>${esc(title(name))} attack</b></div>
      <div class="sites">${p.sites.map((s) => `<div class="site"><div class="row1"><b>${esc(s.site.replace(" site", ""))}</b>
        <span><span style="color:var(--ink)">${pct(s.rate || 0)}</span> · ${s.k} of ${s.n} plants</span></div>
        <div class="tr"><div class="fi" data-w="${(s.rate || 0) * 100}"></div>${s.base != null ? `<div class="lg" style="left:${s.base * 100}%"></div>` : ""}</div>
        ${s.base != null ? `<div class="lgl" style="left:${s.base * 100}%">typical ${pct(s.base)}</div>` : ""}</div>`).join("")}</div>
      <p class="note">Bar: share of their ${p.planted} plants (from ${p.attack_rounds} attack rounds). Tick: the ${esc(p.peers)}.</p>`;
    requestAnimationFrame(() => ui.strip.querySelectorAll(".fi").forEach((f) => (f.style.width = `${f.dataset.w}%`)));
  }

  // ---- selection + evidence card ----
  async function select(i, { fromKey = false } = {}) {
    st.sel = i;
    setParams({ sel: i == null ? null : i });
    listEl.querySelectorAll(".item").forEach((li) => li.classList.toggle("on", +li.dataset.i === i));
    ui.stage.classList.toggle("carded", i != null);
    if (i == null) { ui.note.classList.remove("on"); ui.card.classList.remove("in"); map?.layers.top.replaceChildren(); map?.highlightSite(null); map?.focus(null, 1, 700); return; }
    const { ev, advice } = items[i];
    const li = listEl.querySelector(`[data-i="${i}"]`);
    li?.scrollIntoView({ block: "nearest", behavior: fromKey ? "auto" : "smooth" });
    const fresh = mapName !== ev.map;
    const m = await showMap(ev.map);
    if (!m || st.sel !== i) return;
    drawLayers();
    m.layers.top.replaceChildren();
    m.highlightSite(null);
    const color = ev.side === "attacker" ? COLORS.atk : COLORS.def;
    const at = findingAt(m.geo, ev);
    setTimeout(() => {
      if (st.sel !== i) return;
      const shift = 0; // the map already moved into the space left of the evidence card
      if (ev.category === "Attack" && ev.tags?.site) { m.highlightSite(ev.tags.site); if (at) m.focus(at, 1.25, 1000, { shift }); }
      else if (at) { m.focus(at, 1.5, 1000, { shift }); m.pulse(at, color, null, { r: 22 }); }
      else m.focus(null, 1, 700);
    }, fresh ? 700 : 0);
    ui.note.textContent = ev.category === "Attack" ? "" : (at ? "" : "Whole map: this finding has no single spot");
    ui.note.classList.toggle("on", !!ui.note.textContent);
    renderCard(ev, advice, i);
  }

  /** Why a finding has no pin on the map, in one line (null when it has one). */
  function noSpotNote(ev) {
    if (ev.category === "Attack") return "On the map: the highlighted site is where they plant.";
    if (map && findingAt(map.geo, ev)) return null;
    if (ev.category === "Operator") return ev.tags?.direction === "less"
      ? `No single spot: this is about how rarely they buy the ${esc(ev.tags?.label || "Operator")} on this map, so the whole map is shown.`
      : `No single spot: the holder isn't seen in one area often enough to name it, so the whole map is shown.`;
    return "No single spot for this one, so the whole map is shown.";
  }

  function renderCard(ev, advice, i) {
    const c = ui.card;
    const noSpot = noSpotNote(ev);
    c.classList.remove("in");
    const base = ev.category === "Utility" ? "typical player" : "typical team";
    // The link opens the tab as the finding was measured: Utility settings left from an earlier visit (phase, players,
    // landing view) would recompute the habits and could hide the one this card is about.
    const target = ev.category === "Operator" ? { tab: "operator", weapon: ev.tags?.weapon, map: ev.map, side: ev.side }
      : ev.category === "Utility" ? { tab: "utility", classes: ev.tags?.util_class, map: ev.map, side: ev.side,
        phase: null, uview: null, aim: null, spots: null, player: null } : null;
    setTimeout(() => {
      c.innerHTML = `<button class="x" type="button" aria-label="Close">×</button>
        <div class="k"><span class="chip ${sideCls(ev.side)}">${sideWord(ev.side)}</span>${esc(ev.label)} · ${esc(title(ev.map))}</div>
        <div class="big" style="color:${ev.side === "attacker" ? "var(--atk)" : "var(--def)"}"><span id="cbig">0</span>%</div>
        <div class="of"><b>${ev.k}</b> of <b>${ev.n}</b> ${esc(ev.unit)}${ev.base != null ? ` · ${esc(ev.peers)} ${pct(ev.base)}` : ""}</div>
        <div class="txt">${ev.text}</div>
        <div id="cbar"></div>
        ${advice ? `<div class="advice"><small>${rep.self_scout ? "WORTH VARYING" : "GAME PLAN"}</small>${adviceText(advice, ev, rep.self_scout)}</div>` : ""}
        ${ev.departed ? `<div class="advice" style="border-color:var(--amb)">${esc(ev.departed)}</div>` : ""}
        ${noSpot ? `<div class="nospot">${noSpot}</div>` : ""}
        <div class="src">95% range ${pct(ev.lo)}–${pct(ev.hi)}${ev.base != null ? `, clear of the ${base} (${pct(ev.base)})` : ""}.
          Rank ${rank(i)} of ${items.length}${items[i].plan ? ` · ${planTag(items[i].plan)} in the overview` : ""}.</div>
        ${target ? `<a class="go" href="#" id="cgo">See the ${ev.category === "Operator" ? esc(ev.tags?.label || "Operator") : "utility"} on ${esc(title(ev.map))}, round by round →</a>` : ""}`;
      const b = evidenceBar(ev, { side: ev.side, baseLabel: base });
      c.querySelector("#cbar").appendChild(b.node);
      c.classList.add("in");
      b.play(150);
      countUp(c.querySelector("#cbig"), Math.round(ev.rate * 100), { ms: 800 });
      c.querySelector(".x").addEventListener("click", () => select(null));
      c.querySelector("#cgo")?.addEventListener("click", (e) => { e.preventDefault(); goTab(target); });
    }, 160);
  }

  // ---- controls from the frame ----
  ui.onMap((name) => {
    st.map = name;
    setParams({ map: name || null });
    renderCats(); renderList();
    if (st.sel != null && name && items[st.sel]?.ev.map !== name) select(null);
    showMap(name || items[st.sel ?? -1]?.ev.map || rep.record.most_played).then(drawLayers);
  });
  ui.onSide((side) => { st.side = side; setParams({ side: side === "both" ? null : side }); renderCats(); renderList(); drawLayers(); });
  ui.zoom((f) => map?.focus(st.sel != null && items[st.sel] ? findingAt(map.geo, items[st.sel].ev) || null : null, f, 500));

  const onKey = (e) => {
    if (e.target.closest?.("input, textarea") || !document.getElementById("palette").hidden) return;
    const vis = visible().map((x) => x.i);
    if (!vis.length) return;
    const pos = vis.indexOf(st.sel);
    if (e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); select(vis[Math.min(pos + 1, vis.length - 1)], { fromKey: true }); }
    else if (e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); select(vis[Math.max(pos - 1, 0)], { fromKey: true }); }
    else if (e.key === "Escape") select(null);
  };
  addEventListener("keydown", onKey);
  disposers.push(() => removeEventListener("keydown", onKey));

  renderCats();
  renderList();
  const start = st.sel != null && items[st.sel] ? items[st.sel].ev.map : st.map || rep.record.most_played;
  showMap(start).then(() => { drawLayers(); if (st.sel != null && items[st.sel]) select(st.sel); });
  return () => disposers.forEach((d) => d());
}
