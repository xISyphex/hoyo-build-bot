"""What-if builds: one character wearing another's weapon and gear."""

from __future__ import annotations

import dataclasses
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

    def built(self, c):
        """The character fully built, as what-if builds show Star Rail and ZZZ characters (Genshin stays as it is)."""
        if c.game == "hsr":
            return starrail.parse_character(self.assets, starrail.maxed(self.assets, c.raw))
        if c.game == "zzz":
            return zenless.parse_character(self.assets, zenless.maxed(c.raw))
        return c

    def test_fully_built(self):
        jingliu = next(c for c in self.profiles["hsr"].characters if c.name == "Jingliu")
        info = {**jingliu.raw, "level": 60, "promotion": 4, "skillTreeList": jingliu.raw["skillTreeList"][:3]}
        low = starrail.parse_character(self.assets, info)
        top = starrail.parse_character(self.assets, starrail.maxed(self.assets, info))
        self.assertEqual((low.level, top.level), (60, 80))
        self.assertEqual([t.value for t in top.talents][:4], ["6", "10", "10", "10"])
        self.assertEqual(values(top), values(self.built(jingliu)))  # the same as the real, maxed one
        anby = self.profiles["zzz"].characters[0]
        top = self.built(anby)
        self.assertEqual((anby.level, top.level, top.talents[-1].value), (50, 60, "F"))

    def test_own_gear_changes_nothing(self):
        for game, profile in self.profiles.items():
            for c in profile.characters:
                with self.subTest(game=game, character=c.name):
                    self.assertEqual(values(borrow.borrow(self.assets, c, c)), values(self.built(c)))

    def test_wears_the_donors_gear(self):
        for game, profile in self.profiles.items():
            wearer, donor = profile.characters[:2]
            with self.subTest(game=game):
                b = borrow.borrow(self.assets, wearer, donor)
                self.assertEqual(b.name, wearer.name)
                self.assertEqual(b.level, {"genshin": wearer.level, "hsr": 80, "zzz": 60}[game])
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
                self.assertEqual(values(back), values(self.built(wearer)))

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


class HoyolabBorrowTest(unittest.TestCase):
    """Star Rail characters that only HoYoLAB lists have no showcase entry: their gear is read from the card lines."""

    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()

    def setUp(self):
        self.wearer, self.donor = starrail.parse_profile(self.assets, "1", fixture("hsr_live.json")).characters[3:5]

    @staticmethod
    def as_hoyolab(build):
        """The same character as HoYoLAB hands it over: no showcase entry, a relic-less one to compute from."""
        build.bare = {k: v for k, v in build.raw.items() if k != "relicList"}
        build.raw = {}
        build.source = "hoyolab"
        return build

    def numbers(self, build):
        return {s.name: float(s.value.replace(",", "").rstrip("%")) for s in build.stats}

    def test_matches_the_showcase_swap(self):
        exact = self.numbers(borrow.borrow(self.assets, self.wearer, self.donor))
        for who in ("donor", "wearer", "both"):
            with self.subTest(hoyolab=who):
                w, d = self.wearer, self.donor
                if who in ("donor", "both"):
                    d = self.as_hoyolab(dataclasses.replace(d))
                if who in ("wearer", "both"):
                    w = self.as_hoyolab(dataclasses.replace(w))
                self.assertTrue(borrow.can_borrow(w) and borrow.can_borrow(d))
                got = borrow.borrow(self.assets, w, d)
                self.assertEqual((got.name, got.borrowed_from, got.source), (w.name, d.name, w.source))
                self.assertEqual(got.weapon.name if got.weapon else None, d.weapon.name if d.weapon else None)
                self.assertEqual(got.set_bonuses, d.set_bonuses)
                close = self.numbers(got)
                self.assertEqual(close.keys(), exact.keys())
                for name, value in exact.items():  # card lines are rounded to a decimal
                    self.assertAlmostEqual(close[name], value, delta=max(2.0, value * 0.002), msg=name)
                self.assertTrue(borrow.can_borrow(got))  # the dropdown can lend the same gear on

    def test_hidden_relic_stats_cannot_be_lent(self):
        d = self.as_hoyolab(self.donor)
        for g in d.gear:
            g.subs = []
        self.assertFalse(borrow.can_borrow(d))
