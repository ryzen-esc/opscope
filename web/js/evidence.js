// The evidence bar: the team's rate (dot), its 95% range (band) and the typical team or player (tick).
import { reduced } from "./motion.js";

const pct = (v) => `${Math.round(v * 100)}%`;
/** Keep a label inside the bar when its value sits near either end. */
const edge = (v) => (v < 0.1 ? "transform:translateX(-4px)" : v > 0.9 ? "transform:translateX(calc(-100% + 4px))" : "");

/**
 * ev: {rate, lo, hi, base, k, n}. opts: {side: "attacker"|"defender", labels: true, baseLabel: "typical"}.
 * Returns {node, play(delay)}; the bar is drawn complete until play() animates it in.
 */
export function evidenceBar(ev, { side = "defender", labels = true, baseLabel = "typical" } = {}) {
  const rate = ev.rate ?? ev.k / ev.n;
  const node = document.createElement("div");
  node.className = `evbar${side === "attacker" ? " atk" : ""}${labels ? "" : " plain"}`;
  node.setAttribute("role", "img");
  node.setAttribute("aria-label", `${pct(rate)} (${ev.k} of ${ev.n}), 95% range ${pct(ev.lo)} to ${pct(ev.hi)}`
    + (ev.base != null ? `, ${baseLabel} ${pct(ev.base)}` : ""));
  node.innerHTML = `
    <div class="band" style="left:${ev.lo * 100}%;width:${(ev.hi - ev.lo) * 100}%;transform-origin:${
      ((rate - ev.lo) / Math.max(ev.hi - ev.lo, 1e-6)) * 100}% 50%"></div>
    ${ev.base != null ? `<div class="tick" style="left:${ev.base * 100}%"></div>` : ""}
    <div class="dot" style="left:${rate * 100}%"></div>
    ${labels ? `<div class="lab rate" style="left:${rate * 100}%;${edge(rate)}">${pct(rate)}</div>` : ""}
    ${labels && ev.base != null ? `<div class="lab base" style="left:${ev.base * 100}%;${edge(ev.base)}">${baseLabel} ${pct(ev.base)}</div>` : ""}`;
  const q = (s) => node.querySelector(s);
  function play(delay = 0) {
    if (reduced) return;
    const opts = (d, extra = {}) => ({ duration: d, delay, fill: "both", easing: "cubic-bezier(.2,.8,.2,1)", ...extra });
    q(".tick")?.animate([{ transform: "scaleY(0)", opacity: 0 }, { transform: "none", opacity: 1 }], opts(400));
    q(".dot").animate([{ left: `${(ev.base ?? 0) * 100}%`, transform: "scale(.4)", opacity: 0 },
      { left: `${rate * 100}%`, transform: "none", opacity: 1 }], opts(900, { delay: delay + 300 }));
    q(".band").animate([{ transform: "scaleX(0)" }, { transform: "none" }], opts(700, { delay: delay + 900 }));
    node.querySelectorAll(".lab").forEach((l, i) =>
      l.animate([{ opacity: 0 }, { opacity: 1 }], opts(400, { delay: delay + 700 + i * 300 })));
  }
  return { node, play };
}
