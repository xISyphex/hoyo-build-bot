"""Gear piece pictures shown as emojis (no network, no Discord)."""

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

    def test_uploads_each_picture_once_and_reuses_old_uploads(self):
        woodpecker = "https://enka.network/ui/zzz/SuitWoodpeckerElectro.png"
        old = _Emoji(emoji_name("zzz", woodpecker), 7)
        client, session = _Client([old]), _Session()
        emojis = SetEmojis(client, session)
        first = asyncio.run(emojis.for_pieces(self.anby))
        again = asyncio.run(emojis.for_pieces(self.anby))
        self.assertEqual(first, again)
        self.assertEqual(first[woodpecker], "<:%s:7>" % old.name)
        self.assertEqual(len(client.created), 1)  # only the new picture, and only once
        self.assertEqual(session.requested, ["https://enka.network/ui/zzz/SuitShockstarDisco.png"])

    def test_missing_picture_keeps_the_slot_name(self):
        session = _Session(missing="https://enka.network/ui/zzz/SuitShockstarDisco.png")
        emojis = asyncio.run(SetEmojis(_Client(), session).for_pieces(self.anby))
        names = [f.name for f in build_embed(self.profile, self.anby, piece_emojis=emojis).fields if f.inline][3:]
        self.assertTrue(names[0].startswith("Disc 1"), names)
        self.assertTrue(names[-1].startswith("<:zzz_"), names)

    def test_piece_pictures_replace_slot_names(self):
        from bot.games import starrail

        hsr = starrail.parse_profile(self.assets, "800069903", fixture("hsr_live.json"))
        castorice = hsr.characters[0]
        pieces = asyncio.run(SetEmojis(_Client(), _Session()).for_pieces(castorice))
        self.assertEqual(len(pieces), 6)  # one picture per relic
        names = [f.name for f in build_embed(hsr, castorice, piece_emojis=pieces).fields if f.inline][3:]
        self.assertTrue(all(n.startswith("<:hsr_") and n.endswith(">") for n in names), names)
        # Drive discs all show their set's picture, so the disc number stays.
        discs = asyncio.run(SetEmojis(_Client(), _Session()).for_pieces(self.anby))
        names = [f.name for f in build_embed(self.profile, self.anby, piece_emojis=discs).fields if f.inline][3:]
        self.assertTrue(names[0].startswith("<:zzz_") and " Disc 1" in names[0], names)
        # Without pictures the slot names stay.
        self.assertEqual([f.name for f in build_embed(hsr, castorice).fields if f.inline][3], "Head")


if __name__ == "__main__":
    unittest.main()
