"""The boss of each Memory of Chaos and Pure Fiction node, as a picture for the /hsr-records boxes.

HoYoLAB sends no boss for these two modes (Apocalyptic Shadow's come with its season), so they come from Hakushin's
game data: the season's file lists each floor (by the same maze id HoYoLAB gives the floor) with the enemies of its
two halves, and the Starward floor's on an entry of its own. The strongest enemy of each half is its boss, and the
monster list has its picture. Each box shows its boss's name too. A floor's bosses never change, so they're kept in hsr_bosses.json once found."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path

from .effective import HAKUSHIN

log = logging.getLogger(__name__)

PATHS = {"moc": "en/maze/{season}.json", "pf": "en/story/{season}.json"}
RANKS = ("Minion", "MinionLv2", "Elite", "LittleBoss", "BigBoss")  # weakest first


def _floors(season) -> list[dict]:
    """A season file's floor entries (Pure Fiction keeps them under 'level')."""
    if isinstance(season, dict):
        season = season.get("level")
    return [f for f in season or () if isinstance(f, dict)]


def _boss(ids, monsters: dict) -> dict[str, str] | None:
    """The picture and name of the strongest enemy in the list (the last one listed, among equals)."""
    known = [monsters[str(i)] for i in ids or () if isinstance(monsters.get(str(i)), dict) and monsters[str(i)].get("icon")]
    if not known:
        return None
    best = max(reversed(known), key=lambda m: RANKS.index(m.get("rank")) if m.get("rank") in RANKS else -1)
    stem = best["icon"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
    name = re.sub(r"<[^>]*>", "", best.get("en") or "").strip()
    return {"art": f"{HAKUSHIN}/assets/hsr/monsterfigure/{stem}.webp", "name": name}


def boss_art(season, monsters: dict, floor_id: str) -> dict[str, dict[str, str]]:
    """Node ("1", "2", "3" for Starward) -> boss {"art": picture, "name": name}, for one floor of a Hakushin season."""
    floors = _floors(season)
    arts = {}
    floor = next((f for f in floors if str(f.get("id")) == str(floor_id)), None)
    if floor:
        for node in ("1", "2"):
            if art := _boss(floor.get(f"npc_monster_id_list{node}"), monsters):
                arts[node] = art
    starward = next((f for f in floors if f.get("npc_monster_id_list")), None)  # the one floor with a single list
    if starward and (art := _boss(starward.get("npc_monster_id_list"), monsters)):
        arts["3"] = art
    return arts


class HsrBosses:
    def __init__(self, cache_dir: str | Path):
        self.path = Path(cache_dir) / "hsr_bosses.json"
        try:
            self.known: dict[str, dict[str, dict[str, str]]] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.known = {}
        self.missed: dict[str, float] = {}  # floor -> when Hakushin last didn't know it (asked again after an hour)

    async def _find(self, session, mode: str, season: str, floor: str) -> dict[str, dict[str, str]]:
        async def get(path: str):
            async with session.get(f"{HAKUSHIN}/{path}") as resp:
                return await resp.json(content_type=None) if resp.status == 200 else None

        manifest = await get("manifest.json") or {}
        for version in dict.fromkeys(filter(None, ((manifest.get("hsr") or {}).get(k) for k in ("latest", "live")))):
            data, monsters = await asyncio.gather(get(f"hsr/{version}/" + PATHS[mode].format(season=season)),
                                                  get(f"hsr/{version}/monster.json"))
            if data and isinstance(monsters, dict):
                return boss_art(data, monsters, floor)
        return {}

    async def arts(self, session, mode: str, season, floor) -> dict[str, dict[str, str]]:
        """Node -> boss {"art", "name"} for this floor (empty when Hakushin doesn't know it)."""
        if mode not in PATHS or not season or not floor:
            return {}
        key = f"{mode}/{season}/{floor}"
        if key not in self.known and (key not in self.missed or time.monotonic() - self.missed[key] >= 3600):
            try:
                found = await asyncio.wait_for(self._find(session, mode, str(season), str(floor)), 8)
            except Exception as exc:
                log.info("No %s bosses for %s: %s", mode, key, exc)
                found = {}
            if found:
                self.known[key] = found
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text(json.dumps(self.known), encoding="utf-8")
                except OSError:
                    log.exception("Could not save %s", self.path)
            else:
                self.missed[key] = time.monotonic()
        return self.known.get(key, {})
