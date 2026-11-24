"""JSON API over the analytics (Starlette). Served by `opscope.server` on 127.0.0.1 only.

GET /api/meta                          teams, quick picks, data summary, pipeline numbers, rules
GET /api/team/{team_id}/filters        maps, opponents, patches, events for that team
GET /api/map/{map}                     map geometry in the view frame (outline, props, site zones, sites, spawns)
GET /api/report?team=…                 scouting report (filters: maps, opponents, patches, events)
GET /api/operator?team=…&weapon=…      Operator profiler (plus side)
GET /api/utility?team=…&classes=…      Utility profiler (plus side, phases)

List filters repeat the parameter: `?maps=haven&maps=lotus`. `side` is attacker, defender or both.
"""
from __future__ import annotations

import json
import math

import numpy as np
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

SETUP_STEPS = [
    "Clone the hackathon data repo next to this project (see the README): "
    "git clone --filter=blob:none --sparse https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git",
    "Copy .env.example to .env and point STL_DATA_DIR at that clone.",
    "Build the cache (about 4 minutes): uv run python -m opscope.ingest.build",
    "Reload this page.",
]
SIDES = {"attacker": "attacker", "defender": "defender", "both": None, "": None}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _clean(o):
    """numpy / pandas values -> plain JSON (NaN and NA become null)."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) or math.isinf(o) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if o is None or isinstance(o, (str, int, bool)):
        return o
    try:
        import pandas as pd
        if pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    return str(o)


def json_response(content, status: int = 200) -> Response:
    body = json.dumps(_clean(content), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return Response(body, status_code=status, media_type="application/json")


def _list(req: Request, name: str) -> tuple[str, ...]:
    return tuple(v for v in req.query_params.getlist(name) if v)


def _team(req: Request) -> str:
    from opscope.present import team_labels
    tid = req.query_params.get("team", "")
    if tid not in team_labels():
        raise ApiError(404, f"Unknown team: {tid!r}")
    return tid


def _side(req: Request, default: str = "defender") -> str | None:
    side = req.query_params.get("side", default)
    if side not in SIDES:
        raise ApiError(400, f"side must be attacker, defender or both, not {side!r}")
    return SIDES[side]


def _scope_kwargs(req: Request) -> dict:
    return {"maps": _list(req, "maps"), "opponents": _list(req, "opponents"), "patches": _list(req, "patches"),
            "events": _list(req, "events")}


def endpoint(fn):
    """Run a handler and turn its result (or a known failure) into JSON."""
    def handler(req: Request) -> Response:
        try:
            return json_response(fn(req))
        except ApiError as e:
            return json_response({"error": e.message}, e.status)
        except (FileNotFoundError, RuntimeError) as e:  # no cache yet, or STL_DATA_DIR not set
            return json_response({"error": "setup", "setup": SETUP_STEPS, "detail": str(e)}, 503)
    return handler


@endpoint
def meta(req: Request):
    from opscope.present import meta
    return meta()


@endpoint
def team_filters(req: Request):
    from opscope.present import team_filters, team_labels
    tid = req.path_params["team_id"]
    if tid not in team_labels():
        raise ApiError(404, f"Unknown team: {tid!r}")
    return team_filters(tid)


@endpoint
def map_geometry(req: Request):
    from opscope.geometry import transforms
    from opscope.present import geometry
    name = req.path_params["map"].lower()
    if name not in transforms():
        raise ApiError(404, f"Unknown map: {name!r}")
    return geometry(name)


@endpoint
def report(req: Request):
    from opscope.analytics.operator import Scope
    from opscope.present import report
    return report(Scope(team_id=_team(req), side=None, **_scope_kwargs(req)))


@endpoint
def operator(req: Request):
    from opscope.analytics.operator import Scope
    from opscope.present import WEAPONS, operator
    weapon = req.query_params.get("weapon", "operator")
    if weapon not in WEAPONS:
        raise ApiError(400, f"weapon must be one of {', '.join(WEAPONS)}")
    return operator(Scope(team_id=_team(req), weapon=weapon, side=_side(req), **_scope_kwargs(req)))


@endpoint
def utility(req: Request):
    from opscope.analytics.utility import UtilityScope
    from opscope.present import UTIL_CLASSES, utility
    classes = _list(req, "classes")
    if any(c not in UTIL_CLASSES for c in classes):
        raise ApiError(400, f"classes must be among {', '.join(UTIL_CLASSES)}")
    phases = _list(req, "phases")
    if any(p not in ("buy", "live") for p in phases):
        raise ApiError(400, "phases must be buy and/or live")
    return utility(UtilityScope(team_id=_team(req), side=_side(req), classes=tuple(sorted(classes)),
                                phases=tuple(sorted(phases)), **_scope_kwargs(req)))


routes = [
    Route("/api/meta", meta),
    Route("/api/team/{team_id}/filters", team_filters),
    Route("/api/map/{map}", map_geometry),
    Route("/api/report", report),
    Route("/api/operator", operator),
    Route("/api/utility", utility),
]


class NoStaleAssets:
    """Ask browsers to revalidate the front end's files on every load (cheap: unchanged files answer 304), so an
    updated app never runs with yesterday's CSS or JS."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"] = [h for h in message["headers"] if h[0].lower() != b"cache-control"]
                message["headers"].append((b"cache-control", b"no-cache"))
            await send(message)
        await self.app(scope, receive, send_with_header)


# The server binds to 127.0.0.1, but that alone does not stop DNS rebinding: a web page whose hostname is rebound to
# 127.0.0.1 would be same-origin with the API and could read the GRID-derived data. Answer only our own host names
# (the port in the Host header is ignored, so any --port works).
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


def create_app(static_dir=None) -> Starlette:
    """The API, plus the web front end from `static_dir` when given. Requests for any other Host get a 400."""
    all_routes = list(routes)
    if static_dir is not None:
        from starlette.routing import Mount
        from starlette.staticfiles import StaticFiles
        all_routes.append(Mount("/", StaticFiles(directory=static_dir, html=True), name="web"))
    return Starlette(routes=all_routes, middleware=[
        Middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False),
        Middleware(GZipMiddleware, minimum_size=2000),
        Middleware(NoStaleAssets),
    ])
