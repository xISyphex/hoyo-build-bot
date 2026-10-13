"""Check what HoYoLAB sends for one player, on the bot's server (it has the cookies):

    sudo bash -c 'set -a; . /etc/hoyo-build-bot.env; cd /opt/hoyo-build-bot; .venv/bin/python -m bot.hoyolab_check genshin 618285856'

Prints a short summary per character (no nicknames, no cookies), so it's safe to paste into chat.
"""

from __future__ import annotations

import asyncio
import os
import sys

from .assets import Assets
from .hoyolab import HoyolabClient, HoyolabError


async def main(game: str, uid: str) -> int:
    cookies = os.environ.get("HOYOLAB_COOKIES", "").strip()
    if not cookies:
        print("HOYOLAB_COOKIES isn't set. Add it to /etc/hoyo-build-bot.env first.")
        return 1
    assets = Assets(os.environ.get("CACHE_DIR", "data"))
    assets.load()
    client = HoyolabClient(cookies, assets)
    try:
        builds = await client.fetch(game, uid)
    except HoyolabError as exc:
        print(f"HoYoLAB said no: {exc}")
        return 1
    print(f"{len(builds)} characters from HoYoLAB for {game} UID {uid}:")
    for b in builds:
        subs = [s for g in b.gear for s in g.subs]
        rolls = [s.rolls for g in b.gear[:1] for s in g.subs]
        print(
            f"- {b.name}: Lv. {b.level}, C/E/M{b.constellation}, {len(b.stats)} stats, "
            f"weapon: {'yes' if b.weapon else 'no'}, {len(b.gear)} gear pieces with {len(subs)} substats, "
            f"first piece rolls {rolls} (level {b.gear[0].level if b.gear else '-'})"
        )
    if builds:
        b = builds[0]
        print(f"Example, {b.name}: " + ", ".join(f"{s.name} {s.value}" for s in b.stats))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("genshin", "hsr", "zzz"):
        print("Usage: python -m bot.hoyolab_check genshin|hsr|zzz UID")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
