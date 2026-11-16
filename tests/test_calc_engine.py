"""End-to-end checks of the damage engine (bot/calc) against hand-computed values, on the real game data.

Every expected number is built from first principles in the test: the character's base ATK and the ability
multipliers come from the game data, the rest of the arithmetic is written out in the comments.
"""

from __future__ import annotations

import copy
import unittest

from test_parsers import load_assets

from bot.calc import CalcError, EvaluateRequest, Relic, evaluate
from bot.calc.gamedata import GameData

LV_MULT = 3767.5533
DEF_80_VS_95 = 100 / 215  # (80 + 20) / ((95 + 20) + 80 + 20), no DEF ignore


def base_atk(gd: GameData, cid: str, variant: int, lc_atk: float = 0.0) -> float:
    """Character-screen ATK without relics: (character + light cone base) x (1 + ATK% trace nodes)."""
    base = gd.base_stats(cid, 80, 6)["atk"] + lc_atk
    nodes = sum(n.get("atk%", 0.0) for n in gd.stat_nodes(cid, variant).values())
    return base * (1 + nodes)


def node_sum(gd: GameData, cid: str, variant: int, key: str) -> float:
    return sum(n.get(key, 0.0) for n in gd.stat_nodes(cid, variant).values())


def effect_values(ev, owner: str | None = None) -> dict[tuple[str, str], float]:
    return {(e["owner"], e["source"], e["stat"]): e["value"] for e in ev.effects if owner is None or e["owner"] == owner}


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.gd = GameData(cls.assets)

    def test_seele_rotation(self):
        """Seele (reworked kit), E0, no light cone or relics, one combo (Speed off): Ultimate + 4 Skills."""
        ev = evaluate(self.assets, {"character": {"id": "1102"}, "speed": False}, [])
        self.assertEqual(ev.character["definition"], "1102b1")
        self.assertFalse(ev.approximate)
        gd = self.gd
        atk = base_atk(gd, "1102", 1)
        self.assertAlmostEqual(ev.stats["atk"], atk, places=6)
        # DMG Boost: A2 50% x 3 stacks + Talent (Amplification) 80% at Lv. 10 = 230%
        dmg = 0.5 * 3 + gd.skill_params("1110204", 10)[0]
        self.assertAlmostEqual(dmg, 2.3)
        # crit: 5% x (1 + 50% + 24% CRIT DMG nodes) + 95% = 1.037
        cd = 0.5 + node_sum(gd, "1102", 1, "cd")
        crit = 1 + 0.05 * cd
        # RES: weak to Quantum (0) minus A4's 25% Quantum RES PEN -> x1.25; not broken: x0.9
        mult = 0.9 * DEF_80_VS_95 * 1.25
        ult = atk * gd.skill_params("1110203", 10)[0] * (1 + dmg) * crit * mult
        skill = atk * gd.skill_params("1110202", 10)[0] * (1 + dmg) * crit * mult
        per = {a["key"]: a["per_use"] for a in ev.abilities}
        self.assertAlmostEqual(per["ult"], ult, places=4)
        self.assertAlmostEqual(per["skill"], skill, places=4)
        self.assertAlmostEqual(ev.total, ult + 4 * skill, places=3)
        self.assertEqual(ev.repetitions, 1.0)

    def test_kafka_dot_with_ruan_mei(self):
        """Kafka (reworked kit) E2 with Ruan Mei: the DoT entry, Speed off."""
        req = {"character": {"id": "1005", "eidolon": 2}, "teammates": [{"id": "1303"}], "speed": False}
        ev = evaluate(self.assets, req, [])
        gd = self.gd
        atk = base_atk(gd, "1005", 1)
        # DMG for DoT: Ruan Mei Skill 32% + her A6 36% (teammate input) + Kafka E2 33% (DoT only) = 101%
        dmg = 0.32 + 0.36 + 0.33
        # apply chance: 100% x (1 + 18% EHR nodes) x (1 - 30% enemy Effect RES) = 0.826
        chance = 1.0 * (1 + node_sum(gd, "1005", 1, "ehr")) * 0.7
        self.assertAlmostEqual(chance, 0.826)
        # common: 0.9 x DEF x RES (weak 0, Ruan Mei Ultimate 25% RES PEN -> 1.25) x E1 DoT vulnerability 1.3
        mult = 0.9 * DEF_80_VS_95 * 1.25 * 1.3
        # Shock: 290% of ATK at Ultimate Lv. 10, 4 ticks (Fribbels' tickCoefficient)
        dot = atk * gd.skill_params("1100503", 10)[3] * 4 * (1 + dmg) * chance * mult
        per = {a["key"]: a["per_use"] for a in ev.abilities}
        self.assertAlmostEqual(per["dot"], dot, places=4)
        # Ruan Mei's teammate-only buffs reach Kafka; her A6 counts as the input value (0.36)
        vals = effect_values(ev, "Ruan Mei")
        self.assertAlmostEqual(vals[("Ruan Mei", "Talent", "spd%")], 0.10)
        self.assertAlmostEqual(vals[("Ruan Mei", "Trace A6", "dmg")], 0.36)

    def test_firefly_super_break(self):
        """Firefly (reworked kit) E0, Super Break on: the enhanced Skill's Super Break hit with a BE rope."""
        rope = Relic(uid="rope", set_id="316", slot="Link Rope", rarity=5, level=15, main="be", main_value=0.648,
                     subs={"be": 0.25})
        ev = evaluate(self.assets, {"character": {"id": "1310"}, "speed": False}, [rope])
        gd = self.gd
        # BE: nodes 37.3% + A2 25% (Complete Combustion) + rope 64.8% + 25% = 1.521 -> A4 Super Break 100%
        be = node_sum(gd, "1310", 1, "be") + 0.25 + 0.648 + 0.25
        self.assertAlmostEqual(ev.stats["be"], be, places=9)
        self.assertGreaterEqual(be, 1.5)
        self.assertLess(be, 3.0)
        # LvMult / 10 x (1 + 50% Weakness Break Efficiency) x 30 Toughness x (1 + BE) x 1.0
        #   x DEF x RES 1.0 (weak) x vulnerability 1.2 (Ultimate, enemy broken) x 1.0 (broken: no 0.9)
        expected = LV_MULT / 10 * 1.5 * 30 * (1 + be) * 1.0 * DEF_80_VS_95 * 1.0 * 1.2 * 1.0
        hits = next(a for a in ev.abilities if a["key"] == "skill")["hits"]
        sb = next(h for h in hits if h["func"] == "super_break")
        self.assertAlmostEqual(sb["damage"], expected, places=4)
        # combo: Ultimate (no damage), 4 Skills, 1 Weakness Break
        self.assertEqual({a["key"]: a["uses"] for a in ev.abilities}, {"ult": 1.0, "skill": 4.0, "break": 1.0})

    def test_speed_repetitions(self):
        """With Speed on, the combo repeats (expected turns over 1-5 cycles) / (Skills in the combo)."""
        spd = 115.0  # Seele's 115 base x 1.25 (Skill SPD, one stack before E2) = 143.75
        ev = evaluate(self.assets, {"character": {"id": "1102"}}, [])
        self.assertAlmostEqual(ev.stats["spd"], spd * 1.25)
        # 143.75 SPD: 2.16, 3.59, 5.03, 6.47, 7.91 -> 2 + 3 + 5 + 6 + 7 = 23 turns / 5 = 4.6; 4 Skills -> 1.15
        self.assertAlmostEqual(ev.repetitions, 4.6 / 4)


