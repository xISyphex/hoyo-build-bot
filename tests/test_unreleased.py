"""Unreleased characters: beta data in Hakushin's shapes, read like a showcase entry (the fixture is made up)."""

from __future__ import annotations

import tempfile
import unittest

from bot import borrow, matching
from bot.games import genshin, starrail, zenless
from bot.main import borrowed_line
from bot.unreleased import CONVERT, Unreleased
from tests.test_parsers import fixture, load_assets

LIVE = {"genshin": (genshin, "genshin_live.json"), "hsr": (starrail, "hsr_live.json"), "zzz": (zenless, "zzz_live.json")}
NAMES = {"genshin": "Beta Knight", "hsr": "Beta · Tester", "zzz": "Beta Agent"}


def stats(build) -> dict[str, str]:
    return {s.name: s.value for s in build.stats}


class UnreleasedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.dir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.dir.cleanup)
        cls.beta = Unreleased(cls.dir.name)
        pages = fixture("beta_characters.json")
        cls.beta.saved = {game: {"9901": CONVERT[game]("9901", page)} for game, page in pages.items()}
        cls.assets.extras.append(cls.beta.apply)
        cls.assets.load()

    @classmethod
    def tearDownClass(cls):
        cls.assets.extras.clear()

    def test_names_are_suggested_and_found(self):
        for game, name in NAMES.items():
            with self.subTest(game=game):
                self.assertEqual(self.beta.names(game), [name])
                self.assertIn(name, self.assets.character_names(game))
        self.assertEqual(matching.find("tester", self.assets.character_names("hsr")), "Beta · Tester")

    def test_survives_reading_the_game_data_again(self):
        self.assets.load()
        self.beta.apply(self.assets)  # and a second apply on top of its own entries
        self.assertEqual(self.beta.names("zzz"), ["Beta Agent"])

    def test_bare_builds(self):
        hsr = self.beta.build(self.assets, "hsr", "Beta · Tester")
        self.assertEqual((hsr.level, hsr.rarity, hsr.element, hsr.constellation, hsr.source), (80, 5, "Ice", 0, "beta"))
        self.assertEqual(stats(hsr)["ATK"], "747")  # 345.576 + 5.082 x 79
        self.assertEqual(stats(hsr)["CRIT Rate"], "17.0%")  # 5% and the trace nodes
        self.assertEqual([t.value for t in hsr.talents], ["6", "10", "10", "10"])
        self.assertTrue(hsr.art_url.endswith("avatardrawcard/9901.webp"))
        self.assertEqual(len(hsr.cons_icons), 6)

        zzz = self.beta.build(self.assets, "zzz", "Beta Agent")
        self.assertEqual((zzz.level, zzz.rarity, zzz.element), (60, 4, "Electric"))
        self.assertEqual(stats(zzz)["CRIT Rate"], "33.8%")  # 5% and the core skill's 28.8%
        self.assertEqual(zzz.talents[-1].value, "F")

        gi = self.beta.build(self.assets, "genshin", "Beta Knight")
        self.assertEqual((gi.level, gi.rarity, gi.element), (90, 5, "Electro"))
        self.assertEqual(stats(gi)["CRIT DMG"], "88.4%")  # 50% and the ascension stat
        self.assertEqual(gi.art_url, "https://enka.network/ui/UI_Gacha_AvatarImg_Beta.png")
        self.assertIn("isn't released yet", borrowed_line(gi))

    def test_wears_a_showcase_characters_gear(self):
        for game, (module, name) in LIVE.items():
            with self.subTest(game=game):
                donor = module.parse_profile(self.assets, "1", fixture(name)).characters[0]
                bare = self.beta.build(self.assets, game, NAMES[game])
                worn = borrow.borrow(self.assets, bare, donor)
                self.assertEqual((worn.name, worn.source, worn.borrowed_from), (NAMES[game], "beta", donor.name))
                self.assertEqual(worn.weapon.name, donor.weapon.name)
                self.assertEqual(len(worn.gear), len(donor.gear))
                self.assertNotEqual(stats(worn), stats(bare))
                self.assertIn("isn't released yet", borrowed_line(worn))

    def test_released_characters_use_the_store(self):
        """Once Enka's store knows the character, the beta entry is dropped."""
        self.assets.load()
        store = self.assets.data["zzz_avatars"]
        store["9901"] = {"Name": "Avatar_Real"}
        self.beta.apply(self.assets)
        self.assertEqual(self.beta.names("zzz"), [])
        self.assertEqual(store["9901"], {"Name": "Avatar_Real"})
        self.assets.load()


if __name__ == "__main__":
    unittest.main()
