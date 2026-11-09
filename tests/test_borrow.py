"""What-if builds: one character wearing another's weapon and gear."""

from __future__ import annotations

import unittest

from bot import borrow
from bot.games import genshin, starrail, zenless
from tests.test_parsers import fixture, load_assets

GAMES = [("genshin", genshin, "genshin_live.json"), ("hsr", starrail, "hsr_live.json"), ("zzz", zenless, "zzz_live.json")]


def values(build):
    return [(s.name, s.value) for s in build.stats]


class BorrowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.profiles = {g: mod.parse_profile(cls.assets, "1", fixture(f)) for g, mod, f in GAMES}

    def test_own_gear_changes_nothing(self):
        for game, profile in self.profiles.items():
            for c in profile.characters:
                with self.subTest(game=game, character=c.name):
                    self.assertEqual(values(borrow.borrow(self.assets, c, c)), values(c))

    def test_wears_the_donors_gear(self):
        for game, profile in self.profiles.items():
            wearer, donor = profile.characters[:2]
            with self.subTest(game=game):
                b = borrow.borrow(self.assets, wearer, donor)
                self.assertEqual(b.name, wearer.name)
                self.assertEqual(b.level, wearer.level)
                self.assertEqual(b.constellation, wearer.constellation)
                self.assertEqual(b.weapon.name, donor.weapon.name)
                self.assertEqual([(g.slot, g.main.value) for g in b.gear], [(g.slot, g.main.value) for g in donor.gear])
                self.assertEqual(b.borrowed_from, donor.name)
                self.assertNotEqual(values(b), values(wearer))

    def test_round_trip(self):
        """Lending the gear back gives the wearer's own stats again (Genshin takes gear off finished stats)."""
        for game, profile in self.profiles.items():
            wearer, donor = profile.characters[:2]
            with self.subTest(game=game):
                there = borrow.borrow(self.assets, wearer, donor)
                back = borrow.borrow(self.assets, there, wearer)
                self.assertEqual(values(back), values(wearer))

    def test_genshin_totals(self):
        amber, bennett = self.profiles["genshin"].characters[:2]
        b = borrow.borrow(self.assets, amber, bennett)
        props = b.raw["fightPropMap"]
        self.assertAlmostEqual(props[genshin.ATK], props["4"] * (1 + props["6"]) + props["5"], places=3)
        # Amber's own base ATK stays; the weapon's base ATK is Bennett's
        weapon_base = lambda c: next(s["statValue"] for e in c.raw["equipList"] if "weapon" in e
                                     for s in e["flat"]["weaponStats"] if s["appendPropId"] == "FIGHT_PROP_BASE_ATTACK")
        own = float(amber.raw["fightPropMap"]["4"]) - weapon_base(amber)
        self.assertAlmostEqual(props["4"], own + weapon_base(bennett), places=2)

    def test_hoyolab_builds_cannot_borrow(self):
        c = self.profiles["hsr"].characters[0]
        self.assertTrue(borrow.can_borrow(c))
        c2 = starrail.parse_character(self.assets, c.raw)
        self.assertFalse(borrow.can_borrow(c2))


if __name__ == "__main__":
    unittest.main()