class Targets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()

    def test_teammate_rules(self):
        ev = evaluate(self.assets, {"character": {"id": "1102"}, "teammates": [{"id": "1309"}, {"id": "1101"}]}, [])
        vals = effect_values(ev)
        # Robin as a teammate: 4500 ATK x 22.8% + 200 (Ultimate Lv. 10), not convertible
        self.assertAlmostEqual(vals[("Robin", "Ultimate", "atk")], 4500 * 0.228 + 200)
        # Bronya's single-target Skill reaches the main character; her CRIT DMG buff uses the 250% input
        self.assertAlmostEqual(vals[("Bronya", "Skill", "dmg")], 0.66)
        self.assertAlmostEqual(vals[("Bronya", "Ultimate", "cd")], 0.16 * 2.5 + 0.20)
        self.assertTrue(any("advances" in n for n in ev.notes))

    def test_support_as_main(self):
        ev = evaluate(self.assets, {"character": {"id": "1101"}}, [])
        self.assertEqual(ev.unit, "buff")
        sources = {(e["owner"], e["source"]) for e in ev.effects}
        self.assertNotIn(("Bronya", "Skill"), sources)  # "ally" buffs don't reach Bronya herself
        # buff = 16% x Bronya's CRIT DMG + 20%
        self.assertAlmostEqual(ev.total, 0.16 * ev.stats["cd"] + 0.20)

    def test_memosprite_targets(self):
        req = {"character": {"id": "1407"},
               "teammates": [{"id": "1313", "eidolon": 1, "relic_set": "121", "light_cone": {"id": "23034"}}]}
        ev = evaluate(self.assets, req, [])
        by_source = {(e["owner"], e["source"], e["stat"]): e for e in ev.effects}
        e1 = by_source[("Sunday", "E1 (summon)", "def_pen")]
        self.assertEqual(e1["reaches"], ["memo"])
        self.assertEqual(by_source[("Sunday", "Skill", "dmg")]["reaches"], ["memo", "self"])
        # Sunday wearing A Grounded Ascent / Sacerdos: the buff reaches the memosprite too
        self.assertEqual(by_source[("A Grounded Ascent (Sunday)", "A Grounded Ascent", "dmg")]["reaches"], ["memo", "self"])
        self.assertAlmostEqual(by_source[("Sacerdos' Relived Ordeal (Sunday)", "Sacerdos 4pc", "cd")]["value"], 0.36)
        self.assertIsNotNone(ev.memo_stats)
        # Netherwing hits scale on Castorice's HP: its memo-skill hit's base is HP x 34% (memo skill Lv. 6, 3rd use)
        hit = next(a for a in ev.abilities if a["key"] == "memo_skill")["hits"][0]
        self.assertAlmostEqual(hit["base"], ev.stats["hp"] * 0.34, places=6)

    def test_nonstackable_team_set(self):
        """Messenger 4pc on a teammate and on the main character counts once."""
        req = {"character": {"id": "1102"}, "teammates": [{"id": "1101", "relic_set": "114"}],
               "toggles": {"main.set.114.enabled": True}}
        pieces = [Relic(uid=f"m{i}", set_id="114", slot=s, rarity=5, level=15, main=m, main_value=0.1)
                  for i, (s, m) in enumerate([("Head", "hp"), ("Hands", "atk"), ("Body", "cr"), ("Feet", "spd")])]
        ev = evaluate(self.assets, req, pieces)
        spd = [e for e in ev.effects if e["stat"] == "spd%" and "Messenger" in e["source"] and e["active"]]
        self.assertEqual(len(spd), 1)

    def test_stat_conditional_set(self):
        """Rutilant Arena: +20% Basic/Skill DMG only at 70% CRIT Rate or more."""
        def run(cr):
            sphere = Relic(uid="s", set_id="309", slot="Planar Sphere", rarity=5, level=15, main="dmg_quantum",
                           main_value=0.388, subs={"cr": cr})
            rope = Relic(uid="r", set_id="309", slot="Link Rope", rarity=5, level=15, main="atk%", main_value=0.432)
            ev = evaluate(self.assets, {"character": {"id": "1102"}, "speed": False}, [sphere, rope])
            return next(e for e in ev.effects if e["source"] == "Rutilant Arena")["value"]
        # 5% base + 8% (2pc) = 13%; + 0.57 -> 70%
        self.assertAlmostEqual(run(0.57), 0.20)
        self.assertAlmostEqual(run(0.50), 0.0)

    def test_toggles(self):
        ev = evaluate(self.assets, {"character": {"id": "1102"}, "toggles": {"main.char.dmgBoostStacks": 1}}, [])
        self.assertEqual(ev.toggles["main.char.dmgBoostStacks"], 1.0)
        self.assertAlmostEqual(effect_values(ev)[("Seele", "Trace A2", "dmg")], 0.5)
        with self.assertRaises(CalcError):
            evaluate(self.assets, {"character": {"id": "1102"}, "toggles": {"main.char.nope": 1}}, [])
        with self.assertRaises(CalcError):
            evaluate(self.assets, {"character": {"id": "1102"}, "toggles": {"main.char.dmgBoostStacks": 9}}, [])


