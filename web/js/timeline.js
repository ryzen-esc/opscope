// The round clock: play, pause, scrub or step through a round second by second. Each tab decides what a given
// time means (which dots show, which kill lines draw); the timeline only owns the clock.
//
// opts: { min, max, segments: [{from, to, label, color}], ticks: [t…], start, onTime(t, mode), modes: true }
import { reduced } from "./motion.js";

const fmt = (t) => {
  const s = Math.round(t);
  const neg = s < 0;
  const a = Math.abs(s);
  return `${neg ? "−" : ""}${Math.floor(a / 60)}:${String(a % 60).padStart(2, "0")}`;
};

export function createTimeline(host, opts) {
  const o = { min: 0, max: 100, segments: [], ticks: [], start: null, modes: true, ...opts };
  let t = o.start ?? o.max, playing = false, speed = 1, mode = "build", last = 0, raf = 0, dragging = false;
  host.classList.add("tl");
  host.innerHTML = `
    <button class="tl-play" type="button" aria-label="Play">${icon(false)}</button>
    <div class="tl-clock"><span class="tl-t">0:00</span><small>round clock</small></div>
    <div class="tl-track" role="slider" tabindex="0" aria-label="Time in round" aria-valuemin="${o.min}" aria-valuemax="${o.max}">
      <div class="tl-segs"></div><div class="tl-ticks"></div><div class="tl-fill"></div><div class="tl-head"><span></span></div>
    </div>
    <div class="tl-side">
      <div class="tl-speeds" role="group" aria-label="Speed">${[1, 2, 4].map((s) => `<button type="button" data-s="${s}" class="${s === 1 ? "on" : ""}">${s}×</button>`).join("")}</div>
      ${o.modes ? `<div class="tl-modes" role="group" aria-label="What to show">
        <button type="button" data-m="build" class="on" title="Everything up to the playhead">Build up</button>
        <button type="button" data-m="moment" title="Only the last 5 seconds, fading">Moment</button></div>` : ""}
    </div>`;
  const $ = (s) => host.querySelector(s);
  const track = $(".tl-track"), head = $(".tl-head"), fill = $(".tl-fill"), clock = $(".tl-t"), playBtn = $(".tl-play");
  const span = o.max - o.min, pos = (v) => ((v - o.min) / span) * 100;

  $(".tl-segs").innerHTML = o.segments.map((s) => `<div class="tl-seg" style="left:${pos(s.from)}%;width:${pos(s.to) - pos(s.from)}%;--c:${s.color}">
    <span>${s.label}</span></div>`).join("");
  function setTicks(ticks) {
    $(".tl-ticks").innerHTML = ticks.filter((v) => v >= o.min && v <= o.max).map((v) => `<i style="left:${pos(v)}%"></i>`).join("");
  }
  setTicks(o.ticks);

  function icon(p) {
    return p ? `<svg width="12" height="14" viewBox="0 0 12 14"><path d="M0 0H4V14H0ZM8 0H12V14H8Z" fill="currentColor"/></svg>`
      : `<svg width="12" height="14" viewBox="0 0 12 14"><path d="M0 0L12 7L0 14Z" fill="currentColor"/></svg>`;
  }
  function set(v, { silent = false } = {}) {
    t = Math.max(o.min, Math.min(o.max, v));
    head.style.left = fill.style.width = `${pos(t)}%`;
    clock.textContent = fmt(t);
    track.setAttribute("aria-valuenow", Math.round(t));
    track.setAttribute("aria-valuetext", fmt(t));
    host.querySelectorAll(".tl-seg").forEach((el, i) => el.classList.toggle("on", t >= o.segments[i].from));
    if (!silent) o.onTime?.(t, mode);
  }
  function setPlaying(p) {
    playing = p;
    playBtn.innerHTML = icon(p);
    playBtn.setAttribute("aria-label", p ? "Pause" : "Play");
    if (p) { if (t >= o.max) set(o.min); last = performance.now(); raf = requestAnimationFrame(loop); }
    else cancelAnimationFrame(raf);
  }
  function loop(now) {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    set(t + dt * 8 * speed); // 1× plays a 100 s round in ~12 s
    if (t >= o.max) return setPlaying(false);
    raf = requestAnimationFrame(loop);
  }
  const seek = (e) => {
    const r = track.getBoundingClientRect();
    set(o.min + ((e.clientX - r.left) / r.width) * span);
  };
  track.addEventListener("pointerdown", (e) => { dragging = true; setPlaying(false); track.setPointerCapture(e.pointerId); seek(e); });
  track.addEventListener("pointermove", (e) => dragging && seek(e));
  track.addEventListener("pointerup", () => (dragging = false));
  track.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { e.preventDefault(); setPlaying(false); set(Math.floor(t) + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); setPlaying(false); set(Math.ceil(t) - 1); }
  });
  playBtn.addEventListener("click", () => setPlaying(!playing));
  host.querySelectorAll(".tl-speeds button").forEach((b) => b.addEventListener("click", () => {
    speed = +b.dataset.s;
    host.querySelectorAll(".tl-speeds button").forEach((x) => x.classList.toggle("on", x === b));
  }));
  host.querySelectorAll(".tl-modes button").forEach((b) => b.addEventListener("click", () => {
    mode = b.dataset.m;
    host.querySelectorAll(".tl-modes button").forEach((x) => x.classList.toggle("on", x === b));
    set(t);
  }));

  // Global keys: space plays, ← → step a second (when nothing else has focus).
  const onKey = (e) => {
    if (e.target.closest?.("input, textarea, button, [role=slider]") || !document.getElementById("palette").hidden) return;
    if (e.key === " ") { e.preventDefault(); setPlaying(!playing); }
    else if (e.key === "ArrowRight") { e.preventDefault(); setPlaying(false); set(Math.floor(t) + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); setPlaying(false); set(Math.ceil(t) - 1); }
  };
  addEventListener("keydown", onKey);

  set(t);
  return {
    set, setTicks, play: () => !reduced && setPlaying(true), pause: () => setPlaying(false),
    get time() { return t; }, get mode() { return mode; },
    destroy() { setPlaying(false); removeEventListener("keydown", onKey); host.classList.remove("tl"); host.innerHTML = ""; },
  };
}

export { fmt as clockLabel };
