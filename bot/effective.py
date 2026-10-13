"""Which substats each character wants ("effective" substats), for the count on the build card.

Star Rail and Zenless Zone Zero ship these in the game data itself (the in-game relic recommendations and Fairy's
disc recommendations, the same lists HoYoLAB shows), read from Hakushin's copy of the game data. Genshin only has
them on HoYoLAB, so they are picked up from HoYoLAB's character details whenever the bot reads them.

Saved as {game: {character id: [stat names as the cards show them]}} in CACHE_DIR/effective_stats.json.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from .games import genshin as gi
from .games import starrail as sr
from .games import zenless as zz
from .models import CharacterBuild, Gear

log = logging.getLogger(__name__)

HAKUSHIN = "https://static.nanoka.cc"
MAX_AGE = 24 * 3600
# HoYoLAB's Genshin property types are the game's own fight property numbers.
GI_PROPS = {
    2: "FIGHT_PROP_HP", 3: "FIGHT_PROP_HP_PERCENT", 5: "FIGHT_PROP_ATTACK", 6: "FIGHT_PROP_ATTACK_PERCENT",
    8: "FIGHT_PROP_DEFENSE", 9: "FIGHT_PROP_DEFENSE_PERCENT", 20: "FIGHT_PROP_CRITICAL",
    22: "FIGHT_PROP_CRITICAL_HURT", 23: "FIGHT_PROP_CHARGE_EFFICIENCY", 28: "FIGHT_PROP_ELEMENT_MASTERY",
}


def _key(character_id) -> str:
    return str(character_id).split("-")[0]  # Genshin's Traveler ids carry their element ("10000007-704")


def hsr_names(props: list[str]) -> list[str]:
    return [sr.PROP_SHORT.get(p, p) for p in props]


def zzz_names(prop_ids: list[int]) -> list[str]:
    return [zz._prop_stat(int(p), 0).name for p in prop_ids]


def genshin_names(prop_types: list[int]) -> list[str]:
    return [gi._prop(GI_PROPS[int(t)], 0).name for t in prop_types if int(t) in GI_PROPS]


def genshin_recommended(item: dict) -> list[int] | None:
    """The recommended substat types in one character of HoYoLAB's raw Genshin character details, if it has them.

    HoYoLAB lists them as recommend_relic_property → recommend_properties → sub_property_list (the player's own
    custom picks sit next to them; only HoYoLAB's recommendation is used)."""
    rec = item.get("recommend_relic_property")
    if not isinstance(rec, dict):
        return None
    subs = (rec.get("recommend_properties") or {}).get("sub_property_list")
    return [int(t) for t in subs] if subs else None


class EffectiveStats:
    def __init__(self, cache_dir: str | Path):
        self.path = Path(cache_dir) / "effective_stats.json"
        self.table: dict[str, dict[str, list[str]]] = {"genshin": {}, "hsr": {}, "zzz": {}}
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

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps({**self.table, "updated": self.updated}, indent=1, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            log.exception("Could not save %s", self.path)

    def is_stale(self) -> bool:
        return time.time() - self.updated > MAX_AGE

    def wanted(self, build: CharacterBuild) -> set[str] | None:
        """The substats this character wants, or None if nobody has said yet."""
        names = self.table.get(build.game, {}).get(_key(build.character_id))
        return set(names) if names else None

    def learn(self, game: str, character_id, names: list[str]) -> None:
        if names and self.table[game].get(_key(character_id)) != names:
            self.table[game][_key(character_id)] = names
            self._save()

    def learn_genshin(self, raw: dict) -> None:
        """Picks up recommendations from HoYoLAB's raw Genshin character details."""
        for item in raw.get("list", []):
            types = genshin_recommended(item)
            if types:
                self.learn("genshin", (item.get("base") or item).get("id"), genshin_names(types))

    async def refresh(self, session) -> None:
        """Reads Star Rail's and ZZZ's recommendations from the live game data."""
        try:
            async with session.get(f"{HAKUSHIN}/manifest.json") as resp:
                resp.raise_for_status()
                manifest = await resp.json(content_type=None)
        except Exception:
            log.exception("Could not read Hakushin's manifest; keeping the saved effective stats")
            return
        sem = asyncio.Semaphore(8)

        async def get(path: str):
            async with sem:
                try:
                    async with session.get(f"{HAKUSHIN}/{path}") as resp:
                        if resp.status != 200:
                            return None
                        return await resp.json(content_type=None)
                except Exception:
                    return None

        for game, pick, names in (
            ("hsr", lambda d: (d.get("relics") or {}).get("sub_affix_property_list"), hsr_names),
            ("zzz", lambda d: (d.get("fairy_recommend") or {}).get("part_sub_list"), zzz_names),
        ):
            version = (manifest.get(game) or {}).get("live")
            index = await get(f"{game}/{version}/character.json") if version else None
            if not index:
                log.warning("No %s character list on Hakushin", game)
                continue
            ids = list(index)
            details = await asyncio.gather(*(get(f"{game}/{version}/en/character/{cid}.json") for cid in ids))
            for cid, detail in zip(ids, details):
                props = pick(detail) if isinstance(detail, dict) else None
                if props:
                    self.table[game][_key(cid)] = names(props)
        self.updated = time.time()
        self._save()
        log.info("Effective stats: %s", {g: len(t) for g, t in self.table.items()})


def piece_count(piece: Gear, wanted: set[str]) -> int:
    """Rolls that went into the substats the character wants, the first (base) roll included."""
    return sum(max(s.rolls, 1) for s in piece.subs if s.name in wanted)