class Fallback(unittest.TestCase):
    """A made-up character with no definition: the hits and buffs are read from its ability texts."""

    @classmethod
    def setUpClass(cls):
        real = load_assets()
        fake = copy.copy(real)
        d = dict(real.data)
        d["srr_characters"] = {**d["srr_characters"], "9901": {
            "id": "9901", "name": "Testa", "path": "Warrior", "element": "Fire",
            "ranks": [], "skills": ["990101", "990102", "990103"], "skill_trees": []}}
        d["srr_character_skills"] = {**d["srr_character_skills"],
            "990101": {"name": "Poke", "type": "Normal", "params": [[0.5 + 0.1 * i] for i in range(9)],
                       "desc": "Deals Fire DMG equal to #1[i]% of Testa's ATK to one designated enemy."},
            "990102": {"name": "Jab", "type": "BPSkill", "params": [[1.0 + 0.1 * i, 0.1 + 0.02 * i] for i in range(15)],
                       "desc": "Deals Fire DMG equal to #1[i]% of Testa's ATK to one designated enemy. "
                               "Increases this unit's CRIT Rate by #2[i]%."},
            "990103": {"name": "Blast", "type": "Ultra", "params": [[2.0 + 0.1 * i] for i in range(15)],
                       "desc": "Deals Fire DMG equal to #1[i]% of Testa's ATK to all enemies."},
        }
        d["hsr_meta"] = {**d["hsr_meta"], "avatar": {**d["hsr_meta"]["avatar"], "9901": {"6": {
            "HPBase": 1000, "HPAdd": 0, "AttackBase": 1000, "AttackAdd": 0, "DefenceBase": 500, "DefenceAdd": 0,
            "SpeedBase": 100, "CriticalChance": 0.05, "CriticalDamage": 0.5}}}}
        fake.data = d
        cls.assets = fake

    def test_fallback_character(self):
        ev = evaluate(self.assets, {"character": {"id": "9901"}, "speed": False}, [])
        self.assertTrue(ev.approximate)
        self.assertFalse(ev.character["reviewed"])
        # CRIT Rate from the Skill text at Lv. 10: 10% + 9 x 2% = 28%, on top of 5%
        self.assertAlmostEqual(ev.stats["cr"], 0.33)
        # crit 1 + 33% x 50% = 1.165; common 0.9 x 100/215 (Fire weakness: RES 0)
        mult = 1.165 * 0.9 * DEF_80_VS_95
        per = {a["key"]: a["per_use"] for a in ev.abilities}
        self.assertAlmostEqual(per["ult"], 1000 * 2.9 * mult)  # Ultimate Lv. 10: 290%
        self.assertAlmostEqual(per["skill"], 1000 * 1.9 * mult)  # Skill Lv. 10: 190%
        # fallback rotation for Destruction: Ultimate + 3 Skills
        self.assertAlmostEqual(ev.total, 1000 * (2.9 + 3 * 1.9) * mult)

    def test_undefined_teammate_adds_nothing(self):
        ev = evaluate(self.assets, {"character": {"id": "1102"}, "teammates": [{"id": "9901"}]}, [])
        self.assertTrue(ev.approximate)
        self.assertFalse([e for e in ev.effects if e["owner"] == "Testa"])


