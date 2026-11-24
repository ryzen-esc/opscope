// ⌘K team palette: type to filter, arrows to move, Enter to scout.
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
export function setupPalette({ teams, onPick }) {
  const box = document.getElementById("palette");
  const input = document.getElementById("paletteInput");
  const list = document.getElementById("paletteList");
  let shown = [], sel = 0, lastFocus = null;

  function render() {
    const q = input.value.trim().toLowerCase();
    shown = teams.filter((t) => t.name.toLowerCase().includes(q)).slice(0, 40);
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    list.innerHTML = shown.map((t, i) => `<li role="option" data-id="${t.id}" aria-selected="${i === sel}">
      <span>${esc(t.name)}</span><small>${t.self_scout ? "SELF-SCOUT" : "SCOUT"}</small></li>`).join("")
      || `<li aria-disabled="true"><span>No team matches “${esc(input.value)}”</span></li>`;
    list.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }
  function open() {
    lastFocus = document.activeElement;
    box.hidden = false; input.value = ""; sel = 0; render();
    input.focus();
  }
  function close() { box.hidden = true; lastFocus?.focus?.(); }
  function pick(id) { if (!id) return; close(); onPick(id); }

  document.getElementById("switch").addEventListener("click", open);
  addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); box.hidden ? open() : close(); return; }
    if (box.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, shown.length - 1); render(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); render(); }
    else if (e.key === "Enter") { e.preventDefault(); pick(shown[sel]?.id); }
  });
  input.addEventListener("input", () => { sel = 0; render(); });
  list.addEventListener("click", (e) => pick(e.target.closest("li")?.dataset.id));
  box.addEventListener("click", (e) => { if (e.target === box) close(); });
  return { open, close };
}
