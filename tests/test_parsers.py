"""Parser tests against Enka's real game data with hand-written API responses.

Run with:  python -m unittest discover tests
The game data is downloaded into ./data on first run (needs internet).
"""

from __future__ import annotations

import json
import os
import unittest
import urllib.request
from pathlib import Path

from bot import matching
from bot.assets import FILES, STORE_URL, Assets
from bot.games import genshin, starrail, zenless

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
CACHE = Path(os.environ.get("CACHE_DIR", ROOT / "data"))


def load_assets() -> Assets:
    for rel in FILES.values():
        path = CACHE / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(STORE_URL + rel, timeout=30) as resp:
                path.write_bytes(resp.read())
    assets = Assets(CACHE)
    assets.load()
    return assets


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def stats(build) -> dict[str, str]:
    return {s.name: s.value for s in build.stats}


class AssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()

    def test_character_names_resolve_for_every_game(self):
        for game, expected in [("genshin", "Kamisato Ayaka"), ("hsr", "March 7th"), ("zzz", "Anby")]:
            with self.subTest(game=game):
                names = self.assets.character_names(game)
                self.assertIn(expected, names)
                self.assertGreater(len(names), 40)
                self.assertFalse([n for n in names if n.isdigit()], "unresolved hashes")


class GenshinTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.profile = genshin.parse_profile(cls.assets, "618285856", fixture("genshin.json"))

    def test_profile(self):
        self.assertEqual(self.profile.nickname, "Algoinde")
        self.assertEqual([c.name for c in self.profile.characters], ["Kamisato Ayaka", "Traveler"])

    def test_ayaka_build(self):
        ayaka = self.profile.characters[0]
        self.assertEqual(ayaka.level, 90)
        self.assertEqual(ayaka.constellation, 2)
        self.assertEqual(ayaka.element, "Cryo")
        s = stats(ayaka)
        self.assertEqual(s["HP"], "18,524")
        self.assertEqual(s["CRIT Rate"], "45.3%")
        self.assertEqual(s["Cryo DMG Bonus"], "61.6%")
        self.assertEqual(ayaka.weapon.name, "Mistsplitter Reforged")
        self.assertEqual(ayaka.weapon.refinement, 1)
        self.assertEqual([t.value for t in ayaka.talents], ["9", "9", "13 ★"])
        self.assertEqual([g.slot for g in ayaka.gear], ["Flower", "Plume"])
        self.assertEqual(ayaka.gear[0].level, 20)
        self.assertEqual(ayaka.gear[0].main.value, "4,780")
        self.assertEqual(ayaka.gear[0].subs[0].value, "10.5%")
        self.assertEqual(ayaka.set_bonuses, ["2pc Blizzard Strayer"])

    def test_traveler_uses_element_variant(self):
        self.assertEqual(self.profile.characters[1].element, "Anemo")


class StarRailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.profile = starrail.parse_profile(cls.assets, "800069903", fixture("hsr.json"))

    def test_bare_march_matches_in_game_base_stats(self):
        # March 7th, Lv. 80, nothing equipped: 1058 HP / 511 ATK / 573 DEF / 101 SPD in-game.
        march = self.profile.characters[0]
        self.assertEqual(march.name, "March 7th")
        s = stats(march)
        self.assertEqual((s["HP"], s["ATK"], s["DEF"], s["SPD"]), ("1,058", "511", "573", "101.0"))
        self.assertEqual(s["CRIT Rate"], "5.0%")
        self.assertEqual(s["Energy Regen Rate"], "100.0%")

    def test_relics_light_cone_and_eidolons(self):
        seele = self.profile.characters[1]
        self.assertEqual(seele.name, "Seele")
        self.assertEqual(seele.constellation, 1)
        self.assertEqual(seele.weapon.name, "In the Night")
        self.assertEqual(seele.gear[0].slot, "Head")
        self.assertEqual(seele.gear[0].main.value, "705")  # 5* HP head at +15
        s = stats(seele)
        # 5% base + 18% In the Night passive + one 2.6% substat roll
        self.assertEqual(s["CRIT Rate"], "25.6%")
        # 931 base + 1,058 light cone + 705.6 head
        self.assertEqual(s["HP"], "2,695")
        self.assertEqual(seele.gear[0].set_name, "Hunter of Glacial Forest")
        self.assertEqual(seele.set_bonuses, [])


