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


def _panel_box() -> tuple[int, int, int, int]:
    """The Mindscape picture's panel on the ZZZ card: x, y, width, height."""
    from bot.card import ART_W
    x = 24  # the picture runs under the stub too
    return x, 720 - 24 - 150, ART_W - 6 - x, 150


def _in_panel(fx: float, fy: float) -> tuple[int, int]:
    x, y, w, h = _panel_box()
    return round(x + fx * w), round(y + fy * h)


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
        b = dataclasses.replace(build, constellation=4, character_id="9999")  # no known face: the V opens at the left
        shown, upcoming, _ = mindscape_urls(b)
        png = draw_card(b, {shown: Image.new("RGBA", (1920, 1080), (200, 50, 50, 255)),
                            upcoming: Image.new("RGBA", (1920, 1080), (50, 50, 200, 255))})
        card = Image.open(io.BytesIO(png)).convert("RGB")
        self.assertEqual(card.size, (W, H))
        band, below = card.getpixel(_in_panel(0.2, 0.7)), card.getpixel(_in_panel(0.9, 0.9))
        self.assertGreater(band[2], band[0])  # M4: the diagonal band through the middle shows the next picture
        self.assertGreater(below[0], below[2])  # the rest: this one

    def test_background_black_for_m3_white_for_m6(self):
        import dataclasses
        from bot.card import mindscape_urls
        build = zenless.parse_profile(load_assets(), "1300003409", fixture("zzz_live.json")).characters[0]
        clear = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))  # a fully see-through picture shows the background
        for m, want in ((3, (0, 0, 0)), (6, (255, 255, 255))):
            b = dataclasses.replace(build, constellation=m)
            shown, _, _ = mindscape_urls(b)
            card = Image.open(io.BytesIO(draw_card(b, {shown: clear}))).convert("RGB")
            self.assertEqual(card.getpixel(_in_panel(0.5, 0.5)), want)
        b = dataclasses.replace(build, constellation=4, character_id="9999")  # the unlocked band shows the M6 picture's white
        shown, upcoming, _ = mindscape_urls(b)
        card = Image.open(io.BytesIO(draw_card(b, {shown: clear, upcoming: clear}))).convert("RGB")
        self.assertEqual(card.getpixel(_in_panel(0.2, 0.7)), (255, 255, 255))
        self.assertEqual(card.getpixel(_in_panel(0.9, 0.9)), (0, 0, 0))

    def test_first_slice_opens_on_the_face(self):
        import dataclasses
        from bot.card import MINDSCAPE_FACES, mindscape_urls
        build = zenless.parse_profile(load_assets(), "1300003409", fixture("zzz_live.json")).characters[0]
        x0, y0, w, h = _panel_box()
        for cid in (1191, 1201):  # face at the right, face at the left
            b = dataclasses.replace(build, constellation=4, character_id=str(cid))
            shown, upcoming, _ = mindscape_urls(b)
            # a picture drawn all over (so it isn't zoomed) and see-through next one showing its white background
            card = Image.open(io.BytesIO(draw_card(b, {shown: Image.new("RGBA", (1920, 1080), (90, 0, 0, 255)),
                                                       upcoming: Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))})))
            scale = max(w / 1920, h / 1080)
            fx, fy = MINDSCAPE_FACES[cid]
            px = round(fx * 1920 * scale - (1920 * scale - w) / 2)
            py = round(fy * 1080 * scale - (1080 * scale - h) / 2)
            self.assertEqual(card.convert("RGB").getpixel((x0 + px, y0 + py)), (255, 255, 255), cid)

    def test_drawn_part_fills_the_panel(self):
        from bot.card import _mindscape_panel
        card = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        pic = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        pic.paste((200, 50, 50, 255), (0, 300, 1100, 1080))  # see-through on the right and at the top
        _mindscape_panel(card, pic, (30, 520, 400, 670), 3)  # the picture part starts after the 40px stub
        for x, y in ((80, 530), (390, 530), (390, 660)):  # the drawn part is zoomed to reach every corner
            self.assertEqual(card.getpixel((x, y))[:3], (200, 50, 50))

    def test_other_games_have_none(self):
        from bot.card import mindscape_urls
        build = genshin.parse_profile(load_assets(), "618285856", fixture("genshin_live.json")).characters[0]
        self.assertEqual(mindscape_urls(build), (None, None, 0))


class MindscapeTabTest(unittest.TestCase):
    def test_unlocked_levels_lit_in_the_highest_ones_colour(self):
        import dataclasses
        from bot.card import MINDSCAPE_COLORS, TAB_W
        build = zenless.parse_profile(load_assets(), "1300003409", fixture("zzz_live.json")).characters[0]
        card = Image.open(io.BytesIO(draw_card(dataclasses.replace(build, constellation=3), {}))).convert("RGB")
        top, row = 720 - 24 - 150, 150 / 6

        def colours(n):  # the colours in the M{n} label's row
            y = round(top + row * (n - 0.5))
            return {card.getpixel((x, yy)) for x in range(24, 24 + TAB_W) for yy in range(y - 6, y + 6)}

        for n in (1, 2, 3):
            self.assertIn(MINDSCAPE_COLORS[3], colours(n))  # M1-M3 all in M3's yellow
        self.assertNotIn(MINDSCAPE_COLORS[1], colours(1))
        self.assertNotIn(MINDSCAPE_COLORS[3], colours(4))  # M4 still dim

