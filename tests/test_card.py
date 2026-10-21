"""The build card image (no network, no Discord)."""

from __future__ import annotations

import asyncio
import io
import tempfile
import unittest
from types import SimpleNamespace

from PIL import Image

from bot.card import H, W, CardMaker, crit_value, draw_card, gear_value, server_name
from bot.effective import EffectiveStats, hsr_names, piece_count, zzz_names
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

    def test_effective_substats(self):
        castorice = next(c for c in self.profiles[1].characters if c.name == "Castorice")
        wanted = set(hsr_names(["CriticalChanceBase", "CriticalDamageBase", "HPAddedRatio"]))
        self.assertEqual(wanted, {"CRIT Rate", "CRIT DMG", "HP%"})
        self.assertEqual(zzz_names([20103, 21103, 12102, 31203]), ["CRIT Rate", "CRIT DMG", "ATK%", "AP"])
        body = castorice.gear[2]
        expected = sum(max(s.rolls, 1) for s in body.subs if s.name in wanted)
        self.assertEqual(piece_count(body, wanted), expected)  # base rolls included
        png = draw_card(castorice, {}, wanted=wanted)
        self.assertEqual(Image.open(io.BytesIO(png)).size, (W, H))

    def test_supports_show_speed_value_instead_of_crit_value(self):
        sparkle = next(c for c in self.profiles[1].characters if c.name == "Sparkle")
        speed = sum(float(s.value) for p in sparkle.gear for s in [p.main, *p.subs] if s.name == "SPD")
        self.assertEqual(gear_value(sparkle, {"CRIT DMG", "SPD", "Effect RES"}), ("SPEED VALUE", f"{speed:.1f}"))
        self.assertEqual(gear_value(sparkle, {"CRIT Rate", "CRIT DMG", "SPD"})[0], "CRIT VALUE")
        self.assertEqual(gear_value(sparkle, None)[0], "CRIT VALUE")  # nothing known yet: as before

    def test_genshin_recommendations_come_from_hoyolab_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EffectiveStats(tmp)
            raw = {"list": [{"base": {"id": 10000089}, "recommend_relic_property": {
                "recommend_properties": {"sub_property_list": [20, 22, 3, 23]},
                "custom_properties": {"sub_property_list": [28]}}}]}
            store.learn_genshin(raw)
            build = SimpleNamespace(game="genshin", character_id="10000089")
            self.assertEqual(store.wanted(build), {"CRIT Rate", "CRIT DMG", "HP%", "ER"})
            self.assertEqual(EffectiveStats(tmp).wanted(build), {"CRIT Rate", "CRIT DMG", "HP%", "ER"})  # saved
            self.assertIsNone(store.wanted(SimpleNamespace(game="hsr", character_id="1001")))

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


    def test_reply_is_just_the_card_with_the_dropdown(self):
        import discord

        from bot.main import as_edit, render

        async def card(profile, build):
            return b"png"

        profile = self.profiles[1]
        bot = SimpleNamespace(cards=SimpleNamespace(render=card))
        reply = asyncio.run(render(bot, profile, profile.characters[0]))
        self.assertIsNone(reply["embed"])  # no embed around the image
        self.assertEqual(reply["file"].filename, "build.png")
        labels = [getattr(item, "label", None) for item in reply["view"].children]
        self.assertEqual(labels, [None, "Open on Enka.Network"])  # dropdown and link, no effect button
        self.assertIsInstance(reply["view"].children[0], discord.ui.Select)
        edit = as_edit(reply)
        self.assertIsNone(edit["embed"])
        self.assertEqual(len(edit["attachments"]), 1)


if __name__ == "__main__":
    unittest.main()


class MirrorUrlTest(unittest.TestCase):
    def test_enka_pictures_map_to_hakushin(self):
        from bot.card import mirror_url
        self.assertEqual(mirror_url("https://enka.network/ui/zzz/IconRole1641.png"),
                         "https://static.nanoka.cc/assets/zzz/IconRole1641.webp")
        self.assertEqual(mirror_url("https://enka.network/ui/UI_Gacha_AvatarImg_Furina.png"),
                         "https://static.nanoka.cc/assets/gi/UI_Gacha_AvatarImg_Furina.webp")
        self.assertIsNone(mirror_url("https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/x.png"))


