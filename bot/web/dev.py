"""The optimizer site on its own, without Discord, for working on the page:

    python -m bot.web.dev [--port 8080] [--host 127.0.0.1]

It serves one made-up session (the test fixture's account, with its first four characters' relics moved to Scholar
Lost in Erudition and Rutilant Arena so there is something to swap) and prints its link. Uses the game data in
CACHE_DIR (default ./data), downloading it when missing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

import aiohttp

from ..assets import Assets
from ..effective import EffectiveStats
from ..games import starrail
from ..models import CharacterBuild
from ..optimize import PLANAR_SLOTS
from ..unreleased import Unreleased
from . import WebConfig, WebContext, start
from .sessions import SessionStore

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "hsr_live.json"
SAMPLE_SETS = ("Scholar Lost in Erudition", "Rutilant Arena")


def sample_builds(assets: Assets, shared: int = 4) -> tuple[str, list[CharacterBuild]]:
    """The fixture's made-up account; its first `shared` characters wear the two sample sets."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    profile = starrail.parse_profile(assets, str(data.get("uid", "800000000")), data)
    for build in [b for b in profile.characters if len(b.gear) == 6][:shared]:
        for gear in build.gear:
            gear.set_name = SAMPLE_SETS[1] if gear.slot in PLANAR_SLOTS else SAMPLE_SETS[0]
    return profile.uid, profile.characters


async def main(host: str, port: int) -> None:
    cache = os.environ.get("CACHE_DIR", "data")
    assets = Assets(cache)
    if assets.is_stale():
        async with aiohttp.ClientSession(trust_env=True) as http:
            await assets.refresh(http)
    else:
        assets.load()
    beta = Unreleased(cache)
    beta.apply(assets)
    base = f"http://{host}:{port}"
    ctx = WebContext(assets, EffectiveStats(cache), beta, SessionStore(), base)
    uid, builds = sample_builds(assets)
    session = ctx.sessions.create(0, uid, builds)
    runner = await start(ctx, WebConfig(base, host, port))
    print(f"Optimizer page (made-up session, 2 hours): {ctx.link(session)}", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
