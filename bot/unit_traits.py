"""Element and path / specialty / weapon type symbols for the units on the patch card's banners.

The characters coming next are often newer than the bot's own game data, so Genshin's and Star Rail's come from
Hakushin's latest data, which lists a unit once it's announced. ZZZ's channel calendar carries them itself. Only units
HoYoLAB's own calendar lists are ever looked up."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from .effective import HAKUSHIN
from .games.genshin import ELEMENT_ICONS as GI_ELEMENT_ICONS, WEAPON_ICONS
from .games.starrail import ELEMENTS as HSR_ELEMENTS, PATH_ICONS, SRR_ELEMENT_ICONS, SRR_PATH_ICONS

log = logging.getLogger(__name__)

MAX_AGE = 12 * 3600
GI_ELEMENTS = {"Pyro": "Fire", "Hydro": "Water", "Anemo": "Wind", "Electro": "Electric", "Dendro": "Grass",
               "Geo": "Rock", "Cryo": "Ice"}
CRYO = "symbol:cryo"  # Enka has no Cryo symbol; the card draws its snowflake instead
# HoYoLAB's Star Rail path numbers -> the game data's path ids
HSR_PATHS = {1: "Warrior", 2: "Rogue", 3: "Mage", 4: "Shaman", 5: "Warlock", 6: "Knight", 7: "Priest", 8: "Memory",
             9: "Elation"}
ZZZ_ELEMENTS = {200: "Physical", 201: "Fire", 202: "Ice", 203: "Electric", 204: "Wind", 205: "Ether", 300: "Lumiflux"}
ZZZ_SUB_ELEMENTS = {202: "Frost", 205: "AuricInk"}  # an Ice or Ether agent with a sub-element
ZZZ_SPECIALTIES = {1: "Attack", 2: "Stun", 3: "Anomaly", 4: "Support", 5: "Defense", 6: "Rupture", 7: "Armorer"}
# game -> Hakushin's lists and how to read (element, path / weapon type) from an entry
FILES = {
    "gi": (("character.json", lambda e: (e.get("element"), e.get("weapon"))),
           ("weapon.json", lambda e: (None, e.get("type")))),
    "hsr": (("character.json", lambda e: (e.get("damageType"), e.get("baseType"))),
            ("lightcone.json", lambda e: (None, e.get("baseType")))),
}


def genshin_urls(element: str | None, weapon_type: str | None) -> list[str]:
    urls = []
    name = GI_ELEMENTS.get(element or "", element)
    if name in GI_ELEMENT_ICONS:
        urls.append(f"https://enka.network/ui/UI_Buff_Element_{name}.png")
    elif name == "Ice":
        urls.append(CRYO)
    if weapon_type in WEAPON_ICONS:
        urls.append(f"https://enka.network/ui/UI_GachaTypeIcon_{WEAPON_ICONS[weapon_type]}.png")
    return urls


def hsr_urls(element: str | None, path: str | None) -> list[str]:
    urls = []
    if element in HSR_ELEMENTS:
        urls.append(f"{SRR_ELEMENT_ICONS}{element}.png")
    if path in PATH_ICONS:
        urls.append(f"{SRR_PATH_ICONS}{PATH_ICONS[path]}.png")
    return urls


def zzz_urls(element: int | None, sub_element: int | None, specialty: int | None) -> list[str]:
    urls = []
    name = ZZZ_SUB_ELEMENTS.get(element) if sub_element else None
    name = name or ZZZ_ELEMENTS.get(element)
    if name:
        urls.append(f"https://static.nanoka.cc/assets/zzz/Icon{name}.webp")
    if specialty in ZZZ_SPECIALTIES:
        urls.append(f"https://enka.network/ui/zzz/Icon{ZZZ_SPECIALTIES[specialty]}.png")
    return urls


class UnitTraits:
    """Item id -> (element, path / weapon type) for Genshin and Star Rail, kept in traits.json."""

    def __init__(self, cache_dir: str | Path):
        self.path = Path(cache_dir) / "traits.json"
        self.table: dict[str, dict[str, list]] = {game: {} for game in FILES}
        self.updated = 0.0
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for game in self.table:
                self.table[game].update(data.get(game, {}))
            self.updated = float(data.get("updated", 0))
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            log.exception("Could not read %s", self.path)

    def is_stale(self) -> bool:
        return time.time() - self.updated > MAX_AGE

    def genshin(self, item_id, element: str | None = None) -> list[str]:
        """Symbols for a Genshin character or weapon; element is the calendar's own, used when Hakushin lacks one."""
        known, kind = self.table["gi"].get(str(item_id)) or (None, None)
        return genshin_urls(known or element, kind)

    def hsr(self, item_id, path: int | None = None) -> list[str]:
        """Symbols for a Star Rail character or light cone; path is the calendar's own number."""
        element, known = self.table["hsr"].get(str(item_id)) or (None, None)
        return hsr_urls(element, known or HSR_PATHS.get(path or 0))

    async def refresh(self, session) -> None:
        try:
            async with session.get(f"{HAKUSHIN}/manifest.json") as resp:
                resp.raise_for_status()
                manifest = await resp.json(content_type=None)
        except Exception:
            log.exception("Could not read Hakushin's manifest; keeping the saved unit symbols")
            return

        async def get(path: str):
            try:
                async with session.get(f"{HAKUSHIN}/{path}") as resp:
                    return await resp.json(content_type=None) if resp.status == 200 else None
            except Exception:
                return None

        for game, files in FILES.items():
            version = (manifest.get(game) or {}).get("latest")
            lists = await asyncio.gather(*(get(f"{game}/{version}/{name}") for name, _ in files)) if version else []
            for (name, read), data in zip(files, lists):
                if not isinstance(data, dict):
                    log.warning("No %s %s on Hakushin", game, name)
                    continue
                for item_id, entry in data.items():
                    if isinstance(entry, dict):
                        self.table[game][str(item_id)] = list(read(entry))
        self.updated = time.time()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps({**self.table, "updated": self.updated}), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            log.exception("Could not save %s", self.path)
        log.info("Unit symbols: %s", {g: len(t) for g, t in self.table.items()})
