// Overview: the first thing a coach sees. A hero dossier, then the three findings that matter most told one at a
// time over a pinned map, then the rest of the game plan, then the way into the dashboard.
import { api } from "./api.js";
import { evidenceBar } from "./evidence.js";
import { COLORS, drawMap, findingAt } from "./map.js";
import { countUp, onEnter, reduced, reveals, splitIn } from "./motion.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const title = (s) => String(s || "").replace(/\b\w/g, (c) => c.toUpperCase());
const pct = (v) => `${Math.round(v * 100)}%`;
const sideWord = (s) => (s === "attacker" ? "Attack" : "Defense");
const sideCls = (s) => (s === "attacker" ? "atk" : "def");

/** "Cloud9 (VCT 2025)" -> ["Cloud9", "VCT 2025"] so the hero can set the name big and the era small. */
function splitName(name) {
  const m = /^(.*?)\s*\(([^)]+)\)$/.exec(name);
  return m ? [m[1], m[2]] : [name, null];
}

/** The detail sentence without the sample it repeats ("56 of 79 rounds on Vyse (…: 38%). Have a…" -> "Have a…"). */
function tipOnly(detail, ev) {
  const plain = detail.replace(/<[^>]+>/g, "");
  if (plain.startsWith(ev.sample)) {
    const i = detail.indexOf(". ");
    return i >= 0 ? detail.slice(i + 2) : "";
  }
  return detail;
}

/** Label next to the pulse on the map for one finding. */
function pinLabel(ev) {
  const t = ev.tags || {};
  if (ev.category === "Utility") return `${t.player} · ${title(String(t.ability || "").replace(/-/g, " "))}`;
  if (ev.category === "Operator") return `${t.label || "Operator"}${t.player ? ` · ${t.player}` : ""}`;
  if (ev.category === "Attack") return `Plants ${String(t.site || "").replace(" site", "")}`;
  return "";
}

