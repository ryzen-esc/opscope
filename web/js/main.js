// App shell: URL state (?team=…&view=…), the team palette, view switching and loading/setup screens.
import { api, ApiError } from "./api.js";
import { renderDashboard } from "./dashboard.js";
import { esc, renderOverview } from "./overview.js";
import { scrollToTop, smoothScroll } from "./motion.js";
import { setupPalette } from "./palette.js";

const app = document.getElementById("app");
const VIEWS = ["overview", "dashboard", "method"];
let meta = null, dispose = () => {}, renderToken = 0;

const FILTERS = ["opponents", "patches", "events"];

function state() {
  const q = new URLSearchParams(location.search);
  const team = q.get("team") || meta?.quick_picks?.[0]?.id || "79";
  const view = VIEWS.includes(q.get("view")) ? q.get("view") : "overview";
  const filters = Object.fromEntries(FILTERS.map((k) => [k, q.getAll(k)]));
  return { team, view, filters };
}

/** Change team, view or filters: a new history entry and a full render. Tab-level state is dropped, unless
 * `keepTab` (a filter change on the dashboard): then tab, map, side and the tab's own settings stay, all but `sel`,
 * whose finding indices change with the filters. */
function navigate(next, { replace = false, keepTab = false } = {}) {
  const cur = state();
  const team = next.team ?? cur.team, view = next.view ?? cur.view;
  const q = new URLSearchParams();
  q.set("team", team);
  if (view !== "overview") q.set("view", view);
  const keepFilters = !next.team || next.team === cur.team;
  for (const k of FILTERS) for (const v of (next[k] ?? (keepFilters ? cur.filters[k] : []))) q.append(k, v);
  if (keepTab) {
    for (const [k, v] of new URLSearchParams(location.search)) if (!["team", "view", "sel", ...FILTERS].includes(k)) q.append(k, v);
  }
  for (const k of ["tab", "sel", "map", "side"]) if (next[k] != null) q.set(k, next[k]);
  history[replace ? "replaceState" : "pushState"](null, "", `?${q}`);
  render();
}

/** Tab-level state (tab, map, side, selection…): rewrite the URL in place, no render. Arrays repeat the key. */
function setParams(patch) {
  const q = new URLSearchParams(location.search);
  for (const [k, v] of Object.entries(patch)) {
    q.delete(k);
    if (v == null || v === "") continue;
    for (const item of Array.isArray(v) ? v : [v]) if (item != null && item !== "") q.append(k, item);
  }
  history.replaceState(null, "", `?${q}`);
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
  const { team, view, filters } = state();
  dispose();
  dispose = () => {};
  document.querySelectorAll("#views a").forEach((a) => a.classList.toggle("on", a.dataset.view === view));
  const label = meta.teams.find((t) => t.id === team)?.name || team;
  document.getElementById("switchTeam").textContent = label;
  document.title = `${label} · OpScope`;
  scrollToTop();

  if (view === "method") {
    app.innerHTML = `<section class="soon"><div><div class="kicker">Later build step</div><h2>How it works</h2>
      <p>The method and its limits.</p>
      <p style="margin-top:22px"><a class="btn" href="?team=${encodeURIComponent(team)}" id="back">Back to the overview</a></p></div></section>`;
    app.querySelector("#back").addEventListener("click", (e) => { e.preventDefault(); navigate({ view: "overview" }); });
    return;
  }

  app.innerHTML = LOADING(`Building the scouting report for ${label}…`);
  try {
    const rep = await api.report(team, filters);
    if (token !== renderToken) return;
    const isCurrent = () => token === renderToken;
    let d;
    if (view === "dashboard") {
      d = await renderDashboard(app, { meta, team, filters, params: new URLSearchParams(location.search), setParams, navigate, isCurrent });
    } else {
      app.innerHTML = "";
      d = await renderOverview(app, { meta, team, report: rep, go: (v, extra = {}) => navigate({ view: v, ...extra }), setTeam });
    }
    // A newer render started while this one was awaiting: undo whatever this one set up, keep the newer one's dispose.
    if (!isCurrent()) return d();
    dispose = d;
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
