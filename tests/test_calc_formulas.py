"""Damage formulas of bot/calc against hand-computed values (no game data needed)."""

from __future__ import annotations

import unittest

from bot.calc import formulas as F
from bot.calc.model import AshHit, ashblazing_stacks


class FormulaTests(unittest.TestCase):
    def test_def_multiplier(self):
        # (80 + 20) / ((95 + 20) x (1 - 0) + 80 + 20) = 100 / 215
        self.assertAlmostEqual(F.def_multiplier(80, 95, 0.0), 100 / 215)
        # 20% DEF ignore: 100 / (115 x 0.8 + 100) = 100 / 192
        self.assertAlmostEqual(F.def_multiplier(80, 95, 0.2), 100 / 192)
        # more than 100% ignore counts as 100%: 100 / 100
        self.assertAlmostEqual(F.def_multiplier(80, 95, 1.5), 1.0)

    def test_res_multiplier(self):
        self.assertAlmostEqual(F.res_multiplier(0.2, 0.0), 0.8)
        self.assertAlmostEqual(F.res_multiplier(0.0, 0.25), 1.25)
        self.assertAlmostEqual(F.res_multiplier(0.2, 1.5), 2.0)  # RES floors at -100%
        self.assertAlmostEqual(F.res_multiplier(1.0, 0.0), 0.1)  # and caps at 90%

    def test_vuln_and_crit(self):
        self.assertAlmostEqual(F.vuln_multiplier(0.3), 1.3)
        self.assertAlmostEqual(F.vuln_multiplier(4.0), 3.5)  # capped at +250%
        self.assertAlmostEqual(F.vuln_multiplier(-0.5), 1.0)
        # 50% x (1 + 100%) + 50% = 1.5
        self.assertAlmostEqual(F.crit_multiplier(0.5, 1.0), 1.5)
        self.assertAlmostEqual(F.crit_multiplier(1.3, 1.0), 2.0)  # CRIT Rate capped at 100%
        self.assertAlmostEqual(F.crit_multiplier(-0.1, 1.0), 1.0)

    def test_common_and_crit_damage(self):
        # 0.9 (not broken) x 100/215 x RES 1.0 x vuln 1.0 x final 1.0 x true 1.0
        self.assertAlmostEqual(F.common(80, 95, 0.0, False, 0, 0, 0, 0, 0), 0.9 * 100 / 215)
        # broken, 20% vuln, 50% final, 24% True DMG: 1.0 x 100/215 x 1.2 x 1.5 x 1.24
        self.assertAlmostEqual(F.common(80, 95, 0.0, True, 0, 0, 0.2, 0.5, 0.24), 100 / 215 * 1.2 * 1.5 * 1.24)
        # 1000 base x (1 + 50%) x crit 1.5 x 1.0
        self.assertAlmostEqual(F.crit_damage(1000, 0.5, 0.5, 1.0, 1.0), 2250.0)

    def test_dot(self):
        # 100% base chance x (1 + 18% EHR) x (1 - 30% Effect RES) = 0.826
        self.assertAlmostEqual(F.dot_chance(1.0, 0.18, 0.3, 0.0), 0.826)
        self.assertAlmostEqual(F.dot_chance(1.0, 1.0, 0.3, 0.0), 1.0)  # at most 100%
        # stacked DoT split: p = 0.5; (1 + 0.5 x 0.5 x 2) / (1 + 0.5 x 2) = 1.5 / 2
        self.assertAlmostEqual(F.dot_chance(0.5, 0.0, 0.0, 0.0, split=0.5, stacks=3), 0.75)
        # 2000 x (1 + 100%) x 0.826 x 0.5 x 4 ticks
        self.assertAlmostEqual(F.dot_damage(2000, 1.0, 0.826, 0.5, 4), 6608.0)

    def test_break(self):
        # Fire: 3767.5533 x 2 x (0.5 + 120/40) x (1 + 100% BE) x (1 + 0) x 1.0
        self.assertAlmostEqual(F.break_damage(3767.5533, "Fire", 120, 1.0, 0.0, 1.0), 3767.5533 * 2 * 3.5 * 2)
        # Quantum, 60 Toughness, 50% Break DMG boost, special 0.5:
        # 3767.5533 x 0.5 x 2.0 x 0.5 x 1.0 x 1.5 x 0.4
        self.assertAlmostEqual(F.break_damage(3767.5533, "Quantum", 60, 0.0, 0.5, 0.4, special=0.5),
                               3767.5533 * 0.5 * 2.0 * 0.5 * 1.5 * 0.4)

    def test_super_break(self):
        # 3767.5533 / 10 x ((1 + 50%) x 30 + 0) x (1 + 200% BE) x 1.0 x 1.0 x 1.0
        self.assertAlmostEqual(F.super_break_damage(3767.5533, 30, 0.5, 0, 2.0, 1.0, 0.0, 1.0), 376.75533 * 45 * 3)
        # 20 fixed Toughness on top, modifier 1.5: 376.75533 x (30 + 20) x 2 x 1.5
        self.assertAlmostEqual(F.super_break_damage(3767.5533, 30, 0.0, 20, 1.0, 1.5, 0.0, 1.0), 376.75533 * 50 * 2 * 1.5)

    def test_elation(self):
        # 7535.107 x 1.0 x (1 + 50%) x 1 x 1 x crit 1 x 1
        self.assertAlmostEqual(F.elation_damage(7535.107, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 1.0), 7535.107 * 1.5)
        # punchline 240: 1 + 5 x 240 / 480 = 3.5
        self.assertAlmostEqual(F.elation_damage(1000, 1.0, 0.0, 0.0, 240, 0.0, 0.0, 1.0), 3500.0)

    def test_level_multiplier(self):
        self.assertEqual(F.level_multiplier(80), (3767.5533, True))
        value, exact = F.level_multiplier(75)
        self.assertFalse(exact)
        # linear between the Lv. 70 and Lv. 79 anchors (unverified levels are flagged approximate)
        self.assertAlmostEqual(value, 2659.6406 + (3665.9099 - 2659.6406) * 5 / 9)

    def test_expected_turns(self):
        # cycles of 150, 250, 350, 450, 550 AV at SPD 100: 1, 2, 3, 4, 5 turns -> 3.0
        self.assertAlmostEqual(float(F.expected_turns(100)), 3.0)
        # SPD 134: 2.01, 3.35, 4.69, 6.03, 7.37 -> 2 + 3 + 4 + 6 + 7 = 22 -> 4.4
        self.assertAlmostEqual(float(F.expected_turns(134)), 4.4)

    def test_ashblazing(self):
        # Kafka's follow-up: six single hits at stacks 1..6 weighted 15% x5 and 25%:
        # 0.06 x (0.15 x (1+2+3+4+5) + 0.25 x 6) = 0.06 x 3.75 = 0.225
        hits = [AshHit("single", 0.15)] * 5 + [AshHit("single", 0.25)]
        self.assertAlmostEqual(ashblazing_stacks(hits, 1), 0.225)
        # one AoE hit on 5 enemies starts at ceil(5/2) = 3 stacks
        self.assertAlmostEqual(ashblazing_stacks([AshHit("aoe", 1.0)], 5), 0.18)


if __name__ == "__main__":
    unittest.main()
