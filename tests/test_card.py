"""The build card image (no network, no Discord)."""

from __future__ import annotations

import asyncio
import io
import tempfile
import unittest

from PIL import Image

from bot.card import H, W, CardMaker, crit_value, draw_card, server_name
from bot.embeds import card_embed
from bot.games import genshin, starrail, zenless
from test_parsers import fixture, load_assets


def _png(color=(200, 50, 50, 255), size=(300, 400)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", size, color).save(out, "PNG")
    return out.getvalue()


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
    def __init__(self, missing=()):
        self.missing, self.requested = set(missing), []

    def get(self, url, timeout=None):
        self.requested.append(url)
        return _Response(None if url in self.missing else _png())


class CardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assets = load_assets()
        cls.profiles = [
            genshin.parse_profile(assets, "618285856", fixture("genshin_live.json")),
            starrail.parse_profile(assets, "800069903", fixture("hsr_live.json")),
            zenless.parse_profile(assets, "1300003409", fixture("zzz_live.json")),
        ]

    def test_every_showcased_character_draws_without_pictures(self):
        for profile in self.profiles:
            for build in profile.characters:
                with self.subTest(game=profile.game, character=build.name):
                    png = draw_card(build, {})
                    self.assertEqual(Image.open(io.BytesIO(png)).size, (W, H))

    def test_art_and_weapon_pictures_are_known(self):
        for profile in self.profiles:
            build = profile.characters[0]
            self.assertTrue(build.art_url and build.art_url.startswith("https://"), profile.game)
            if build.weapon:
                self.assertTrue(build.weapon.icon_url.startswith("https://"), profile.game)

    def test_crit_value_counts_main_stats_and_substats(self):
        castorice = next(c for c in self.profiles[1].characters if c.name == "Castorice")
        self.assertAlmostEqual(crit_value(castorice), 153.7 + 64.8, places=1)  # subs + CRIT DMG body

    def test_server_from_uid(self):
        cases = [("genshin", "618285856", "America"), ("genshin", "700000001", "Europe"), ("hsr", "800069903", "Asia"),
                 ("hsr", "100000001", "China"), ("zzz", "1300003409", "Asia"), ("zzz", "1500000001", "Europe"),
                 ("zzz", "10000001", "China"), ("genshin", "1800000001", None)]
        for game, uid, server in cases:
            self.assertEqual(server_name(game, uid), server, (game, uid))

    def test_pictures_download_once_and_survive_a_restart(self):
        profile = self.profiles[1]
        build = profile.characters[0]
        with tempfile.TemporaryDirectory() as tmp:
            session = _Session(missing={build.weapon.icon_url})
            png = asyncio.run(CardMaker(session, tmp).render(profile, build))
            self.assertEqual(Image.open(io.BytesIO(png)).size, (W, H))
            fetched = len(session.requested)
            self.assertGreater(fetched, 1)
            # A new bot process reads the saved pictures; only the broken one is tried again.
            again = _Session(missing={build.weapon.icon_url})
            asyncio.run(CardMaker(again, tmp).render(profile, build))
            self.assertEqual(again.requested, [build.weapon.icon_url])

    def test_embed_shows_the_card_and_the_effect_only_when_asked(self):
        profile = self.profiles[1]
        build = next(c for c in profile.characters if c.weapon and c.weapon.effect)
        embed = card_embed(profile, build, "build.png")
        self.assertEqual(embed.image.url, "attachment://build.png")
        self.assertFalse(embed.fields)
        self.assertIsNone(embed.description)
        shown = card_embed(profile, build, "build.png", show_effect=True)
        self.assertIn(build.weapon.name, shown.description)
        self.assertLessEqual(len(shown), 6000)


if __name__ == "__main__":
    unittest.main()
