"""Game data (names, base stats, stat curves) published by Enka.Network.

The Enka API returns only IDs and raw numbers; these files turn them into names
and let us compute final stats. They are downloaded once, cached on disk and
refreshed periodically so new characters work without a redeploy.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

STORE_URL = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/"

FILES = {
    "gi_avatars": "gi/avatars.json",
    "gi_locs": "gi/locs.json",
    "gi_weapons": "gi/weapons.json",
    "gi_relics": "gi/relics.json",
    "gi_loc_legacy": "loc.json",
    "hsr_characters": "hsr/honker_characters.json",
    "hsr_weapons": "hsr/honker_weps.json",
    "hsr_relics": "hsr/honker_relics.json",
    "hsr_meta": "hsr/honker_meta.json",
    "hsr_skilltree": "hsr/honker_skilltree.json",
    "hsr_ranks": "hsr/honker_ranks.json",
    "hsr_locs": "hsr/hsr.json",
    "zzz_avatars": "zzz/avatars.json",
    "zzz_weapons": "zzz/weapons.json",
    "zzz_equipments": "zzz/equipments.json",
    "zzz_locs": "zzz/locs.json",
}

MAX_AGE = 12 * 3600

# W-Engine passives are not in Enka's store; Hakushin publishes them per W-Engine,
# already filled in for each phase. Only W-Engines not yet cached are downloaded.
HAKUSHIN_ZZZ = "https://api.hakush.in/zzz/data/"
ZZZ_EFFECTS = "zzz/weapon_effects.json"


class Assets:
    def __init__(self, cache_dir: str | Path, lang: str = "en"):
        self.cache_dir = Path(cache_dir)
        self.lang = lang
        self.data: dict[str, dict] = {}
        self._hsr_names: dict[float, str] = {}
        self._gi_names: dict[str, str] = {}

    def _path(self, key: str) -> Path:
        return self.cache_dir / FILES[key]

    def is_stale(self) -> bool:
        paths = [self._path(k) for k in FILES]
        if not all(p.exists() for p in paths):
            return True
        return time.time() - min(p.stat().st_mtime for p in paths) > MAX_AGE

    async def refresh(self, session) -> None:
        """Download every store file; keep the cached copy if a download fails."""
        for key, rel in FILES.items():
            try:
                async with session.get(STORE_URL + rel) as resp:
                    resp.raise_for_status()
                    body = await resp.read()
                json.loads(body)  # never cache a broken file
                path = self._path(key)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            except Exception:
                log.exception("Could not refresh %s, keeping cached copy", rel)
        await self._refresh_zzz_effects(session)
        self.load()

    async def _refresh_zzz_effects(self, session) -> None:
        path = self.cache_dir / ZZZ_EFFECTS
        effects = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        try:
            async with session.get(HAKUSHIN_ZZZ + "weapon.json") as resp:
                resp.raise_for_status()
                index = await resp.json(content_type=None)
        except Exception:
            log.exception("Could not list W-Engines on Hakushin, keeping cached effects")
            return
        for weapon_id in index:
            if weapon_id in effects:
                continue
            try:
                async with session.get(f"{HAKUSHIN_ZZZ}{self.lang}/weapon/{weapon_id}.json") as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
            except Exception:
                log.warning("Could not fetch W-Engine %s effect from Hakushin", weapon_id)
                continue
            talents = data.get("Talents") or {}
            effects[weapon_id] = {
                str(phase): {"Name": t.get("Name", ""), "Desc": t.get("Desc", "")}
                for phase, t in talents.items()
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(effects, ensure_ascii=False), encoding="utf-8")

    def load(self) -> None:
        for key in FILES:
            path = self._path(key)
            if path.exists():
                self.data[key] = json.loads(path.read_text(encoding="utf-8"))
            else:
                self.data[key] = {}
        effects = self.cache_dir / ZZZ_EFFECTS
        self.data["zzz_weapon_effects"] = (
            json.loads(effects.read_text(encoding="utf-8")) if effects.exists() else {}
        )
        self._build_indexes()

    def _build_indexes(self) -> None:
        legacy = self.data["gi_loc_legacy"].get(self.lang, {})
        current = self.data["gi_locs"].get(self.lang, {})
        self._gi_names = {**legacy, **current}

        # HSR name hashes are 64-bit, but the store's character/weapon files were
        # written by JavaScript and lost precision. Matching on the float value
        # of both sides lines them up again.
        self._hsr_names = {}
        for key, text in self.data["hsr_locs"].get(self.lang, {}).items():
            if key.isdigit():
                self._hsr_names[float(int(key))] = text

    # ---- name lookups -------------------------------------------------

    def gi_text(self, key) -> str | None:
        return self._gi_names.get(str(key))

    def hsr_text(self, key) -> str | None:
        if key is None:
            return None
        if isinstance(key, str) and not key.lstrip("-").isdigit():
            return self.data["hsr_locs"].get(self.lang, {}).get(key)
        return self._hsr_names.get(float(int(key)))

    def zzz_text(self, key) -> str | None:
        return self.data["zzz_locs"].get(self.lang, {}).get(key)

    # ---- character name lists (autocomplete / fuzzy matching) --------

    def character_names(self, game: str) -> list[str]:
        names: set[str] = set()
        if game == "genshin":
            for info in self.data["gi_avatars"].values():
                name = self.gi_text(info.get("NameTextMapHash"))
                if name:
                    names.add(name)
        elif game == "hsr":
            for info in self.data["hsr_characters"].values():
                name = self.hsr_text(info.get("AvatarName", {}).get("Hash"))
                if name:
                    names.add(name)
        elif game == "zzz":
            for info in self.data["zzz_avatars"].values():
                name = self.zzz_text(info.get("Name"))
                if name:
                    names.add(name)
        return sorted(names)
