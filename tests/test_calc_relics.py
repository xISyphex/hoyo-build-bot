"""Kelz v4 relic export parser (bot/calc/relics.py) on a made-up export."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from test_parsers import load_assets

from bot.calc import CalcError, character_request, evaluate, parse_kelz

FIXTURE = Path(__file__).parent / "fixtures" / "calc" / "kelz_v4.json"


class KelzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_relics(self):
        export = parse_kelz(self.data, self.assets)
        self.assertEqual(export.source, "reliquary_archiver")
        self.assertIsNone(export.uid)
        head, body, rope, feet = export.relics
        # 5-star Head at +15: 112.896 + 15 x 39.5136 = 705.6 HP
        self.assertEqual((head.slot, head.main), ("Head", "hp"))
        self.assertAlmostEqual(head.main_value, 705.6)
        # substats from roll count and steps: CRIT Rate 2 x 2.592% + 3 x 0.324% = 6.156%
        self.assertAlmostEqual(head.subs["cr"], 0.06156)
        # SPD 3 x 2.0 + 2 x 0.3 = 6.6 (the hidden decimals survive)
        self.assertAlmostEqual(head.subs["spd"], 6.6)
        self.assertAlmostEqual(head.subs["atk"], 19.051896)
        self.assertEqual(head.location, "1102")
        # Body CRIT Rate at +15: 32.4%; substats without counts use the value (percent units)
        self.assertEqual(body.main, "cr")
        self.assertAlmostEqual(body.main_value, 0.324)
        self.assertAlmostEqual(body.subs["atk%"], 0.0864)
        self.assertAlmostEqual(body.subs["cd"], 0.1296)
        # Rope "ATK" is ATK%: 43.2%
        self.assertEqual(rope.main, "atk%")
        self.assertAlmostEqual(rope.main_value, 0.432)
        self.assertAlmostEqual(rope.subs["be"], 0.0648)
        self.assertAlmostEqual(feet.main_value, 25.032)
        self.assertEqual(feet.subs, {})

    def test_character_request(self):
        export = parse_kelz(self.data, self.assets)
        req = character_request(export, "1102")
        # levels above the pre-eidolon caps are clamped (the engine adds eidolon levels itself)
        self.assertEqual(req["abilities"], {"basic": 6, "skill": 10, "ult": 10, "talent": 10})
        self.assertEqual(req["eidolon"], 1)
        self.assertEqual(req["ability_version"], 1)
        self.assertFalse(req["traces"]["ability_3"])
        self.assertEqual(req["light_cone"], {"id": "23001", "level": 80, "ascension": 6, "rank": 2})
        worn = [r for r in export.relics if r.location == "1102"]
        ev = evaluate(self.assets, {"character": req, "toggles": {"main.char.e1EnemyHp80CrBoost": True}}, worn)
        self.assertEqual(ev.sets, {"108": 1, "305": 1})
        self.assertEqual(ev.character["definition"], "1102b1")
        # the export's eidolon reaches the E1 effects (their condition is switched on)
        sources = {e["source"] for e in ev.effects if e["active"]}
        self.assertIn("E1", sources)
        with self.assertRaises(CalcError):
            character_request(export, "1005")

    def test_errors(self):
        bad = copy.deepcopy(self.data)
        bad["version"] = 3
        with self.assertRaisesRegex(CalcError, "version"):
            parse_kelz(bad, self.assets)
        bad = copy.deepcopy(self.data)
        bad["relics"][1]["set_id"] = "999"
        with self.assertRaisesRegex(CalcError, "relic #2: unknown set"):
            parse_kelz(bad, self.assets)
        bad = copy.deepcopy(self.data)
        bad["relics"][3]["mainstat"] = "CRIT Rate"  # not a Feet main stat
        with self.assertRaisesRegex(CalcError, "relic #4"):
            parse_kelz(bad, self.assets)
        bad = copy.deepcopy(self.data)
        bad["relics"][0]["substats"][0]["key"] = "Luck_"
        with self.assertRaisesRegex(CalcError, "unknown substat"):
            parse_kelz(bad, self.assets)
        with self.assertRaises(CalcError):
            parse_kelz([], self.assets)


if __name__ == "__main__":
    unittest.main()
