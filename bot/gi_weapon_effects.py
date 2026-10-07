"""Genshin weapon passives, filled in for the weapon's refinement.

Enka's store has no passive text, so this reads theBowja/genshin-db: one small
JSON file per weapon with the passive written out for R1 to R5. Files are
fetched the first time a weapon is shown and kept on disk, so a lookup only
waits on the network for weapons the bot has never seen.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path

import aiohttp

from .models import PlayerProfile

log = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/theBowja/genshin-db/main/src/data/English/"
INDEX_URL = BASE_URL.replace("/English/", "/index/English/") + "weapons.json"
WEAPON_URL = BASE_URL + "weapons/{file}.json"

INDEX_MAX_AGE = 12 * 3600
WEAPON_MAX_AGE = 7 * 24 * 3600
MISSING_RETRY = 12 * 3600  # don't ask again for a weapon genshin-db doesn't have yet
TIMEOUT = aiohttp.ClientTimeout(total=8)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


class GenshinWeaponEffects:
    def __init__(self, session: aiohttp.ClientSession, cache_dir: str | Path):
        self.session = session
        self.dir = Path(cache_dir) / "gi" / "weapon_effects"
        self._index: dict[str, str] = {}
        self._index_loaded = 0.0
        self._weapons: dict[str, dict] = {}
        self._missing: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def fill(self, profile: PlayerProfile) -> None:
        """Set effect_name/effect on every weapon in the profile. Never raises."""
        weapons = [b.weapon for b in profile.characters if b.weapon]
        if not weapons:
            return
        async with self._lock:
            try:
                await self._load_index()
            except Exception:
                log.exception("Could not load the genshin-db weapon index")
            for weapon in weapons:
                try:
                    data = await self._weapon(weapon.name)
                except Exception:
                    log.exception("Could not load the passive for %s", weapon.name)
                    continue
                if not data or not data.get("effectName"):
                    continue
                refinement = data.get(f"r{min(max(weapon.refinement, 1), 5)}") or {}
                if refinement.get("description"):
                    weapon.effect_name = data["effectName"]
                    weapon.effect = refinement["description"].strip()

    async def _load_index(self) -> None:
        if self._index and time.time() - self._index_loaded < INDEX_MAX_AGE:
            return
        path = self.dir / "_index.json"
        names = None
        if path.exists() and time.time() - path.stat().st_mtime < INDEX_MAX_AGE:
            names = json.loads(path.read_text(encoding="utf-8"))
        else:
            body = await self._download(INDEX_URL)
            if body is not None:
                names = json.loads(body).get("names", {})
                self._write(path, json.dumps(names))
            elif path.exists():
                names = json.loads(path.read_text(encoding="utf-8"))  # stale beats nothing
        if names is not None:
            self._index = names
            self._index_loaded = time.time()

    async def _weapon(self, name: str) -> dict | None:
        file = self._index.get(name) or _slug(name)
        if file in self._weapons:
            return self._weapons[file]
        if time.time() - self._missing.get(file, 0) < MISSING_RETRY:
            return None
        path = self.dir / f"{file}.json"
        if path.exists() and time.time() - path.stat().st_mtime < WEAPON_MAX_AGE:
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            body = await self._download(WEAPON_URL.format(file=file))
            if body is None:
                if not path.exists():
                    self._missing[file] = time.time()
                    return None
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                full = json.loads(body)
                data = {k: full[k] for k in ("effectName", "r1", "r2", "r3", "r4", "r5") if k in full}
                self._write(path, json.dumps(data))
        self._weapons[file] = data
        return data

    async def _download(self, url: str) -> bytes | None:
        if self.session is None:  # tests: cache only
            return None
        try:
            async with self.session.get(url, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    log.info("genshin-db returned %s for %s", resp.status, url)
                    return None
                body = await resp.read()
            json.loads(body)  # never cache a broken file
            return body
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            log.warning("Could not download %s", url)
            return None

    def _write(self, path: Path, text: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError:
            log.warning("Could not cache %s", path)
