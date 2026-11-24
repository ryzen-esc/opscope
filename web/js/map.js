// Map renderer. Geometry comes from /api/map/{name} already in the view frame (0..1000 units, attackers at the
// bottom), so every layer (dots, kills, habit spots) is drawn in the same units with no further transform.
import { easeInOut, reduced } from "./motion.js";

const NS = "http://www.w3.org/2000/svg";
export const COLORS = { def: "#00aeef", atk: "#f2545b", amb: "#f5b43c", grn: "#4fd18b", ink: "#eef3f7", bg: "#06080b" };

export function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

const ringPath = (r) => "M" + r.map((p) => `${p[0]} ${p[1]}`).join("L") + "Z";
const sideOf = (s) => (s === "attacker" ? "atk" : "def");

/**
 * Draw a map into `svg`. opts: {floor, wall, wallPx, glow, spawns, sites, siteAreas, props, pad}.
 * Returns an object with the layers plus drawIn(ms, delay), focus(at, zoom, ms), zoomBy(factor), pulse(...),
 * highlightSite(name).
 */
export function drawMap(svg, geo, opts = {}) {
  const o = { floor: "#101b27", wall: "#5fb4e6", wallPx: 1.5, glow: true, spawns: true, sites: true, siteAreas: true,
    props: true, pad: 0.06, ...opts };
  svg.innerHTML = "";
  const [x0, y0, x1, y1] = geo.bbox;
  const pad = Math.max(x1 - x0, y1 - y0) * o.pad;
  const base = [x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad];
  svg.setAttribute("viewBox", base.join(" "));
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${geo.map} minimap`);

  const root = el("g", {}, svg);
  const floor = el("path", { d: geo.rings.map(ringPath).join(" "), fill: o.floor, "fill-rule": "evenodd" }, root);
  const detail = el("g", {}, root);
  const areas = {};
  if (o.siteAreas) for (const a of geo.site_areas || []) {
    const p = el("path", { d: ringPath(a.ring), fill: "rgba(245,180,60,.09)", "data-site": a.name }, detail);
    (areas[a.name] ||= []).push(p);
  }
  if (o.props && geo.props?.length) el("path", { d: geo.props.map(ringPath).join(" "), fill: "rgba(255,255,255,.04)",
    stroke: o.wall, "stroke-opacity": .3, "stroke-width": .7, "vector-effect": "non-scaling-stroke" }, detail);
  const walls = el("g", { fill: "none", stroke: o.wall, "stroke-linejoin": "round" }, root);
  if (o.glow) walls.style.filter = `drop-shadow(0 0 4px ${o.wall})`;
  const wallPaths = geo.rings.map((r) => el("path", { d: ringPath(r), pathLength: 1, "stroke-width": o.wallPx,
    "vector-effect": "non-scaling-stroke" }, walls));
  const layers = { under: el("g", {}, root), sites: el("g", {}, root), data: el("g", {}, root), top: el("g", {}, root) };

  if (o.sites) for (const s of geo.sites || []) {
    const t = el("text", { x: s.at[0], y: s.at[1], fill: COLORS.amb, "font-size": 34, "font-family": "Big Shoulders Display, sans-serif",
      "font-weight": 800, "text-anchor": "middle", "dominant-baseline": "central", opacity: .85 }, layers.sites);
    t.textContent = s.name[0];
  }
  if (o.spawns) for (const [side, at] of Object.entries(geo.spawns || {})) {
    const c = side === "attacker" ? COLORS.atk : COLORS.def, r = 17;
    const g = el("g", {}, layers.sites);
    el("rect", { x: at[0] - r, y: at[1] - r, width: 2 * r, height: 2 * r, fill: COLORS.bg, stroke: c, "stroke-width": 1.4,
      "vector-effect": "non-scaling-stroke" }, g);
    const t = el("text", { x: at[0], y: at[1], fill: c, "font-size": 12, "font-family": "JetBrains Mono, monospace",
      "font-weight": 600, "text-anchor": "middle", "dominant-baseline": "central" }, g);
    t.textContent = side === "attacker" ? "ATK" : "DEF";
  }

  function drawIn(ms = 1500, delay = 0) {
    if (reduced) return;
    const a = (n, kf, d, dl) => n.animate(kf, { duration: d, delay: delay + dl, fill: "both", easing: "cubic-bezier(.6,.05,.2,1)" });
    a(floor, [{ opacity: 0 }, { opacity: 1 }], ms * .8, ms * .25);
    a(detail, [{ opacity: 0 }, { opacity: 1 }], ms * .6, ms * .55);
    wallPaths.forEach((p, i) => {
      p.style.strokeDasharray = "1 1";
      a(p, [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], ms, i * ms * .03);
    });
    a(layers.sites, [{ opacity: 0 }, { opacity: 1 }], 500, ms * .7);
  }

  let now = base.slice(), raf = 0;
  // Where the camera is aimed (the last target, not an in-between frame), so the zoom buttons carry on from it.
  // `at` stays when zooming back out to 1, so "+" returns to the same spot; a fresh drawMap starts at 1.
  let cam = { at: null, zoom: 1, shift: 0 };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  /** The viewBox that centres `at` at `zoom`, kept inside the map. */
  function frame(at, zoom, shift) {
    if (!at || zoom <= 1) return base.slice();
    // Centre on the spot (moved left by `shift` of the view, to clear a panel on the right), but keep the camera
    // inside the map so an edge spot never shows empty space.
    const w = base[2] / zoom, h = base[3] / zoom;
    const cx = at[0] + shift * w;
    return [clamp(cx - w / 2, base[0], base[0] + base[2] - w), clamp(at[1] - h / 2, base[1], base[1] + base[3] - h), w, h];
  }

  function fly(target, ms) {
    cancelAnimationFrame(raf);
    if (reduced || ms <= 0) { now = target; svg.setAttribute("viewBox", now.join(" ")); return; }
    const from = now.slice(), t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / ms), e = easeInOut(k);
      now = from.map((v, i) => v + (target[i] - v) * e);
      svg.setAttribute("viewBox", now.join(" "));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }

  /** Animate the camera to centre `at` at `zoom` (1 = whole map); null resets. */
  function focus(at, zoom = 1, ms = 1200, { shift = 0 } = {}) {
    cam = at && zoom > 1 ? { at, zoom, shift } : { at: null, zoom: 1, shift: 0 };
    fly(frame(cam.at, cam.zoom, cam.shift), ms);
  }

  /** Zoom by `factor` from the current camera, about the spot it is aimed at (else the map centre), within 1x to 4x. */
  function zoomBy(factor, ms = 400) {
    let zoom = clamp(cam.zoom * factor, 1, 4);
    if (zoom < 1.01) zoom = 1; // 1.4 x 1/1.4 is not exactly 1
    if (zoom === cam.zoom) return;
    cam = { ...cam, zoom, at: cam.at || [base[0] + base[2] / 2, base[1] + base[3] / 2] };
    fly(frame(cam.at, cam.zoom, cam.shift), ms);
  }

  /** A pulsing ring at `at` with an optional label. */
  function pulse(at, color, label, { r = 26, layer = layers.top } = {}) {
    const g = el("g", { class: "pulse" }, layer);
    const ring = el("circle", { cx: at[0], cy: at[1], r, fill: "none", stroke: color, "stroke-width": 2, "vector-effect": "non-scaling-stroke" }, g);
    const wave = el("circle", { cx: at[0], cy: at[1], r, fill: "none", stroke: color, "stroke-width": 1.5, "vector-effect": "non-scaling-stroke" }, g);
    el("circle", { cx: at[0], cy: at[1], r: r * .22, fill: color }, g);
    if (!reduced) {
      ring.animate([{ r: 0, opacity: 0 }, { r: r * 1.15, opacity: 1, offset: .7 }, { r, opacity: 1 }], { duration: 900, fill: "both", easing: "ease-out" });
      wave.animate([{ r, opacity: .9 }, { r: r * 3.2, opacity: 0 }], { duration: 2200, iterations: Infinity, delay: 700 });
    }
    if (label) {
      const t = el("text", { x: at[0] + r * 1.5, y: at[1] - r * 1.25, fill: COLORS.ink, "font-size": 17,
        "font-family": "Inter, sans-serif", "font-weight": 600, stroke: COLORS.bg, "stroke-width": 4, "paint-order": "stroke" }, g);
      t.textContent = label;
      el("line", { x1: at[0] + r * .75, y1: at[1] - r * .75, x2: at[0] + r * 1.35, y2: at[1] - r * 1.15, stroke: COLORS.ink,
        "stroke-width": 1, "vector-effect": "non-scaling-stroke" }, g);
      if (!reduced) t.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 600, fill: "both" });
    }
    return g;
  }

  /** Brighten one plant-site zone (e.g. "A site") and dim any lit before; null only dims. */
  function highlightSite(name, color = COLORS.amb) {
    for (const p of Object.values(areas).flat()) {
      p.getAnimations().forEach((a) => a.cancel());
      p.setAttribute("fill", "rgba(245,180,60,.09)");
      p.removeAttribute("fill-opacity");
    }
    if (name == null) return;
    for (const p of areas[name] || []) {
      p.setAttribute("fill", color);
      p.setAttribute("fill-opacity", ".28");
      if (!reduced) p.animate([{ fillOpacity: .05 }, { fillOpacity: .34 }, { fillOpacity: .22 }], { duration: 1400, fill: "forwards" });
    }
  }

  return { svg, geo, layers, floor, detail, walls, wallPaths, drawIn, focus, zoomBy, pulse, highlightSite, base };
}

/** Where a finding sits on the map: its own spot, else the named area (callout or site), else null. */
export function findingAt(geo, ev) {
  if (ev.at) return ev.at;
  const name = (ev.tags?.area || ev.tags?.site || "").toLowerCase();
  if (!name) return null;
  const site = (geo.sites || []).find((s) => s.name.toLowerCase() === name);
  if (site) return site.at;
  const c = (geo.callouts || []).find((s) => s.name.toLowerCase() === name);
  return c ? c.at : null;
}

export { sideOf };
