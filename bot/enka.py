"""Small Enka.Network client with a per-UID cache that honours the API's ttl."""

from __future__ import annotations

import asyncio
import time

import aiohttp

from .assets import Assets
from .games import genshin, starrail, zenless
from .models import PlayerProfile

API = "https://enka.network/api/"
ENDPOINTS = {
    "genshin": "uid/{uid}",
    "hsr": "hsr/uid/{uid}",
    "zzz": "zzz/uid/{uid}",
}
PARSERS = {
    "genshin": genshin.parse_profile,
    "hsr": starrail.parse_profile,
    "zzz": zenless.parse_profile,
}
ERRORS = {
    400: "That UID doesn't look right. Check it and try again.",
    404: "No player with that UID exists.",
    424: "The game is under maintenance or just updated. Try again later.",
    429: "Enka.Network is rate-limiting requests right now. Try again in a minute.",
    500: "Enka.Network had a server error. Try again later.",
    503: "Enka.Network is down right now. Try again later.",
}


class EnkaError(Exception):
    """Raised with a message that is safe to show to Discord users."""


class EnkaClient:
    def __init__(self, session: aiohttp.ClientSession, assets: Assets):
        self.session = session
        self.assets = assets
        self._cache: dict[tuple[str, str], tuple[float, PlayerProfile]] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def fetch(self, game: str, uid: str) -> PlayerProfile:
        key = (game, uid)
        cached = self._cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        # One request per UID at a time: autocomplete and the command itself
        # often ask for the same profile within the same second.
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            data = await self._get(ENDPOINTS[game].format(uid=uid))
            profile = PARSERS[game](self.assets, uid, data)
            self._cache[key] = (time.monotonic() + max(profile.ttl, 30), profile)
            self._prune()
            return profile

    def cached(self, game: str, uid: str) -> PlayerProfile | None:
        entry = self._cache.get((game, uid))
        return entry[1] if entry else None

    async def _get(self, path: str) -> dict:
        try:
            async with self.session.get(API + path, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise EnkaError(ERRORS.get(resp.status, f"Enka.Network returned an error ({resp.status})."))
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise EnkaError("Couldn't reach Enka.Network. Try again in a moment.") from exc

    def _prune(self) -> None:
        now = time.monotonic()
        for key in [k for k, (expires, _) in self._cache.items() if expires < now]:
            self._cache.pop(key, None)
            self._locks.pop(key, None)
