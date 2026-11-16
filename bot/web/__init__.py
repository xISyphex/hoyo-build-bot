"""The optimizer website, served from the bot's own process when WEB_BASE_URL is set.

    WEB_BASE_URL  the public address links point at (https://example.ts.net); unset: no website, and /hsr-optimize
                  answers in Discord as before
    WEB_HOST      the address to listen on (default 127.0.0.1: put a reverse proxy or tunnel in front)
    WEB_PORT      the port to listen on (default 8080)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from aiohttp import web

from .app import WebContext, make_app
from .sessions import SessionStore

log = logging.getLogger(__name__)

__all__ = ["WebConfig", "WebContext", "SessionStore", "config_from_env", "make_app", "start"]


@dataclass(frozen=True)
class WebConfig:
    base_url: str
    host: str = "127.0.0.1"
    port: int = 8080


def config_from_env(env=None) -> WebConfig | None:
    """The website's settings, or None when WEB_BASE_URL isn't set (no website)."""
    env = os.environ if env is None else env
    base = (env.get("WEB_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return None
    if not base.startswith(("https://", "http://")):
        raise ValueError("WEB_BASE_URL must start with https:// (or http:// for testing)")
    port = int(env.get("WEB_PORT") or 8080)
    return WebConfig(base, (env.get("WEB_HOST") or "127.0.0.1").strip(), port)


async def start(ctx: WebContext, config: WebConfig) -> web.AppRunner:
    """Starts the website on the running event loop. Stop it with `await runner.cleanup()`."""
    runner = web.AppRunner(make_app(ctx), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, config.host, config.port).start()
    log.info("Optimizer site listening on %s:%s, links point at %s", config.host, config.port, config.base_url)
    return runner
