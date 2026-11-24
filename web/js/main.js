// App shell: URL state (?team=…&view=…), the team palette, view switching and loading/setup screens.
import { api, ApiError } from "./api.js";
import { esc, renderOverview } from "./overview.js";
import { scrollToTop, smoothScroll } from "./motion.js";
import { setupPalette } from "./palette.js";

const app = document.getElementById("app");
const VIEWS = ["overview", "dashboard", "method"];
let meta = null, dispose = () => {}, renderToken = 0;

function state() {
  const q = new URLSearchParams(location.search);
  const team = q.get("team") || meta?.quick_picks?.[0]?.id || "79";
  const view = VIEWS.includes(q.get("view")) ? q.get("view") : "overview";
  return { team, view };
}

function navigate(next, { replace = false } = {}) {
  const s = { ...state(), ...next };
  const q = new URLSearchParams();
  q.set("team", s.team);
  if (s.view !== "overview") q.set("view", s.view);
  history[replace ? "replaceState" : "pushState"](null, "", `?${q}`);
  render();
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("on");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("on"), 2600);
}

const LOADING = (label) => `<div class="loading"><div><img class="ret" src="img/opscope-icon.svg" alt="">${esc(label)}</div></div>`;

function showSetup(body) {
  app.innerHTML = `<section class="setup"><div class="kicker">Setup needed</div><h1>OpScope needs the match data</h1>
    <p>It reads the licensed GRID data from a local cache, which hasn't been built on this machine yet.</p>
    <ol>${(body?.setup || []).map((s) => `<li>${esc(s).replace(/(uv run [^\s]+(?: [^\s]+)*|git clone .*$)/, "<code>$1</code>")}</li>`).join("")}</ol></section>`;
  document.getElementById("switchTeam").textContent = "No data yet";
}

async function render() {
  const token = ++renderToken;
  const { team, view } = state();
  dispose();
  dispose = () => {};
  document.querySelectorAll("#views a").forEach((a) => a.classList.toggle("on", a.dataset.view === view));
  const label = meta.teams.find((t) => t.id === team)?.name || team;
  document.getElementById("switchTeam").textContent = label;
  document.title = `${label} · OpScope`;
  scrollToTop();

  if (view !== "overview") {
    app.innerHTML = `<section class="soon"><div><div class="kicker">Next build step</div>
      <h2>${view === "dashboard" ? "The dashboard" : "How it works"}</h2>
      <p>${view === "dashboard" ? "Every tendency on the map, with the round-by-round timeline. Coming in the next step."
        : "The method and its limits. Coming in a later step."}</p>
      <p style="margin-top:22px"><a class="btn" href="?team=${encodeURIComponent(team)}" id="back">Back to the overview</a></p></div></section>`;
    app.querySelector("#back").addEventListener("click", (e) => { e.preventDefault(); navigate({ view: "overview" }); });
    return;
  }

  app.innerHTML = LOADING(`Building the scouting report for ${label}…`);
  try {
    const rep = await api.report(team);
    if (token !== renderToken) return;
    app.innerHTML = "";
    dispose = await renderOverview(app, { meta, team, report: rep, go: (v) => navigate({ view: v }), setTeam });
  } catch (e) {
    if (token !== renderToken) return;
    if (e instanceof ApiError && e.status === 503) return showSetup(e.body);
    app.innerHTML = `<section class="soon"><div><div class="kicker">Something went wrong</div><h2>Couldn't load ${esc(label)}</h2>
      <p>${esc(e.message)}</p></div></section>`;
  }
}

function setTeam(id) {
  if (id === state().team) return toast(`Already scouting ${meta.teams.find((t) => t.id === id)?.name || id}`);
  navigate({ team: id });
}

function trackScroll() {
  const bar = document.getElementById("progress");
  const onScroll = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    bar.style.width = max > 0 ? `${(scrollY / max) * 100}%` : "0";
  };
  addEventListener("scroll", onScroll, { passive: true });
}

/** Warm the server's cache for the quick picks, one at a time, so switching between them is instant. */
async function prefetch() {
  for (const p of meta.quick_picks) {
    if (p.id === state().team) continue;
    await api.report(p.id).catch(() => {});
  }
}

async function boot() {
  app.innerHTML = LOADING("Loading OpScope…");
  try {
    meta = await api.meta();
  } catch (e) {
    if (e instanceof ApiError && e.status === 503) return showSetup(e.body);
    app.innerHTML = `<section class="soon"><div><h2>Can't reach the OpScope server</h2><p>Start it with <code>uv run opscope</code>.</p></div></section>`;
    return;
  }
  smoothScroll();
  trackScroll();
  setupPalette({ teams: meta.teams, onPick: setTeam });
  document.querySelectorAll("#views a").forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    navigate({ view: a.dataset.view });
  }));
  addEventListener("popstate", render);
  await render();
  (window.requestIdleCallback || setTimeout)(prefetch);
}

boot();