export async function renderOverview(app, { meta, team, report: rep, go, setTeam }) {
  const disposers = [];
  if (rep.empty) {
    app.innerHTML = `<section class="soon"><div><div class="kicker">No games</div><h2>${esc(rep.name)}</h2>
      <p>No games match these filters.</p></div></section>`;
    return () => {};
  }
  const r = rep.record;
  const [name, era] = splitName(rep.name);
  const self = rep.self_scout;
  const top3 = rep.plan.slice(0, 3), rest = rep.plan.slice(3);
  const picks = meta.quick_picks.map((p) => `<button type="button" data-team="${p.id}" class="${p.id === team ? "on" : ""}">${esc(p.label)}</button>`).join("");
  const longName = name.length > 9;

  app.innerHTML = `
  <section class="hero" data-chapter="overview">
    <svg class="bgmap" id="heroMap" aria-hidden="true"></svg>
    <div class="picks"><span>QUICK PICKS</span>${picks}</div>
    <div class="kicker">${self ? "Self-scout" : "Opponent dossier"}${era ? ` · ${esc(era)}` : ""}${rep.peers !== era ? ` · compared with ${esc(rep.peers)}` : ""} · ${r.games} maps</div>
    <h1 id="teamName" style="${longName ? `font-size:clamp(64px, ${Math.max(6, 15 - (name.length - 9) * .8)}vw, 200px)` : ""}">${esc(name)}</h1>
    <p class="sub">${self
      ? `What opponents can read from ${esc(name)}'s matches, and the evidence behind each habit.`
      : `How ${esc(name)} plays, what to plan for, and the evidence behind each call.`}</p>
    <div class="stats" id="stats"></div>
    ${rep.roster.length ? `<div class="roster" id="roster"><em>ROSTER</em>${rep.roster.map((p) => `<span>${esc(p)}</span>`).join("")}</div>` : ""}
    <p class="notes">${rep.notes.map(esc).join(" ")}</p>
    <div class="cue" aria-hidden="true"><i></i>SCROLL</div>
  </section>

  ${top3.length ? `
  <section data-chapter="findings">
    <div class="chead reveal"><div class="num">01 · ${self ? "PREDICTABILITY CHECK" : "GAME PLAN"}</div>
      <h2>${self ? (top3.length === 3 ? "Three habits opponents can read" : "What opponents can read")
                 : (top3.length === 3 ? "Three things to plan around" : "What to plan around")}</h2>
      <p>${self
        ? `Each one is something ${esc(name)} does far more or less often than the typical ${esc(rep.peers)} team or player, with enough rounds behind it to be sure.`
        : `The tendencies that set ${esc(name)} apart from the typical ${esc(rep.peers)} team, with the rounds behind each one.`}</p></div>
    <div class="story">
      <div class="stage"><div class="cap" id="stageCap"></div><svg id="stage"></svg></div>
      <div class="steps" id="steps"></div>
    </div>
  </section>` : `
  <section class="soon"><div><div class="kicker">Nothing stands out</div><h2>No strong tendencies</h2>
    <p>Nothing ${esc(name)} does differs from the typical ${esc(rep.peers)} team by enough to plan around.</p></div></section>`}

  ${rest.length ? `
  <section data-chapter="rest">
    <div class="chead reveal" style="padding-top:12vh"><div class="num">02 · ${self ? "ALSO WORTH VARYING" : "ALSO PREPARE FOR"}</div>
      <h2>${rest.length === 1 ? "One more" : `${["", "", "Two", "Three", "Four", "Five"][rest.length] || rest.length} more`}</h2></div>
    <div class="rest" id="rest"></div>
  </section>` : ""}

  <section class="cta" data-chapter="next">
    <div class="reveal"><div class="kicker">The full picture</div>
      <h2>All ${rep.insights.length} tendencies,<br>on the map</h2>
      <p>The dashboard has every tendency, the Operator and utility evidence round by round with a timeline you can scrub, and the map pool.</p></div>
    <a class="btn reveal" href="?view=dashboard&team=${encodeURIComponent(team)}" data-go="dashboard">Open the dashboard <span aria-hidden="true">→</span></a>
  </section>
  <p class="foot">${esc(rep.rule)} Data: GRID official match data · ${meta.summary.series} series · ${meta.summary.maps.toLocaleString()} maps ·
    ${meta.summary.rounds.toLocaleString()} rounds · ${meta.summary.first} to ${meta.summary.last}.</p>`;

  // ---- hero ----
  splitIn(app.querySelector("#teamName"), { stagger: Math.max(25, 60 - name.length * 2) });
  const stats = [
    ["Maps won", r.wins, (v) => `${Math.round(v)}–${r.games - Math.round(v)}`, `${r.wins} of ${r.games} maps`, COLORS.ink],
    ["Attack rounds won", r.atk_won / r.atk_n * 100, (v) => `${Math.round(v)}%`, `${r.atk_won} of ${r.atk_n} rounds`, COLORS.atk],
    ["Defense rounds won", r.def_won / r.def_n * 100, (v) => `${Math.round(v)}%`, `${r.def_won} of ${r.def_n} rounds`, COLORS.def],
    ["Most played", null, null, `${r.most_played_games} of ${r.games} maps`, COLORS.ink],
  ];
  const statsEl = app.querySelector("#stats");
  stats.forEach(([label, v, fmt, sub, color], i) => {
    const d = document.createElement("div");
    d.className = "stat";
    d.innerHTML = `<div class="v" style="color:${color}">${v == null ? esc(title(r.most_played)) : ""}</div>
      <div class="l">${label}</div><div class="s">${sub}</div>`;
    statsEl.appendChild(d);
    if (!reduced) d.animate([{ opacity: 0, transform: "translateY(18px)" }, { opacity: 1, transform: "none" }],
      { duration: 700, delay: 800 + i * 110, fill: "both", easing: "ease-out" });
    if (v != null) countUp(d.querySelector(".v"), v, { fmt, delay: 800 + i * 110, ms: 1400 });
  });
  app.querySelectorAll("#roster span").forEach((s, i) => !reduced && s.animate([{ opacity: 0, transform: "translateX(-8px)" },
    { opacity: 1, transform: "none" }], { duration: 500, delay: 1300 + i * 70, fill: "both" }));
  api.map(r.most_played).then((geo) => {
    const m = drawMap(app.querySelector("#heroMap"), geo, { floor: "#0c1621", wallPx: 1.3, spawns: false, sites: false });
    m.drawIn(3000, 150);
  }).catch(() => {});
  app.querySelectorAll(".picks button").forEach((b) => b.addEventListener("click", () => setTeam(b.dataset.team)));

  // ---- findings: pinned map + steps ----
  if (top3.length) {
    const stepsEl = app.querySelector("#steps");
    const stage = { svg: app.querySelector("#stage"), map: null, mapName: null, cur: -1, token: 0 };
    top3.forEach((p, i) => {
      const ev = p.evidence, cls = sideCls(ev.side);
      const s = document.createElement("article");
      s.className = "step";
      s.dataset.i = i;
      const baseLabel = ev.category === "Utility" ? "typical player" : "typical team";
      s.innerHTML = `
        <div class="n">0${i + 1} <span class="chip ${cls}">${sideWord(ev.side)}</span> ${esc(title(ev.map))}</div>
        <div class="big ${cls}"><span class="pct">${Math.round(ev.rate * 100)}</span>%</div>
        <div class="of"><b>${ev.k}</b> of <b>${ev.n}</b> ${esc(ev.unit)}</div>
        ${ev.base != null ? `<div class="peer">${esc(ev.peers)}: ${pct(ev.base)}</div>` : ""}
        <div class="cat">${esc(ev.label)}</div>
        <h3>${p.headline}</h3>
        <p>${tipOnly(p.detail, ev)}</p>
        <div class="evwrap"></div>
        <div class="range">95% range ${pct(ev.lo)}–${pct(ev.hi)}${ev.base != null ? `, clear of the ${baseLabel} (${pct(ev.base)})` : ""}</div>
        ${ev.departed ? `<div class="departed">${esc(ev.departed)}</div>` : ""}`;
      const bar = evidenceBar(ev, { side: ev.side, baseLabel: baseLabel.replace("typical ", "typical ") });
      s.querySelector(".evwrap").appendChild(bar.node);
      s._bar = bar;
      stepsEl.appendChild(s);
    });

    async function show(i) {
      if (stage.cur === i) return;
      stage.cur = i;
      const token = ++stage.token;
      const p = top3[i], ev = p.evidence, color = ev.side === "attacker" ? COLORS.atk : COLORS.def;
      stepsEl.querySelectorAll(".step").forEach((s) => s.classList.toggle("on", +s.dataset.i === i));
      const step = stepsEl.children[i];
      if (!step._played) {
        step._played = true;
        step._bar.play(300);
        countUp(step.querySelector(".pct"), Math.round(ev.rate * 100), { ms: 1200, delay: 150 });
      }
      app.querySelector("#stageCap").innerHTML = `<span class="chip ${sideCls(ev.side)}">${sideWord(ev.side)}</span>${esc(title(ev.map))} · ${esc(ev.label)}`;
      const geo = await api.map(ev.map);
      if (token !== stage.token) return; // the reader scrolled on while the map loaded
      const fresh = stage.mapName !== ev.map;
      if (fresh) {
        if (stage.map && !reduced) await stage.svg.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 250, fill: "forwards" }).finished;
        if (token !== stage.token) return;
        stage.map = drawMap(stage.svg, geo);
        stage.mapName = ev.map;
        stage.svg.getAnimations().forEach((a) => a.cancel());
        stage.map.drawIn(1200);
      } else {
        stage.map.layers.top.innerHTML = "";
        stage.map.focus(null, 1, 600);
      }
      const at = findingAt(geo, ev);
      setTimeout(() => {
        if (token !== stage.token) return;
        if (ev.category === "Attack" && ev.tags?.site) stage.map.highlightSite(ev.tags.site);
        if (at) {
          stage.map.focus(at, ev.category === "Attack" ? 1.25 : 1.5, 1300);
          stage.map.pulse(at, color, pinLabel(ev));
        }
      }, fresh ? 950 : 250);
    }
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && show(+e.target.dataset.i)),
      { rootMargin: "-45% 0px -45% 0px" });
    [...stepsEl.children].forEach((s) => io.observe(s));
    disposers.push(() => io.disconnect());
    // Draw the first map before the reader reaches it, so the stage is never empty.
    disposers.push(onEnter(app.querySelector(".story"), () => { if (stage.cur < 0) show(0); }, { threshold: 0.01 }));
  }

  // ---- the rest of the plan ----
  const restEl = app.querySelector("#rest");
  rest.forEach((p, j) => {
    const ev = p.evidence;
    const row = document.createElement("a");
    row.className = "row reveal";
    row.href = `?view=dashboard&team=${encodeURIComponent(team)}`;
    row.dataset.go = "dashboard";
    row.innerHTML = `<div class="i">0${j + 4}</div>
      <div><div class="h">${p.headline}</div><div class="d">${esc(ev.label)} · ${esc(title(ev.map))}</div></div>
      <div class="eb"></div>
      <div class="m"><span class="chip ${sideCls(ev.side)}">${sideWord(ev.side)}</span>${ev.k}/${ev.n}</div>`;
    const b = evidenceBar(ev, { side: ev.side, labels: false });
    row.querySelector(".eb").appendChild(b.node);
    restEl.appendChild(row);
    disposers.push(onEnter(row, () => b.play(150), { threshold: 0.6 }));
  });

  app.querySelectorAll("[data-go]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); go(a.dataset.go); }));
  disposers.push(reveals(app));
  return () => disposers.forEach((d) => d());
}
