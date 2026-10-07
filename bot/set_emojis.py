"""Gear piece pictures as Discord emojis, so they can stand in for the slot names.

Embed text can't hold images, but it can hold emojis. The bot uploads each
picture once as an application emoji (owned by the bot, usable in every server,
up to 2,000 of them) and reuses it from then on.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

import aiohttp
import discord

from .models import CharacterBuild

log = logging.getLogger("hoyo-bot")

MAX_BYTES = 256 * 1024  # Discord's emoji size limit


def emoji_name(game: str, url: str) -> str:
    # Letters, digits and underscores, at most 32 characters, stable for the same image.
    return f"{game}_{hashlib.sha1(url.encode()).hexdigest()[:16]}"


class SetEmojis:
    def __init__(self, client: discord.Client, session: aiohttp.ClientSession):
        self.client = client
        self.session = session
        self.emojis: dict[str, str] = {}  # emoji name -> "<:name:id>"
        self.failed: set[str] = set()  # don't retry a broken image on every lookup
        self.lock = asyncio.Lock()
        self.loaded = False

    async def _load(self) -> None:
        """Pick up the emojis uploaded before the last restart (once, on first use)."""
        self.loaded = True
        try:
            for emoji in await self.client.fetch_application_emojis():
                self.emojis[emoji.name] = str(emoji)
        except Exception:
            log.exception("Could not list the bot's emojis; pictures will be uploaded as needed")

    async def for_pieces(self, build: CharacterBuild) -> dict[str, str]:
        """Image URL -> emoji for each equipped piece's own picture."""
        result = {}
        for piece in build.gear:
            if piece.piece_icon and piece.piece_icon not in result:
                emoji = await self._get(build.game, piece.piece_icon)
                if emoji:
                    result[piece.piece_icon] = emoji
        return result

    async def _get(self, game: str, url: str) -> str | None:
        name = emoji_name(game, url)
        if name in self.emojis or name in self.failed:
            return self.emojis.get(name)
        async with self.lock:  # two lookups of the same piece must not upload it twice
            if not self.loaded:
                await self._load()
            if name in self.emojis or name in self.failed:
                return self.emojis.get(name)
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    image = await resp.read()
                if len(image) > MAX_BYTES:
                    raise ValueError(f"image is {len(image)} bytes")
                emoji = await self.client.create_application_emoji(name=name, image=image)
            except Exception:
                log.exception("Could not make an emoji for image %s", url)
                self.failed.add(name)
                return None
            self.emojis[name] = str(emoji)
            return self.emojis[name]
