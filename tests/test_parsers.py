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
from bot.assets import FILES, STORE_URL, URLS, Assets
from bot.games import genshin, starrail, zenless

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
CACHE = Path(os.environ.get("CACHE_DIR", ROOT / "data"))


def load_assets() -> Assets:
    for key, rel in FILES.items():
        path = CACHE / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(URLS.get(key, STORE_URL + rel), timeout=30) as resp:
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


class GenshinLiveTest(unittest.TestCase):
    """A real Enka response for UID 618285856 (fetched 2026-10-07, nickname anonymized)."""

    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.profile = genshin.parse_profile(cls.assets, "618285856", fixture("genshin_live.json"))
        cls.by_name = {c.name: c for c in cls.profile.characters}

    def test_substat_rolls(self):
        # appendPropIdList holds one affix id per roll; the flower's has 8 for 4 substats.
        flower = self.by_name["Amber"].gear[0]
        self.assertEqual([(s.name, s.rolls) for s in flower.subs], [("DEF", 2), ("ATK%", 2), ("CRIT DMG", 3), ("EM", 1)])

    def test_profile(self):
        self.assertEqual(self.profile.nickname, "TestPlayer")
        self.assertEqual(self.profile.level, 57)
        self.assertEqual(list(self.by_name), ["Amber", "Bennett", "Ganyu", "Xingqiu"])
        self.assertEqual(self.profile.showcase_names, ["Amber", "Bennett", "Ganyu", "Xingqiu"])

    def test_amber(self):
        amber = self.by_name["Amber"]
        self.assertEqual((amber.level, amber.rarity, amber.element, amber.constellation), (90, 4, "Pyro", 6))
        s = stats(amber)
        self.assertEqual((s["HP"], s["ATK"], s["CRIT Rate"]), ("14,241", "2,367", "51.9%"))
        self.assertEqual(s["Physical DMG Bonus"], "108.3%")
        self.assertEqual([t.value for t in amber.talents], ["10", "13 ★", "13 ★"])
        self.assertEqual((amber.weapon.name, amber.weapon.refinement), ("Skyward Harp", 2))
        self.assertEqual([g.slot for g in amber.gear], ["Flower", "Plume", "Sands", "Goblet", "Circlet"])
        self.assertEqual(amber.set_bonuses, ["2pc Bloodstained Chivalry", "2pc Pale Flame"])

    def test_set_names_resolve_by_set_id(self):
        # The setNameTextMapHash in the response is missing from the store's
        # text map for these sets; the name has to come from relics.json.
        xingqiu = self.by_name["Xingqiu"]
        self.assertEqual(
            [g.set_name for g in xingqiu.gear],
            ["Emblem of Severed Fate", "Emblem of Severed Fate", "Wanderer's Troupe",
             "Tenacity of the Millelith", "Wanderer's Troupe"],
        )
        self.assertEqual(xingqiu.set_bonuses, ["2pc Emblem of Severed Fate", "2pc Wanderer's Troupe"])
        self.assertEqual(self.by_name["Ganyu"].gear[3].set_name, "Shimenawa's Reminiscence")

    def test_every_embed_fits_discord_limits(self):
        from bot.embeds import build_embed

        for build in self.profile.characters:
            with self.subTest(character=build.name):
                for shown in (False, True):
                    embed = build_embed(self.profile, build, show_effect=shown)
                    self.assertLessEqual(len(embed), 6000)
                    self.assertTrue(all(len(f.value) <= 1024 for f in embed.fields))


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

    def test_substat_rolls(self):
        head = self.by_name["Castorice"].gear[0]
        self.assertEqual([s.rolls for s in head.subs], [1, 2, 3, 3])

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
        self.assertIn("newer than the game data", unknown.notes[0])

    def test_light_cone_effect(self):
        lc = self.by_name["Castorice"].weapon
        self.assertEqual(lc.effect_name, "Engrave")
        self.assertTrue(lc.effect.startswith("Increases the wearer's Max HP by 30%."))
        self.assertNotIn("#", lc.effect)
        # Superimposition 2 uses the second column of numbers (37.5% HP, 35% DEF ignore).
        data = json.loads(json.dumps(self.data))
        data["detailInfo"]["avatarDetailList"][0]["equipment"]["rank"] = 2
        s2 = starrail.parse_profile(self.assets, "800069903", data).characters[0].weapon
        self.assertIn("Max HP by 37.5%", s2.effect)
        self.assertIn("ignore 35% of the target's DEF", s2.effect)
        # A light cone on a character of another path gives no bonus, and says so.
        data["detailInfo"]["avatarDetailList"][0]["avatarId"] = 1001  # March 7th, Preservation
        off_path = starrail.parse_profile(self.assets, "800069903", data).characters[0].weapon
        self.assertEqual(off_path.effect_name, "Engrave (inactive: path doesn't match)")

    def test_every_embed_fits_discord_limits(self):
        from bot.embeds import build_embed

        for build in self.profile.characters:
            with self.subTest(character=build.name):
                for shown in (False, True):
                    embed = build_embed(self.profile, build, show_effect=shown)
                    self.assertLessEqual(len(embed), 6000)
                    self.assertTrue(all(len(f.value) <= 1024 for f in embed.fields))
        castorice = build_embed(self.profile, self.by_name["Castorice"], show_effect=True)
        self.assertIn("> **Engrave**\n> Increases the wearer's Max HP by 30%.", weapon_field(castorice))

    def test_every_light_cone_effect_fills_in(self):
        for tid in self.assets.data["hsr_lc_ranks"]:
            for rank in range(1, 6):
                with self.subTest(light_cone=tid, rank=rank):
                    effect = starrail.light_cone_effect(self.assets, tid, rank)
                    self.assertNotRegex(effect["effect"], r"#\d")
                    self.assertLessEqual(len(effect["effect"]), 1000)


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
        self.assertEqual((anby.gear[0].subs[0].name, anby.gear[0].subs[0].rolls), ("CRIT Rate", 3))
        self.assertEqual(anby.gear[0].subs[0].value, "7.2%")
        self.assertEqual(anby.talents[-1].value, "F")

    def test_yixuan(self):
        # SkillLevelList as a dict (the docs call it a dict), Rupture agent, new element.
        yixuan = self.profile.characters[1]
        self.assertEqual(yixuan.name, "Yixuan")
        self.assertEqual(yixuan.element, "Auric Ink")
        s = stats(yixuan)
        self.assertNotIn("Energy Regen", s)  # Rupture agents have no Energy Regen
        self.assertEqual(s["Wind DMG Bonus"], "30.0%")  # 750 * (1 + 15 * 0.2)
        self.assertEqual(yixuan.gear[0].main.name, "Wind DMG")
        self.assertEqual(dict((t.name, t.value) for t in yixuan.talents)["Basic"], "12 ★")

    def test_live_response(self):
        # Real Enka response (UID 1300003409, fetched 2026-10-07, nickname anonymized).
        profile = zenless.parse_profile(self.assets, "1300003409", fixture("zzz_live.json"))
        self.assertEqual(profile.nickname, "Proxy")
        self.assertEqual(profile.level, 52)
        self.assertEqual(profile.showcase_names, ["Anby", "Nicole", "Corin", "Miyabi", "Soldier 11", "Vivian"])
        miyabi = profile.characters[3]
        self.assertEqual(miyabi.element, "Frost")
        # Live discs use MainPropertyList; S-rank +15 main stats are fixed in-game values.
        self.assertEqual([g.main.value for g in miyabi.gear], ["2,200", "316", "184", "24.0%", "30.0%", "30.0%"])
        self.assertEqual((miyabi.gear[0].subs[0].name, miyabi.gear[0].subs[0].rolls), ("CRIT DMG", 4))
        self.assertEqual(miyabi.gear[0].subs[0].value, "19.2%")
        self.assertEqual(miyabi.set_bonuses, ["4pc Branch & Blade Song", "2pc Woodpecker Electro"])
        self.assertEqual(miyabi.weapon.name, "Fusion Compiler")

    def test_wengine_effect_for_phase(self):
        # Shape of Hakushin's per-phase W-Engine talents, as cached by Assets.
        effects = {"14118": {
            "1": {"name": "Frostbite", "desc": "Increases ATK by <color=#2BAD00>12%</color>.\\nStacks up to 3 times."},
            "5": {"name": "Frostbite", "desc": "Increases ATK by <color=#2BAD00>24%</color>.\\nStacks up to 3 times."},
        }}
        self.assets.data["zzz_weapon_effects"] = effects
        try:
            data = fixture("zzz_live.json")
            miyabi = zenless.parse_profile(self.assets, "1300003409", data).characters[3]
            self.assertEqual(miyabi.weapon.effect_name, "Frostbite")
            self.assertEqual(miyabi.weapon.effect, "Increases ATK by 12%.\nStacks up to 3 times.")
            data["PlayerInfo"]["ShowcaseDetail"]["AvatarList"][3]["Weapon"]["UpgradeLevel"] = 5
            miyabi = zenless.parse_profile(self.assets, "1300003409", data).characters[3]
            self.assertIn("24%", miyabi.weapon.effect)
            # No cached effect for a W-Engine: nothing shown, no error.
            anby = zenless.parse_profile(self.assets, "1300003409", data).characters[0]
            self.assertIsNone(anby.weapon.effect)
        finally:
            self.assets.data["zzz_weapon_effects"] = {}

    def test_live_embeds_fit_discord_limits(self):
        from bot.embeds import build_embed

        profile = zenless.parse_profile(self.assets, "1300003409", fixture("zzz_live.json"))
        for build in profile.characters:
            with self.subTest(character=build.name):
                embed = build_embed(profile, build, show_effect=True)
                self.assertLessEqual(len(embed), 6000)
                self.assertTrue(all(len(f.value) <= 1024 for f in embed.fields))

    def test_element_fallback(self):
        self.assertEqual(zenless._element(["ZhenZhenAssault", "Physics"]), "Physical")
        self.assertEqual(zenless._element(["Wind"]), "Wind")
        self.assertEqual(zenless._element(["Lumen"]), "Lumen")


