// Small motion helpers: count-ups, scroll reveals, smooth scrolling. Everything respects reduced motion.
export const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

export const easeOut = (k) => 1 - Math.pow(1 - k, 4);
export const easeInOut = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

/** Count a number up inside `node`; fmt(v) renders the value. */
export function countUp(node, to, { from = 0, ms = 1200, delay = 0, fmt = (v) => Math.round(v) } = {}) {
  if (reduced) { node.textContent = fmt(to); return; }
  const t0 = performance.now() + delay;
  node.textContent = fmt(from);
  const step = (t) => {
    const k = Math.max(0, Math.min(1, (t - t0) / ms));
    node.textContent = fmt(from + (to - from) * easeOut(k));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/** Call fn when `node` scrolls into view (once by default). Returns a disposer. */
export function onEnter(node, fn, { threshold = 0.35, once = true } = {}) {
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (e.isIntersecting) { fn(e); if (once) io.unobserve(e.target); }
  }), { threshold });
  io.observe(node);
  return () => io.disconnect();
}

/** Fade-and-rise every `.reveal` inside root as it enters the viewport. */
export function reveals(root) {
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }), { threshold: 0.2 });
  root.querySelectorAll(".reveal").forEach((n) => io.observe(n));
  return () => io.disconnect();
}

/** Split an element's text into per-character spans and animate them in. */
export function splitIn(node, { delay = 120, stagger = 50 } = {}) {
  const text = node.textContent;
  node.textContent = "";
  node.setAttribute("aria-label", text);
  [...text].forEach((c, i) => {
    const s = document.createElement("span");
    s.className = "ch";
    s.setAttribute("aria-hidden", "true");
    s.textContent = c === " " ? " " : c;
    node.appendChild(s);
    if (!reduced) s.animate([{ transform: "translateY(55%)", opacity: 0, filter: "blur(8px)" },
      { transform: "none", opacity: 1, filter: "blur(0)" }],
      { duration: 900, delay: delay + i * stagger, fill: "both", easing: "cubic-bezier(.2,.8,.2,1)" });
  });
}

let lenis = null;
export function smoothScroll() {
  if (lenis || reduced || !window.Lenis) return lenis;
  lenis = new window.Lenis({ lerp: 0.09, wheelMultiplier: 0.95 });
  const raf = (t) => { lenis.raf(t); requestAnimationFrame(raf); };
  requestAnimationFrame(raf);
  return lenis;
}
export function scrollToTop() {
  if (lenis) lenis.scrollTo(0, { immediate: true }); else window.scrollTo(0, 0);
}
export function scrollToNode(node) {
  if (lenis) lenis.scrollTo(node, { duration: 1.4 }); else node.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
}
