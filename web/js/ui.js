// Small shared UI pieces: segmented controls and the hover tooltip.
/** A segmented control with a sliding indicator. */
export function segment(host, options, current, onPick, cls = "") {
  host.className = `seg ${cls}`;
  host.innerHTML = `<div class="ind"></div>` + options.map(([k, l]) => `<button type="button" data-k="${k}">${l}</button>`).join(""); // labels are trusted constants
  const ind = host.querySelector(".ind");
  const set = (k) => {
    host.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.k === k));
    const b = host.querySelector(`button[data-k="${k}"]`);
    if (b) { ind.style.left = `${b.offsetLeft}px`; ind.style.width = `${b.offsetWidth}px`; }
  };
  host.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { set(b.dataset.k); onPick(b.dataset.k); }));
  requestAnimationFrame(() => set(current));
  set(current);
  return set;
}

export function tooltip() {
  const t = document.createElement("div");
  t.className = "tip";
  document.body.appendChild(t);
  const move = (e) => { t.style.left = `${Math.min(e.clientX + 14, innerWidth - 300)}px`; t.style.top = `${e.clientY + 14}px`; };
  return { show: (e, html) => { t.innerHTML = html; t.classList.add("on"); move(e); }, move, hide: () => t.classList.remove("on"),
    remove: () => t.remove() };
}