class _FakeResponse:
    def __init__(self, body):
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.body is None:
            raise RuntimeError("HTTP 404")

    async def json(self, content_type=None):
        return self.body


class _FakeSession:
    def __init__(self, routes):
        self.routes, self.requested = routes, []

    def get(self, url):
        self.requested.append(url)
        return _FakeResponse(self.routes.get(url))


class ZenlessEffectsRefreshTest(unittest.TestCase):
    def test_caches_new_wengines_only(self):
        import asyncio
        import tempfile

        from bot.assets import HAKUSHIN

        with tempfile.TemporaryDirectory() as tmp:
            assets = Assets(tmp)
            (Path(tmp) / "zzz").mkdir()
            (Path(tmp) / "zzz" / "weapon_effects.json").write_text('{"14102": {"1": {"name": "Old", "desc": "x"}}}')
            session = _FakeSession({
                HAKUSHIN + "manifest.json": {"zzz": {"live": "2.3", "latest": "2.4"}},
                HAKUSHIN + "zzz/2.3/weapon.json": {"14102": {}, "14118": {}, "13101": {}},
                HAKUSHIN + "zzz/2.3/en/weapon/14118.json": {"talents": {"1": {"name": "Frostbite", "desc": "ATK +12%"}}},
            })
            asyncio.run(assets._refresh_zzz_effects(session))
            assets.load()
            effects = assets.data["zzz_weapon_effects"]
            self.assertEqual(effects["14102"]["1"]["name"], "Old")  # cached, not refetched
            self.assertEqual(effects["14118"]["1"]["desc"], "ATK +12%")
            self.assertNotIn("13101", effects)  # failed download is skipped, retried next refresh
            self.assertNotIn(HAKUSHIN + "zzz/2.3/en/weapon/14102.json", session.requested)

            # Hakushin unreachable: keep the cache, no exception.
            asyncio.run(assets._refresh_zzz_effects(_FakeSession({})))
            assets.load()
            self.assertIn("14118", assets.data["zzz_weapon_effects"])


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