class StarRailFlatPropsTest(unittest.TestCase):
    """Enka's documented response shape: rolled relic values in _flat.props, support characters flagged _assist."""

    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.profile = starrail.parse_profile(cls.assets, "800069903", fixture("hsr_flat.json"))

    def test_support_duplicate_is_dropped(self):
        self.assertEqual([c.name for c in self.profile.characters], ["Seele", "March 7th"])

    def test_relic_values_come_from_flat_props(self):
        seele = self.profile.characters[0]
        head, feet = seele.gear
        self.assertEqual((head.slot, head.main.value), ("Head", "705"))
        self.assertEqual([(s.name, s.value) for s in head.subs], [("CRIT Rate", "3.2%"), ("SPD", "6.6")])
        # Relic id unknown to the store data: slot and set still come from the response.
        self.assertEqual((feet.slot, feet.set_name, feet.main.value), ("Feet", "Hunter of Glacial Forest", "25.0"))
        self.assertEqual(seele.set_bonuses, ["2pc Hunter of Glacial Forest"])
        s = stats(seele)
        self.assertEqual(s["SPD"], "146.6")  # 115 base + 6.6 + 25.032
        self.assertEqual(s["CRIT Rate"], "26.2%")  # 5% base + 18% In the Night + 3.24%


class StarRailLiveTest(unittest.TestCase):
    """A real Enka response (UID 800069903, fetched 2026-10-07, nickname anonymized)."""

    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.data = fixture("hsr_live.json")
        cls.profile = starrail.parse_profile(cls.assets, "800069903", cls.data)
        cls.by_name = {c.name: c for c in cls.profile.characters}

    def test_profile(self):
        self.assertEqual((self.profile.nickname, self.profile.level), ("Player", 70))
        self.assertEqual(len(self.profile.characters), 8)

    def test_castorice_matches_enka_library(self):
        # Totals cross-checked with the `enka` PyPI package on the same response.
        c = self.by_name["Castorice"]
        s = stats(c)
        self.assertEqual((s["HP"], s["ATK"], s["DEF"], s["SPD"]), ("9,259", "1,595", "1,215", "89.7"))
        self.assertEqual((s["CRIT Rate"], s["Quantum DMG Boost"]), ("66.1%", "24.4%"))
        self.assertEqual(c.weapon.name, "Make Farewells More Beautiful")
        # Substats arrive as CriticalChance/CriticalDamage, without the "Base" suffix.
        self.assertEqual([x.name for x in c.gear[0].subs], ["HP%", "DEF%", "CRIT Rate", "CRIT DMG"])
        self.assertEqual(c.set_bonuses, ["4pc Poet of Mourning Collapse", "2pc Bone Collection's Serene Demesne"])

    def test_long_trace_ids(self):
        # Firefly's traces come as 11310xxx; her minor traces add 37.3% Break Effect.
        firefly = self.by_name["Firefly"]
        self.assertEqual(stats(firefly)["Break Effect"], "216.3%")
        self.assertEqual([t.value for t in firefly.talents], ["6", "10", "10", "10"])

    def test_character_missing_from_store_data(self):
        data = json.loads(json.dumps(self.data))
        data["detailInfo"]["avatarDetailList"][0]["avatarId"] = 9999
        unknown = starrail.parse_profile(self.assets, "800069903", data).characters[0]
        self.assertEqual(unknown.name, "Character 9999")
        self.assertIn("newer than Enka's game data", unknown.notes[0])


class ZenlessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.profile = zenless.parse_profile(cls.assets, "1300003409", fixture("zzz.json"))

    def test_anby(self):
        anby = self.profile.characters[0]
        self.assertEqual(anby.name, "Anby")
        self.assertEqual(anby.element, "Electric")
        self.assertEqual(anby.weapon.name, "Steel Cushion")
        # Example from Enka's ZZZ docs: Steel Cushion Lv. 60, modification 5 -> 684 ATK / 24% ATK.
        self.assertEqual([(w.name, w.value) for w in anby.weapon.stats], [("ATK", "684"), ("CRIT Rate", "24.0%")])
        s = stats(anby)
        self.assertEqual(s["HP"], "9,590")  # 7,500 Lv. 60 base (matches in-game) + 2,090 disc
        self.assertEqual(s["Energy Regen"], "1.20")
        self.assertEqual(anby.gear[0].main.value, "2,090")  # docs example: 550 base HP disc at +14
        self.assertEqual(anby.gear[0].subs[0].name, "CRIT Rate +2")
        self.assertEqual(anby.gear[0].subs[0].value, "7.2%")
        self.assertEqual(anby.talents[-1].value, "F")


class MatchingTest(unittest.TestCase):
    def test_find(self):
        names = ["Raiden Shogun", "Kamisato Ayaka", "Kamisato Ayato", "Hu Tao", "Zhu Yuan"]
        self.assertEqual(matching.find("raiden", names), "Raiden Shogun")
        self.assertEqual(matching.find("ei", names), "Raiden Shogun")
        self.assertEqual(matching.find("hutao", names), "Hu Tao")
        self.assertEqual(matching.find("Ayato", names), "Kamisato Ayato")
        self.assertEqual(matching.find("zhu", names), "Zhu Yuan")
        self.assertEqual(matching.find("ayaak", names), "Kamisato Ayaka")
        self.assertIsNone(matching.find("Furina", names))


if __name__ == "__main__":
    unittest.main()
