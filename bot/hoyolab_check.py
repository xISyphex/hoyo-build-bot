"""Check what HoYoLAB sends for one player, on the bot's server (it has the cookies):

    sudo bash -c 'set -a; . /etc/hoyo-build-bot.env; cd /opt/hoyo-build-bot; .venv/bin/python -m bot.hoyolab_check genshin 618285856'

Prints a short summary per character (no nicknames, no cookies), so it's safe to paste into chat.

    ... -m bot.hoyolab_check starward 714485603

prints what HoYoLAB sends about Star Rail's end-game modes (numbers and flags only, no characters or names), to see
where the Starward stars are.
"""

from __future__ import annotations

import asyncio
import os
import sys

from .assets import Assets
from .hoyolab import HoyolabClient, HoyolabError


def _plain(data) -> dict:
    """The numbers and flags of one HoYoLAB object (no lists, names or pictures)."""
    return {k: v for k, v in data.items() if isinstance(v, (int, float, bool)) or (isinstance(v, str) and v.isdigit())}


async def starward(client, uid: int) -> None:
    for mode, get in (("moc", client.get_starrail_challenge), ("pf", client.get_starrail_pure_fiction),
                      ("apoc", client.get_starrail_apc_shadow)):
        data = await get(uid, raw=True)
        print(f"{mode}: {_plain(data)}")
        for floor in (data.get("all_floor_detail") or [])[:2]:
            print(f"  floor {floor.get('maze_id')}: {_plain(floor)}")
            for node in ("node_1", "node_2", "node_3"):
                if isinstance(floor.get(node), dict):
                    print(f"    {node}: {_plain(floor[node])}, other keys {sorted(k for k in floor[node] if k not in _plain(floor[node]))}")
            print(f"    other keys {sorted(k for k in floor if k not in _plain(floor) and not k.startswith('node_'))}")


async def main(game: str, uid: str) -> int:
    cookies = os.environ.get("HOYOLAB_COOKIES", "").strip()
    if not cookies:
        print("HOYOLAB_COOKIES isn't set. Add it to /etc/hoyo-build-bot.env first.")
        return 1
    assets = Assets(os.environ.get("CACHE_DIR", "data"))
    assets.load()
    client = HoyolabClient(cookies, assets)
    if game == "starward":
        await starward(client.client, int(uid))
        return 0
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
    if len(sys.argv) != 3 or sys.argv[1] not in ("genshin", "hsr", "zzz", "starward"):
        print("Usage: python -m bot.hoyolab_check genshin|hsr|zzz|starward UID")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