class EmbedTest(unittest.TestCase):
    """Builds the Discord embed and command payloads (needs discord.py installed)."""

    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.profile = genshin.parse_profile(cls.assets, "618285856", fixture("genshin.json"))

    def test_genshin_embed_fits_discord_limits(self):
        from bot.embeds import build_embed

        for build in self.profile.characters:
            with self.subTest(character=build.name):
                embed = build_embed(self.profile, build, show_effect=True)
                self.assertLessEqual(len(embed), 6000)
                self.assertLessEqual(len(embed.fields), 25)
                self.assertTrue(all(len(f.value) <= 1024 for f in embed.fields))
        ayaka = build_embed(self.profile, self.profile.characters[0]).to_dict()
        self.assertEqual(ayaka["title"], "Kamisato Ayaka")
        self.assertEqual(ayaka["description"], "★★★★★ · Cryo · Lv. 90 · C2")
        names = [f["name"] for f in ayaka["fields"]]
        # Two equal stat columns, both titled (an empty title shows as a blank row on phones),
        # no talents, and the set bonuses come last, under the artifact pieces.
        self.assertEqual(names[:3], ["Stats", "Stats", "Weapon"])
        left, right = (ayaka["fields"][i]["value"].count("\n") + 1 for i in (0, 1))
        self.assertIn(left - right, (0, 1))
        self.assertNotIn("Talents", names)
        self.assertEqual(names[-1], "Artifacts")
        self.assertIn("• HP **", ayaka["fields"][0]["value"])
        self.assertNotIn("```", ayaka["fields"][1]["value"])

    def test_slash_command_payload(self):
        import discord
        from discord import app_commands

        from bot.main import make_claim_command, make_command

        tree = app_commands.CommandTree(discord.Client(intents=discord.Intents.none()))
        tree.add_command(make_command("genshin"))
        tree.add_command(make_claim_command("genshin"))
        payload = tree.get_command("genshin").to_dict(tree)
        # Character first so the UID can be left out when the caller has claimed one.
        self.assertEqual([o["name"] for o in payload["options"]], ["character", "uid"])
        self.assertTrue(payload["options"][0]["autocomplete"])
        self.assertTrue(payload["options"][0]["required"])
        self.assertFalse(payload["options"][1].get("required", False))
        self.assertLessEqual(len(payload["options"][1]["description"]), 100)
        claim = tree.get_command("genshin-claim").to_dict(tree)
        self.assertEqual([o["name"] for o in claim["options"]], ["uid"])


