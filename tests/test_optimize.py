"""/hsr-optimize: the best pieces of two sets among the relics an account's characters wear."""

from __future__ import annotations

import unittest

from bot import cone_effects, optimize
from bot.games import starrail
from bot.hoyolab import _sr_promotion
from bot.main import optimize_text
from bot.models import Gear, Stat
from tests.test_parsers import fixture, load_assets

RELICS, PLANAR = "Scholar Lost in Erudition", "Rutilant Arena"
SLOW = optimize.turns(100)  # what 100 SPD is worth
DEF = 100 / (115 + 100)  # the DEF multiplier of a Lv. 95 enemy against a Lv. 80 character


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

    def bare_bonus(self, build) -> dict:
        """The character's own bonuses, without the relics the optimized build's stats were made with."""
        return starrail.parse_character(self.assets, {**{k: v for k, v in build.raw.items() if k != "relicList"}}).calc["bonus"] \
            if build.raw else build.calc["bonus"]

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
        self.assertEqual(result.tried, 4 ** 6 * result.cones)
        self.assertEqual(result.build.set_bonuses, [f"4pc {RELICS}", f"2pc {PLANAR}"])
        self.assertTrue(result.build.optimized)
        self.assertEqual(result.build.name, target.name)
        # their own pieces are one of the combinations, so the best can't be worse
        self.assertGreaterEqual(result.index, result.current)
        self.assertEqual(result.build.score, result.index)  # drawn on the card, with the gain
        self.assertAlmostEqual(result.build.score_gain, (result.index / result.current - 1) * 100)
        # and nothing beats it: every single-piece swap is no better
        scorer = optimize.Scorer(self.assets, {**result.build.calc, "bonus": self.bare_bonus(result.build)},
                                 {"CRIT Rate", "CRIT DMG", "HP%"}, cone=result.cone_effect)
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
        self.assertIn("Scored on HP, ", text)

    def test_set_effects_depend_on_the_build(self):
        """Rutilant Arena's DMG bonus needs 70% CRIT Rate."""
        calc = {"hp": 1000, "atk": 1000, "def": 500, "spd": 100, "element": "Ice", "bonus": {"CriticalDamageBase": 0.5}}
        scorer = optimize.Scorer(self.assets, calc, {"CRIT Rate", "CRIT DMG", "ATK%"})
        arena = {optimize.set_ids(self.assets)[PLANAR]: 2}
        low = scorer.index([{"CriticalChanceBase": 0.61}], arena)  # 69% with the set's own 8%
        high = scorer.index([{"CriticalChanceBase": 0.62}], arena)
        self.assertAlmostEqual(low, 1000 * (1 + 0.69 * 0.5) * DEF)
        self.assertAlmostEqual(high, 1000 * 1.2 * (1 + 0.70 * 0.5) * DEF)

    def test_scored_on_what_the_character_builds(self):
        calc = {"hp": 1000, "atk": 1000, "def": 500, "spd": 100, "element": "Fire", "bonus": {}}
        breaker = optimize.Scorer(self.assets, calc, {"Break Effect", "SPD", "ATK%"})
        self.assertEqual(breaker.counted(), ["ATK", "Fire DMG", "Break Effect", "SPD"])
        self.assertAlmostEqual(breaker.index([{"BreakDamageAddedRatioBase": 1.0, "SpeedDelta": 50, "CriticalChanceBase": 0.5}], {}),
                               1000 * 2.0 * optimize.turns(150) * DEF)

    def test_speed_pays_at_the_breakpoints(self):
        """Memory of Chaos: 134 SPD takes a second turn in the first cycle, 133 doesn't; 160 takes four turns in two."""
        self.assertEqual(optimize.turns(128), optimize.turns(133))
        self.assertGreater(optimize.turns(134), optimize.turns(133) * 1.1)
        self.assertEqual(optimize.turns(135), optimize.turns(142))
        self.assertGreater(optimize.turns(160), optimize.turns(159))
        self.assertAlmostEqual(optimize.turns(200), 2.0)

    def test_speed_can_be_switched(self):
        self.assertEqual(optimize.with_speed({"CRIT Rate", "SPD"}, None), {"CRIT Rate", "SPD"})
        self.assertEqual(optimize.with_speed({"CRIT Rate", "SPD"}, False), {"CRIT Rate"})
        self.assertEqual(optimize.with_speed({"CRIT Rate"}, True), {"CRIT Rate", "SPD"})
        self.assertNotIn("SPD", optimize.with_speed(None, False))  # a character the game recommends nothing for
        calc = {"hp": 1000, "atk": 1000, "def": 500, "spd": 100, "element": "Ice", "bonus": {}}
        off = optimize.Scorer(self.assets, calc, optimize.with_speed({"ATK%", "SPD"}, False))
        self.assertEqual(off.index([{"SpeedDelta": 60}], {}), off.index([{}], {}))
        self.assertNotIn("SPD", off.counted())

    def test_light_cone_passives(self):
        parse = cone_effects.parse
        self.assertEqual(parse("Increases the wearer's ATK by #1[i]%. After the wearer uses Skill, increases ATK by #2[i]%, "
                               "stacking up to #3[i] times.", [0.16, 0.08, 3], {"AttackAddedRatio": 0.16}),
                         {"AttackAddedRatio": 0.24})  # the 16% is in the light cone's own stats already
        self.assertEqual(parse("Gains 1 stack of Eclipse, up to a max of #2[i] stack(s). Each stack of Eclipse increases the "
                               "DMG of the wearer's next attack by #3[f1]%. When #2[i] stack(s) are reached, additionally "
                               "enables that attack to ignore #4[i]% of the enemy's DEF.", [0.2, 3, 0.14, 0.12]),
                         {"DMG": 0.42, "DefIgnore": 0.12})
        self.assertEqual(parse("The wearer deals #1[i]% more CRIT DMG to Slowed enemies. Enemies take #2[i]% increased DMG.",
                               [0.24, 0.1]), {"CriticalDamageBase": 0.24, "Vulnerability": 0.1})
        self.assertEqual(parse("Restores HP equal to #1[i]% of the wearer's ATK. The next ally taking action (except the "
                               "wearer) deals #2[i]% more DMG. Regenerates #3[i] Energy.", [0.1, 0.3, 4]), {})
        # and the scorer uses them: a passive's CRIT DMG is worth what the same CRIT DMG on a relic is
        calc = {"hp": 1000, "atk": 1000, "def": 500, "spd": 100, "element": "Ice", "bonus": {"CriticalChanceBase": 0.5}}
        plain = optimize.Scorer(self.assets, calc, {"CRIT Rate", "CRIT DMG", "ATK%"})
        cone = optimize.Scorer(self.assets, calc, {"CRIT Rate", "CRIT DMG", "ATK%"}, cone={"CriticalDamageBase": 0.4})
        self.assertAlmostEqual(cone.index([{}], {}), plain.index([{"CriticalDamageBase": 0.4}], {}))

    def test_elation_formula(self):
        """Elation DMG: a fixed base and Elation in place of ATK and DMG Boost, with crit."""
        calc = {"hp": 1000, "atk": 1000, "def": 500, "spd": 100, "element": "Quantum", "bonus": {"CriticalDamageBase": 0.5}}
        scorer = optimize.Scorer(self.assets, calc, {"CRIT Rate", "CRIT DMG", "SPD"}, elation=True)
        self.assertEqual(scorer.counted(), ["Elation", "CRIT Rate", "CRIT DMG", "SPD"])
        props = {"ElationDamageAddedRatioBase": 0.4, "CriticalChanceBase": 0.5, "AttackAddedRatio": 0.9, "QuantumAddedRatio": 0.4}
        self.assertAlmostEqual(scorer.index([props], {}), 7535.107 * 1.4 * 1.25 * DEF * SLOW)
        girl = {"129": 4}  # Ever-Glorious Magical Girl: 16% CRIT DMG, Elation DMG ignores 20% DEF at full stacks
        self.assertAlmostEqual(scorer.index([props], girl), 7535.107 * 1.4 * (1 + 0.5 * 0.66) * 100 / (115 * 0.8 + 100) * SLOW)

    def test_tries_same_path_light_cones(self):
        builds = self.account(keep=8)
        paths = {}
        for b in builds:
            paths.setdefault(self.assets.data["hsr_characters"][b.character_id]["AvatarBaseType"], []).append(b)
        same = next(group for group in paths.values() if len(group) >= 2 and all(b.weapon for b in group))
        target = same[0]
        result = optimize.optimize(self.assets, target, builds, RELICS, PLANAR, None)
        names = {b.weapon.name for b in same}
        self.assertEqual(result.cones, len(names))
        self.assertIn(result.build.weapon.name, names)
        owner = next(b for b in same if b.name == result.cone_owner)
        self.assertEqual(owner.weapon.name, result.build.weapon.name)
        self.assertIn("Light cone: **", optimize_text(result, target, RELICS, PLANAR))

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
