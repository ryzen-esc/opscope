// Thin client for the local OpScope API. Responses are cached per URL for the session.
const cache = new Map();

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

function url(path, params = {}) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "") continue;
    for (const item of Array.isArray(v) ? v : [v]) if (item !== "" && item != null) q.append(k, item);
  }
  const s = q.toString();
  return s ? `${path}?${s}` : path;
}

export function get(path, params) {
  const u = url(path, params);
  if (!cache.has(u)) {
    const p = fetch(u).then(async (r) => {
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new ApiError(r.status, body);
      return body;
    });
    p.catch(() => cache.delete(u)); // let a failed request be retried
    cache.set(u, p);
  }
  return cache.get(u);
}

const scope = (f = {}) => ({ maps: f.maps, opponents: f.opponents, patches: f.patches, events: f.events });

export const api = {
  meta: () => get("/api/meta"),
  filters: (team) => get(`/api/team/${encodeURIComponent(team)}/filters`),
  map: (name) => get(`/api/map/${encodeURIComponent(name)}`),
  report: (team, f) => get("/api/report", { team, ...scope(f) }),
  operator: (team, f = {}) => get("/api/operator", { team, weapon: f.weapon, side: f.side, ...scope(f) }),
  utility: (team, f = {}) => get("/api/utility", { team, side: f.side, classes: f.classes, phases: f.phases, ...scope(f) }),
};