class RequestValidation(unittest.TestCase):
    def test_strict_from_dict(self):
        with self.assertRaises(CalcError):
            EvaluateRequest.from_dict({"character": {"id": "1102"}, "colour": "red"})
        with self.assertRaises(CalcError):
            EvaluateRequest.from_dict({"character": {"id": "1102", "eidolon": "two"}})
        with self.assertRaises(CalcError):
            EvaluateRequest.from_dict({"teammates": []})
        req = EvaluateRequest.from_dict({"character": {"id": "1102", "light_cone": {"id": "23001", "rank": 5}},
                                         "teammates": [{"id": "1309"}], "enemy": {"count": 3}})
        self.assertEqual(req.character.light_cone.rank, 5)
        self.assertEqual(EvaluateRequest.from_dict(req.to_dict()), req)

    def test_relic_from_dict(self):
        r = Relic.from_dict({"uid": "a", "set_id": "108", "slot": "Body", "rarity": 5, "level": 15, "main": "cr",
                             "main_value": 0.324, "subs": {"cd": 0.1}})
        self.assertEqual(Relic.from_dict(r.to_dict()), r)
        with self.assertRaises(CalcError):
            Relic.from_dict({**r.to_dict(), "main": "be"})  # BE is not a Body main stat
        with self.assertRaises(CalcError):
            Relic.from_dict({**r.to_dict(), "set_id": "301"})  # planar set on a Body
        with self.assertRaises(CalcError):
            Relic.from_dict({**r.to_dict(), "extra": 1})


if __name__ == "__main__":
    unittest.main()
