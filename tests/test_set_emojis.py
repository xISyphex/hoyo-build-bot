"""Set images shown as emojis in front of the set bonuses (no network, no Discord)."""

from __future__ import annotations

import asyncio
import unittest

from bot.embeds import build_embed
from bot.games import zenless
from bot.set_emojis import SetEmojis, emoji_name
from test_parsers import fixture, load_assets


class _Response:
    def __init__(self, body: bytes | None):
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.body is None:
            raise RuntimeError("HTTP 404")

    async def read(self):
        return self.body


class _Session:
    def __init__(self, missing: str = ""):
        self.missing, self.requested = missing, []

    def get(self, url, timeout=None):
        self.requested.append(url)
        return _Response(None if url == self.missing else b"png")


class _Emoji:
    def __init__(self, name: str, id_: int):
        self.name, self.id = name, id_

    def __str__(self):
        return f"<:{self.name}:{self.id}>"


class _Client:
    def __init__(self, existing=()):
        self.existing, self.created = list(existing), []

    async def fetch_application_emojis(self):
        return self.existing

    async def create_application_emoji(self, *, name, image):
        self.created.append(name)
        return _Emoji(name, 100 + len(self.created))


class SetEmojiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()

    def setUp(self):
        self.profile = zenless.parse_profile(self.assets, "1300003409", fixture("zzz_live.json"))
        self.anby = self.profile.characters[0]  # 4pc Shockstar Disco, 2pc Woodpecker Electro

    def test_uploads_each_set_once_and_reuses_old_uploads(self):
        woodpecker = "https://enka.network/ui/zzz/SuitWoodpeckerElectro.png"
        old = _Emoji(emoji_name("zzz", woodpecker), 7)
        client, session = _Client([old]), _Session()
        emojis = SetEmojis(client, session)
        first = asyncio.run(emojis.for_build(self.anby))
        again = asyncio.run(emojis.for_build(self.anby))
        self.assertEqual(first, again)
        self.assertEqual(first["Woodpecker Electro"], "<:%s:7>" % old.name)
        self.assertTrue(first["Shockstar Disco"].startswith("<:zzz_"))
        self.assertEqual(len(client.created), 1)  # only the new set, and only once
        self.assertEqual(session.requested, ["https://enka.network/ui/zzz/SuitShockstarDisco.png"])

    def test_missing_image_falls_back_to_a_dot(self):
        session = _Session(missing="https://enka.network/ui/zzz/SuitShockstarDisco.png")
        emojis = asyncio.run(SetEmojis(_Client(), session).for_build(self.anby))
        self.assertNotIn("Shockstar Disco", emojis)
        sets = build_embed(self.profile, self.anby, set_emojis=emojis).fields[-1]
        self.assertEqual(sets.name, "Drive Discs")
        lines = sets.value.splitlines()
        self.assertEqual(lines[0], "• 4pc Shockstar Disco")
        self.assertTrue(lines[1].startswith("<:zzz_") and lines[1].endswith(" 2pc Woodpecker Electro"))


if __name__ == "__main__":
    unittest.main()
