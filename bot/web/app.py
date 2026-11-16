"""The optimizer website: the page and its JSON API, served by aiohttp inside the bot's own event loop.

Routes:
    GET  /hsr/optimize            the page (the session token rides in the URL fragment, so it never reaches a log)
    GET  /static/...              its CSS, JS and fonts
    GET  /api/hsr/meta            characters, light cones and sets for the pickers (no token needed, cached, ETag)
    GET  /api/hsr/session         the player's characters and relics            (Authorization: Bearer <token>)
    POST /api/hsr/relics/import   a relic file (not implemented yet: 501)        (Authorization: Bearer <token>)
    POST /api/hsr/optimize        run the search, see bot/web/schema.py           (Authorization: Bearer <token>)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from aiohttp import web

from . import engine, schema
from .inventory import session_payload
from .meta import IMAGE_HOSTS, MetaCache
from .sessions import Session, SessionStore

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
FONTS = Path(__file__).resolve().parent.parent / "fonts"
FONT_FILES = {"Rajdhani-Medium.ttf", "Rajdhani-SemiBold.ttf", "Rajdhani-Bold.ttf"}
IMPORT_LIMIT = 5 * 1024 * 1024  # a relic file
JSON_LIMIT = 64 * 1024  # an optimize request

CSP = "; ".join([
    "default-src 'none'",
    "script-src 'self'",
    "style-src 'self'",
    "font-src 'self'",
    "img-src 'self' data: " + " ".join(IMAGE_HOSTS),
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
])
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

CONTEXT = web.AppKey("context", object)


@dataclass
class WebContext:
    """What the site needs from the bot: the game data, the stats and sets each character wants, the beta's
    characters, and the sessions."""

    assets: object
    effective: object  # EffectiveStats: wanted(build), recommended_sets(id, planar)
    unreleased: object | None
    sessions: SessionStore
    base_url: str

    def __post_init__(self):
        self.meta = MetaCache(self.assets, self.effective)

    def link(self, session: Session) -> str:
        return f"{self.base_url}/hsr/optimize#{session.token}"


def error(status: int, message: str, **extra) -> web.Response:
    return web.json_response({"error": message, **extra}, status=status)


class ApiError(Exception):
    """Ends a request with a JSON error."""

    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


@web.middleware
async def guard(request: web.Request, handler):
    """Security headers on everything; API errors as JSON, never a stack trace."""
    api = request.path.startswith("/api/")
    try:
        response = await handler(request)
    except ApiError as exc:
        response = error(exc.status, exc.message, **exc.extra)
    except web.HTTPException as exc:
        if api:
            response = error(exc.status, {404: "not found", 405: "method not allowed",
                                          413: "request too large"}.get(exc.status, exc.reason.lower()))
        else:
            response = web.Response(status=exc.status, text=exc.text or exc.reason, headers=exc.headers)
    except Exception:
        log.exception("Optimizer site: %s %s failed", request.method, request.path)
        response = error(500, "internal error") if api else web.Response(status=500, text="Internal error")
    for key, value in SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    if api:
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _session(request: web.Request) -> Session:
    ctx: WebContext = request.app[CONTEXT]
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "missing token")
    session = ctx.sessions.get(token.strip())
    if session is None:
        raise ApiError(401, "session expired", hint="Run /hsr-optimize again.")
    return session


async def page(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(STATIC / "optimize.html", headers={"Cache-Control": "no-cache"})


async def font(request: web.Request) -> web.StreamResponse:
    name = request.match_info["name"]
    if name not in FONT_FILES:
        raise web.HTTPNotFound()
    return web.FileResponse(FONTS / name, headers={"Cache-Control": "public, max-age=604800"})


async def meta(request: web.Request) -> web.StreamResponse:
    ctx: WebContext = request.app[CONTEXT]
    _, body, etag = ctx.meta.get()
    headers = {"ETag": etag, "Cache-Control": "public, max-age=300"}
    if etag in request.headers.get("If-None-Match", ""):
        return web.Response(status=304, headers=headers)
    response = web.Response(body=body, content_type="application/json", headers=headers)
    response.enable_compression()
    return response


async def session_info(request: web.Request) -> web.StreamResponse:
    ctx: WebContext = request.app[CONTEXT]
    session = _session(request)
    response = web.json_response(session_payload(ctx.assets, session, ctx.meta))
    response.enable_compression()
    return response


async def import_relics(request: web.Request) -> web.StreamResponse:
    _session(request)
    if (request.content_length or 0) > IMPORT_LIMIT:
        return error(413, "request too large", limit=IMPORT_LIMIT)
    body = await request.read()  # the app's client_max_size stops anything over the limit
    try:
        json.loads(body)
    except ValueError:
        return error(400, "the file isn't JSON")
    return error(501, "not implemented")


async def run_optimize(request: web.Request) -> web.StreamResponse:
    ctx: WebContext = request.app[CONTEXT]
    session = _session(request)
    if (request.content_length or 0) > JSON_LIMIT:
        return error(413, "request too large", limit=JSON_LIMIT)
    body = await request.read()
    if len(body) > JSON_LIMIT:
        return error(413, "request too large", limit=JSON_LIMIT)
    try:
        data = json.loads(body)
    except ValueError:
        return error(400, "the body isn't JSON")
    try:
        config = schema.check(data, ctx.meta.get()[0])
    except schema.Invalid as exc:
        return error(400, "invalid request", details=exc.errors)
    if session.busy:
        return error(409, "an optimize is already running for this session")
    wait = session.take_call(time.time())
    if wait is not None:
        response = error(429, "too many optimize runs; wait a few minutes", retry_after=int(wait) + 1)
        response.headers["Retry-After"] = str(int(wait) + 1)
        return response
    name = ctx.meta.character(config["character"]["id"])["name"]
    session.busy = True
    try:
        result = await engine.run(ctx, session, config, name)
    except engine.EngineError as exc:
        return error(422, str(exc))
    finally:
        session.busy = False
    return web.json_response(result)


def make_app(ctx: WebContext) -> web.Application:
    app = web.Application(middlewares=[guard], client_max_size=IMPORT_LIMIT)
    app[CONTEXT] = ctx
    app.router.add_get("/hsr/optimize", page)
    app.router.add_get("/static/fonts/{name}", font)
    app.router.add_static("/static/", STATIC, show_index=False, follow_symlinks=False)
    app.router.add_get("/api/hsr/meta", meta)
    app.router.add_get("/api/hsr/session", session_info)
    app.router.add_post("/api/hsr/relics/import", import_relics)
    app.router.add_post("/api/hsr/optimize", run_optimize)
    return app