class FaceTest(unittest.TestCase):
    def _figure(self):
        """A figure on a transparent picture with a patterned 'face' near its top."""
        import random as rnd
        rnd.seed(1)
        art = Image.new("RGBA", (500, 1000), (0, 0, 0, 0))
        art.paste((90, 90, 160, 255), (150, 100, 350, 1000))  # the body
        face = Image.new("RGBA", (120, 120))
        face.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255) for _ in range(120 * 120)])
        face = face.resize((120, 120))
        art.paste(face, (190, 140))
        return art, face

    def test_face_icon_is_found_in_the_picture(self):
        from bot import face as facemod
        if facemod.cv2 is None:
            self.skipTest("OpenCV not installed")
        art, icon = self._figure()
        x, y, size = facemod.find_face(art, icon)
        self.assertAlmostEqual(x, 250, delta=12)
        self.assertAlmostEqual(y, 200, delta=12)
        self.assertAlmostEqual(size, 120, delta=15)

    def test_without_an_icon_the_face_is_guessed_from_the_outline(self):
        from bot.face import EST_D, EST_Y, find_face
        art, _ = self._figure()
        x, y, size = find_face(art, None)
        self.assertAlmostEqual(x, 250, delta=5)
        self.assertAlmostEqual(y, 100 + EST_Y * 900, delta=2)
        self.assertAlmostEqual(size, EST_D * 900, delta=2)

    def test_zzz_card_draws_with_a_face(self):
        build = zenless.parse_profile(load_assets(), "1300003409", fixture("zzz_live.json")).characters[0]
        art, _ = self._figure()
        png = draw_card(build, {build.art_url: art}, face=(250, 200, 120))
        self.assertEqual(Image.open(io.BytesIO(png)).size, (W, H))


class MindscapeTest(unittest.TestCase):
    def test_next_picture_takes_over_a_third_per_copy(self):
        import dataclasses
        from bot.card import mindscape_urls
        build = zenless.parse_profile(load_assets(), "1300003409", fixture("zzz_live.json")).characters[0]
        got = {}
        for m in range(7):
            shown, upcoming, thirds = mindscape_urls(dataclasses.replace(build, constellation=m))
            got[m] = (shown[-5], upcoming[-5] if upcoming else None, thirds)
        self.assertEqual(got, {0: ("1", None, 0), 1: ("1", "2", 1), 2: ("1", "2", 2), 3: ("2", None, 0),
                               4: ("2", "3", 1), 5: ("2", "3", 2), 6: ("3", None, 0)})
        b = dataclasses.replace(build, constellation=4)
        shown, upcoming, _ = mindscape_urls(b)
        png = draw_card(b, {shown: Image.new("RGBA", (1920, 1080), (200, 50, 50, 255)),
                            upcoming: Image.new("RGBA", (1920, 1080), (50, 50, 200, 255))})
        card = Image.open(io.BytesIO(png)).convert("RGB")
        self.assertEqual(card.size, (W, H))
        top = 720 - 24 - 170  # the panel's top
        band, below = card.getpixel((24 + 176, top + 70)), card.getpixel((24 + 340, top + 160))
        self.assertGreater(band[2], band[0])  # M4: the diagonal band through the middle shows the next picture
        self.assertGreater(below[0], below[2])  # the rest: this one

    def test_other_games_have_none(self):
        from bot.card import mindscape_urls
        build = genshin.parse_profile(load_assets(), "618285856", fixture("genshin_live.json")).characters[0]
        self.assertEqual(mindscape_urls(build), (None, None, 0))


class FlameTest(unittest.TestCase):
    def test_flame_colour_climbs_with_the_mindscape(self):
        import dataclasses
        from bot.card import mindscape_urls
        build = zenless.parse_profile(load_assets(), "1300003409", fixture("zzz_live.json")).characters[0]
        picture = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        pixels = {}
        for m in (0, 1, 6):
            b = dataclasses.replace(build, constellation=m)
            card = Image.open(io.BytesIO(draw_card(b, {mindscape_urls(b)[0]: picture})))
            pixels[m] = card.convert("RGB").getpixel((200, 720 - 24 - 170 - 4))  # just above the picture's panel
        r0, g0, b0 = pixels[0]
        self.assertGreater(pixels[1][0], r0 + 20)  # M1: red
        self.assertGreater(pixels[6][2], b0 + 20)  # M6: blue