def weapon_field(embed) -> str:
    return next(f.value for f in embed.fields if f.name in ("Weapon", "Light Cone", "W-Engine"))


class WeaponEffectTest(unittest.TestCase):
    """Genshin weapon passives from genshin-db, rendered in the embed (no network)."""

    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()

    def setUp(self):
        self.profile = genshin.parse_profile(self.assets, "618285856", fixture("genshin_live.json"))

    def fill_from_cache(self, files: dict[str, dict]) -> None:
        import asyncio
        import tempfile

        from bot.gi_weapon_effects import GenshinWeaponEffects

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "gi" / "weapon_effects"
            folder.mkdir(parents=True)
            (folder / "_index.json").write_text(json.dumps({"Skyward Harp": "skywardharp"}))
            for name, data in files.items():
                (folder / f"{name}.json").write_text(json.dumps(data))
            asyncio.run(GenshinWeaponEffects(None, tmp).fill(self.profile))

    def test_passive_uses_the_weapons_refinement(self):
        self.fill_from_cache({
            "skywardharp": {
                "effectName": "Echoing Ballad",
                **{f"r{r}": {"description": f"Increases CRIT DMG by {15 + 5 * r}%."} for r in range(1, 6)},
            },
            "freedomsworn": {"effectName": "Revolutionary Chorale", "r1": {"description": "x" * 2000}},
        })
        harp = self.profile.characters[0].weapon  # Amber's Skyward Harp is R2
        self.assertEqual((harp.effect_name, harp.effect), ("Echoing Ballad", "Increases CRIT DMG by 25%."))
        # Weapons the cache doesn't have stay without an effect instead of failing the lookup.
        # (No session, so nothing is downloaded.)
        self.assertIsNone(self.profile.characters[2].weapon.effect)

        from bot.embeds import build_embed

        # Hidden until "Show Weapon effect" is pressed.
        self.assertNotIn("Echoing Ballad", weapon_field(build_embed(self.profile, self.profile.characters[0])))
        amber = weapon_field(build_embed(self.profile, self.profile.characters[0], show_effect=True))
        self.assertTrue(amber.endswith("> **Echoing Ballad**\n> Increases CRIT DMG by 25%."))
        bennett = weapon_field(build_embed(self.profile, self.profile.characters[1], show_effect=True))
        self.assertLessEqual(len(bennett), 1024)
        self.assertTrue(bennett.endswith("…"))

    def test_long_effect_never_pushes_embed_over_the_limit(self):
        from bot.embeds import EMBED_LIMIT, build_embed
        from bot.models import Stat

        build = self.profile.characters[0]
        build.weapon.effect_name, build.weapon.effect = "Long", "y" * 900
        # Fill the embed to just under the limit without the effect.
        build.notes = ["n" * 2000]
        for piece in build.gear:
            piece.subs = [Stat("s" * 100, "v" * 100) for _ in range(3)]
        build.weapon.effect = None
        without = len(build_embed(self.profile, build, show_effect=True))
        build.weapon.effect = "y" * 900
        self.assertLess(without, EMBED_LIMIT - 100)
        self.assertGreater(without + 900, EMBED_LIMIT)
        embed = build_embed(self.profile, build, show_effect=True)
        self.assertLessEqual(len(embed), EMBED_LIMIT)
        self.assertIn("> **Long**\n> yyy", weapon_field(embed))


