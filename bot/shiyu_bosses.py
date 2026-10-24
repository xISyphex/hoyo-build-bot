"""Who the boss was in each of Shiyu Defense's final battles, for the /zzz-records labels.

HoYoLAB only sends the boss's picture, so the name comes from Hakushin's game data: the season (HoYoLAB's zone id)
lists each battle room's boss icon, and the monster list has the English name for that icon. A season's names never
change, so they're kept in shiyu_bosses.json once found."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from .effective import HAKUSHIN

log = logging.getLogger(__name__)


def _stem(path: str) -> str:
    """'.../IconMonster_MiasmaThracian.png' -> 'MiasmaThracian' (the same for the monster list's 'Monster_...')."""
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return name.split("_", 1)[1] if "_" in name else name


def boss_names(season: dict, monsters: dict) -> dict[str, str]:
    """Room (layer) id -> boss name, for every room of a Hakushin season whose boss icon names a known monster."""
    by_icon = {_stem(m["icon"]): m["en"] for m in monsters.values() if isinstance(m, dict) and m.get("icon") and m.get("en")}
    names = {}
    for zone in (season.get("zone") or {}).values():
        for room_id, room in (zone.get("layer_room") or {}).items():
            stem = _stem(room.get("monster_icon") or "")
            name = by_icon.get(stem) or by_icon.get(stem.removesuffix("Boss"))
            if name:
                names[str(room_id)] = name
    return names


class ShiyuBosses:
    def __init__(self, cache_dir: str | Path):
        self.path = Path(cache_dir) / "shiyu_bosses.json"
        try:
            self.known: dict[str, dict[str, str]] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.known = {}
        self.missed: dict[str, float] = {}  # season -> when Hakushin last didn't know it (asked again after an hour)

    async def _find(self, session, zone: str) -> dict[str, str]:
        async def get(path: str):
            async with session.get(f"{HAKUSHIN}/{path}") as resp:
                return await resp.json(content_type=None) if resp.status == 200 else None

        manifest = await get("manifest.json") or {}
        for version in dict.fromkeys(filter(None, ((manifest.get("zzz") or {}).get(k) for k in ("latest", "live")))):
            season, monsters = await asyncio.gather(get(f"zzz/{version}/en/shiyu/{zone}.json"), get(f"zzz/{version}/monster.json"))
            if isinstance(season, dict) and isinstance(monsters, dict):
                return boss_names(season, monsters)
        return {}

    async def name(self, session, zone, layer_ids: list) -> dict[str, str]:
        """Layer id -> boss name for this season's battles (empty when Hakushin doesn't know them)."""
        zone = str(zone)
        stale = zone not in self.known or any(str(i) not in self.known[zone] for i in layer_ids)
        if stale and (zone not in self.missed or time.monotonic() - self.missed[zone] >= 3600):
            try:
                found = await asyncio.wait_for(self._find(session, zone), 8)
            except Exception as exc:
                log.info("No Shiyu Defense boss names for season %s: %s", zone, exc)
                found = {}
            if not found or any(str(i) not in found for i in layer_ids):
                self.missed[zone] = time.monotonic()
            if found:
                self.known[zone] = found
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text(json.dumps(self.known), encoding="utf-8")
                except OSError:
                    log.exception("Could not save %s", self.path)
        return self.known.get(zone, {})
