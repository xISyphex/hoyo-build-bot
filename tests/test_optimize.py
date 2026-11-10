"""/hsr-optimize: the best pieces of two sets among the relics an account's characters wear."""

from __future__ import annotations

import unittest

from bot import optimize
from bot.games import starrail
from bot.hoyolab import _sr_promotion
from bot.main import optimize_text
from bot.models import Gear, Stat
from tests.test_parsers import fixture, load_assets

RELICS, PLANAR = "Scholar Lost in Erudition", "Rutilant Arena"


class OptimizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()

    def account(self, keep: int = 4):
        """The fixture's showcase, as if its first characters all wore the same two sets."""
        profile = starrail.parse_profile(self.assets, "1", fixture("hsr_live.json"))
        builds = [b for b in profile.characters if len(b.gear) == 6][:keep]
        for b in builds:
            for g in b.gear:
                g.set_name = PLANAR if g.slot in optimize.PLANAR_SLOTS else RELICS
        return builds

    def test_reads_a_relics_stats_back(self):
        piece = Gear("Body", RELICS, 15, 5, Stat("CRIT Rate", "32.4%"),
                     [Stat("SPD", "9.2"), Stat("HP", "1,143"), Stat("CRIT DMG", "6.5%"), Stat("ATK%", "4.3%")])
        props = optimize.gear_props(piece)
        self.assertAlmostEqual(props["CriticalChanceBase"], 0.324)
        self.assertAlmostEqual(props["SpeedDelta"], 9.2)
        self.assertAlmostEqual(props["HPDelta"], 1143)
        self.assertAlmostEqual(props["AttackAddedRatio"], 0.043)

    def test_set_lists(self):
        relics, planars = optimize.set_names(self.assets, False), optimize.set_names(self.assets, True)
        self.assertIn(RELICS, relics)
        self.assertIn(PLANAR, planars)
        self.assertFalse(set(relics) & set(planars))

    def test_best_combination(self):
        builds = self.account()
        target = builds[0]
        result = optimize.optimize(self.assets, target, builds, RELICS, PLANAR, {"CRIT Rate", "CRIT DMG", "HP%"})
        self.assertEqual([p.gear.slot for p in result.pieces], starrail.SLOT_ORDER)
        self.assertEqual(result.tried, 4 ** 6)
        self.assertEqual(result.build.set_bonuses, [f"4pc {RELICS}", f"2pc {PLANAR}"])
        self.assertTrue(result.build.optimized)
        self.assertEqual(result.build.name, target.name)
        # their own pieces are one of the combinations, so the best can't be worse
        self.assertGreaterEqual(result.index, result.current)
        # and nothing beats it: every single-piece swap is no better
        scorer = optimize.Scorer(self.assets, result.build.calc, {"CRIT Rate", "CRIT DMG", "HP%"})
        ids = optimize.set_ids(self.assets)
        sets = {ids[RELICS]: 4, ids[PLANAR]: 2}
        self.assertAlmostEqual(scorer.index([p.props for p in result.pieces], sets), result.index)
        for i, slot in enumerate(starrail.SLOT_ORDER):
            for other in optimize.pool(builds):
                if other.gear.slot == slot:
                    swapped = [*result.pieces[:i], other, *result.pieces[i + 1:]]
                    self.assertLessEqual(scorer.index([p.props for p in swapped], sets), result.index + 1e-9)
        text = optimize_text(result, target, RELICS, PLANAR)
        self.assertIn("Damage index", text)
        self.assertIn("Scored on HP, CRIT Rate, CRIT DMG", text)

    def test_set_effects_depend_on_the_build(self):
        """Rutilant Arena's DMG bonus needs 70% CRIT Rate."""
        calc = {"hp": 1000, "atk": 1000, "def": 500, "spd": 100, "element": "Ice", "bonus": {"CriticalDamageBase": 0.5}}
        scorer = optimize.Scorer(self.assets, calc, {"CRIT Rate", "CRIT DMG", "ATK%"})
        arena = {optimize.set_ids(self.assets)[PLANAR]: 2}
        low = scorer.index([{"CriticalChanceBase": 0.61}], arena)  # 69% with the set's own 8%
        high = scorer.index([{"CriticalChanceBase": 0.62}], arena)
        self.assertAlmostEqual(low, 1000 * (1 + 0.69 * 0.5))
        self.assertAlmostEqual(high, 1000 * 1.2 * (1 + 0.70 * 0.5))

    def test_scored_on_what_the_character_builds(self):
        calc = {"hp": 1000, "atk": 1000, "def": 500, "spd": 100, "element": "Fire", "bonus": {}}
        breaker = optimize.Scorer(self.assets, calc, {"Break Effect", "SPD", "ATK%"})
        self.assertEqual(breaker.counted(), ["ATK", "Fire DMG", "Break Effect", "SPD"])
        self.assertAlmostEqual(breaker.index([{"BreakDamageAddedRatioBase": 1.0, "SpeedDelta": 50, "CriticalChanceBase": 0.5}], {}),
                               1000 * 2.0 * 1.5)

    def test_missing_pieces(self):
        builds = self.account()
        with self.assertRaises(optimize.OptimizeError) as caught:
            optimize.optimize(self.assets, builds[0], builds, "Musketeer of Wild Wheat", PLANAR, None)
        self.assertIn("Head (Musketeer of Wild Wheat)", str(caught.exception))
        with self.assertRaises(optimize.OptimizeError):
            optimize.optimize(self.assets, builds[0], builds, PLANAR, PLANAR, None)  # a planar set as the relic set

    def test_promotion_from_level(self):
        self.assertEqual([_sr_promotion(n) for n in (1, 20, 21, 40, 41, 70, 71, 80)], [0, 0, 1, 2, 3, 5, 6, 6])


if __name__ == "__main__":
    unittest.main()