class StarRailResFallbackTest(unittest.TestCase):
    """Characters newer than Enka's store get their data from StarRailRes instead."""

    def test_starrailres_data_gives_the_same_stats_as_the_store(self):
        assets = load_assets()
        data = fixture("hsr_live.json")
        before = {b.name: b.stats for b in starrail.parse_profile(assets, "800069903", data).characters}
        # Forget everything the store knows about these characters, light cones and sets.
        meta = assets.data["hsr_meta"]
        for info in data["detailInfo"]["avatarDetailList"]:
            cid = str(info["avatarId"])
            assets.data["hsr_characters"].pop(cid)
            meta["avatar"].pop(cid)
            for pid in [p for p in meta["tree"] if p.startswith((cid, "1" + cid))]:
                meta["tree"].pop(pid)
            if info.get("equipment"):
                tid = str(info["equipment"]["tid"])
                assets.data["hsr_weapons"].pop(tid, None)
                meta["equipment"].pop(tid, None)
                meta["equipmentSkill"].pop(tid, None)
        meta["relic"]["setSkill"].clear()
        assets._fill_hsr_gaps()
        after = starrail.parse_profile(assets, "800069903", data).characters
        self.assertEqual({b.name: b.stats for b in after}, before)

    def test_new_character_gets_a_name(self):
        assets = load_assets()
        data = fixture("hsr_live.json")
        data["detailInfo"]["avatarDetailList"][0]["avatarId"] = 1504  # Ashveil, not in Enka's store
        ashveil = starrail.parse_profile(assets, "800069903", data).characters[0]
        self.assertEqual((ashveil.name, ashveil.element), ("Ashveil", "Lightning"))
        self.assertNotEqual(stats(ashveil)["HP"], "0")
        self.assertIn("Ashveil", assets.character_names("hsr"))
