import io
import unittest

from PIL import Image

import records_fakes as F
from bot import records as R
from bot.models import CharacterBuild, Weapon
from bot.records_card import W, draw_records


def build(cid, cons, refinement):
    return CharacterBuild("hsr", str(cid), "", 80, 5, "", cons, None, [], [], Weapon("", 80, refinement, 5), [], [])


class ModesTest(unittest.TestCase):
    def test_modes_in_the_order_typed(self):
        self.assertEqual(R.parse_modes("hsr", "pf moc"), (["pf", "moc"], []))
        self.assertEqual(R.parse_modes("zzz", "DA, sd"), (["da", "sd"], []))
        self.assertEqual(R.parse_modes("genshin", "it abyss"), (["theater", "abyss"], []))

    def test_nothing_typed_means_every_mode(self):
        self.assertEqual(R.parse_modes("hsr", None)[0], ["moc", "pf", "apoc", "aa"])
        self.assertEqual(R.parse_modes("zzz", "all")[0], ["sd", "da"])

    def test_unknown_words_are_reported(self):
        self.assertEqual(R.parse_modes("hsr", "moc sd"), (["moc"], ["sd"]))

    def test_copies_label(self):
        self.assertEqual(R.copies_label("hsr", R.Member("1", None, copies=2, weapon_copies=1)), "E2S1")
        self.assertEqual(R.copies_label("genshin", R.Member("1", None, copies=0)), "C0")
        self.assertEqual(R.copies_label("zzz", R.Member("1", None, copies=6, weapon_copies=1)), "M6W1")


class ReadersTest(unittest.TestCase):
    def test_memory_of_chaos(self):
        rec = R.hsr_moc(F.moc())
        self.assertEqual(dict(rec.headline), {"Stars": "36 / 36", "Starward": "3", "Cycles": "7"})
        self.assertEqual([t.label for t in rec.teams], ["Node 1", "Node 2", "Starward"])
        self.assertEqual(rec.teams[0].members[0].copies, 2)

    def test_two_nodes_without_starward(self):
        data = F.pf()
        data.floors[0].node_3 = None
        self.assertEqual([t.label for t in R.hsr_pf(data).teams], ["Node 1", "Node 2"])

    def test_starward_shown_whenever_it_was_played(self):
        self.assertEqual(dict(R.hsr_pf(F.pf()).headline)["Starward"], "2")
        self.assertEqual(dict(R.hsr_apoc(F.apoc()).headline)["Starward"], "0")  # played, no stars earned
        data = F.pf()
        data.floors[0].node_3, data.starward_stars = None, 0
        self.assertNotIn("Starward", dict(R.hsr_pf(data).headline))

    def test_scores(self):
        self.assertEqual(dict(R.hsr_pf(F.pf()).headline)["Score"], "114,632")
        self.assertEqual(R.hsr_apoc(F.apoc()).teams[1].chips, [("score", "3,720")])
        self.assertNotIn("Floor", dict(R.hsr_apoc(F.apoc()).headline))  # the season line already names it

    def test_anomaly_arbitration_knights_then_king(self):
        rec = R.hsr_aa(F.aa())
        self.assertEqual([t.label for t in rec.teams], ["Knight I", "Knight II", "Knight III", "Plight"])
        self.assertEqual([t.enemies[0].name for t in rec.teams],  # HoYoLAB's names until the game data has them
                         ["Wolf Knight", "Lion Knight", "Stag Knight", "Sovereign of Thrones"])
        self.assertEqual([t.key for t in rec.teams], ["1|K1", "2|K2", "3|K3", ":plight|PLIGHT"])
        self.assertEqual(rec.teams[3].left, [("Cycles", "4")])
        self.assertTrue(rec.teams[3].plight)
        self.assertEqual(dict(rec.headline), {"Stars": "9", "Cycles": "7"})  # the knights only
        self.assertEqual([t.stage for t in rec.teams], ["", "", "", "King"])

    def test_zzz_ranking(self):
        sd, da = R.zzz_sd(F.sd()), R.zzz_da(F.da())
        self.assertEqual(dict(sd.headline)["Top"], "4.21%")
        self.assertEqual(dict(da.headline)["Top"], "2.8%")
        self.assertEqual(sd.teams[0].chips, [("rating", "S"), ("score", "31,890"), ("time", "1:44")])
        self.assertEqual((sd.season_id, sd.teams[2].key), ("62059", "62059053"))  # to look the bosses up by
        self.assertEqual(len(da.teams), 4)
        self.assertEqual((sd.teams[0].bangboo.rarity, sd.teams[1].bangboo), (5, None))
        self.assertEqual(da.teams[0].bangboo.level, 60)
        self.assertEqual((da.teams[3].stage, da.teams[3].label), ("Adversity Mode", "Adversity"))
        self.assertEqual(da.teams[3].enemies, [R.Enemy("Notorious - Miasma Priest")])  # HoYoLAB's, until the game data's
        self.assertEqual([t.key for t in da.teams], ["name:notoriousdeadendbutcher|1", "name:notoriousmarionette|2",
                                                     "name:notoriouspompey|3", "adversity-name:notoriousmiasmapriest|adversity"])
        self.assertEqual((da.season_id, da.starts), ("", "2026-10-13"))  # the fakes have no zone id: found by the day
        self.assertEqual((da.teams[3].left, da.teams[3].right), ([("Stars", "2/3")], [("Top", "0.16%")]))
        self.assertEqual(dict(da.headline)["Score"], "60,120")

    def test_genshin(self):
        self.assertEqual(len(R.gi_abyss(F.abyss()).teams), 6)
        self.assertEqual([t.label for t in R.gi_theater(F.theater()).teams], ["Act 9", "Act 10"])
        self.assertEqual(R.gi_stygian(F.stygian()).teams[0].members[0].copies, 2)

    def test_no_runs(self):
        data = F.moc()
        data.has_data = False
        self.assertIn("No Memory of Chaos runs", R.hsr_moc(data).empty)

    def test_weapon_copies_come_from_builds(self):
        rec = R.hsr_moc(F.moc())
        R.fill_copies([rec], [build(1407, 2, 1)])
        self.assertEqual(R.copies_label("hsr", rec.teams[0].members[0]), "E2S1")
        self.assertEqual(R.copies_label("hsr", rec.teams[0].members[1]), "E0")  # weapon unknown

    def test_outfit_from_builds(self):
        import dataclasses
        rec = R.hsr_moc(F.moc())
        R.fill_copies([rec], [dataclasses.replace(build(1407, 2, 1), outfit_icon="outfit.png")])
        self.assertEqual(rec.teams[0].members[0].icon_url, "outfit.png")

    def test_season_dates(self):
        self.assertEqual(R.hsr_moc(F.moc()).season, "Lupine Moon · 6 Oct – 17 Nov")
        self.assertEqual(R.gi_abyss(F.abyss()).season, "Floor 12 · 9 / 9★ · 16 Sep – 16 Oct")
        self.assertEqual(R.zzz_da(F.da()).season, "13 Oct – 27 Oct")
        self.assertEqual(R.gi_theater(F.theater()).season, "1 Oct – 1 Nov")
        # An Asia 4:00 reset is 20:00 UTC the day before, and still shows as its own day
        self.assertEqual(R._dates(1760126400, 1762718400), "11 Oct – 10 Nov")  # 2025-10-10/11-09 20:00 UTC
        data = F.stygian()
        del data[0].season.start_at
        self.assertEqual(R.gi_stygian(data).season, "Season 3")  # no dates: just the name


class DrawTest(unittest.TestCase):
    def test_draws_every_game(self):
        for game, recs in (
            ("hsr", [R.hsr_moc(F.moc()), R.hsr_aa(F.aa()), R.Record("pf", "Pure Fiction", empty="No runs.")]),
            ("zzz", [R.zzz_sd(F.sd()), R.zzz_da(F.da())]),
            ("genshin", [R.gi_abyss(F.abyss())]),
        ):
            img = Image.open(io.BytesIO(draw_records(game, "800069903", recs, {})))
            self.assertEqual(img.width, W)
            self.assertGreater(img.height, 300)

    def test_boss_art_and_medal_pictures(self):
        rec = R.hsr_aa(F.aa())
        rec.teams[3].art, rec.medal = "boss.png", "medal.png"
        pics = {"boss.png": Image.new("RGBA", (300, 400), (200, 40, 40, 255)), "medal.png": Image.new("RGBA", (64, 64), (250, 200, 60, 255))}
        img = Image.open(io.BytesIO(draw_records("hsr", "800069903", [rec], pics)))
        self.assertEqual(img.width, W)

    def test_every_rating_plate(self):
        from bot import card, record_icons
        card.FONTS = card.FONTS or card.Fonts()
        for letter in ("S+", "S", "A", "B"):
            self.assertEqual(record_icons.rating(letter, 24, card.FONTS.main).height, 24)


if __name__ == "__main__":
    unittest.main()


class ZzzDashboardTest(unittest.TestCase):
    def test_top_percent_reads_as_a_number(self):
        from bot.records_zzz import _percent
        self.assertEqual(_percent("0.84%"), 0.84)
        self.assertEqual(_percent("-"), 100.0)

    def test_score_tiers_per_mode(self):
        from bot.records_zzz import score_tier
        self.assertEqual([score_tier("sd", v) for v in ("51,000", "25,000", "24,999")], ["platinum", "gold", "purple"])
        self.assertEqual([score_tier("da", v) for v in ("65,000", "20,000", "14,000", "13,999")],
                         ["platinum", "gold", "purple", "blue"])


ICONS = "Assets/NapResources/UI/Sprite/A1DynamicLoad/IconBossGeneral/UnPacker/"
CARDS = "UI/Sprite/A1DynamicLoad/BossCard/UnPacker/BossCardLv04/"


def _zzz_monster(mid, name, image, hp):
    return {"id": mid, "name": name, "image": CARDS + image, "stats": {"hp": hp, "attack": 1}}


def _shiyu(zone, boss_hp=50615124.48):
    """A Shiyu Defense season file as Hakushin writes it: a frontier, then the final one's three battles."""
    battle = lambda n, icon, monsters: {"name": f"Room {n}", "stage_num": 5, "monster_level": 70, "goal_type": 2,  # noqa: E731
                                        "layer_room": {f"{zone}05{n}": {"monster_icon": ICONS + icon, "monster_list": monsters}}}
    return {"id": zone, "zone": {
        f"{zone}04": {"name": "Fourth Frontier", "stage_num": 4, "monster_level": 65, "goal_type": 0, "layer_room": {
            "1": {"monster_icon": ICONS + "IconMonster_MiasmaTerrorBird.png",
                  "monster_list": {"31262": _zzz_monster(1, "Terror Bird", "Monster_MiasmaTerrorBird.png", 9)}}}},
        f"{zone}05": {"name": "", "stage_num": 5, "monster_level": 0, "goal_type": 3, "layer_room": {}},
        f"{zone}051": battle(1, "IconMonster_Sentinel.png", {
            "31303": _zzz_monster(20026, "Miasmic - Frenzied Maniac", "Monster_MiasmaFrenziedManiac.png", 4276096.11),
            "31531": _zzz_monster(30048, "Airspace Sentinel", "Monster_Sentinel.png", boss_hp)}),
        f"{zone}052": battle(2, "", {  # no icon: the one with the most HP
            "31491": _zzz_monster(20034, "Mushussu", "Monster_Mushussu.png", 10698745),
            "31214": _zzz_monster(300372, "Miasmic - Doppelganger - The Defector", "Monster_X.png", 52688086)}),
    }}


def _assault(regular, hard):
    """A Deadly Assault season file: Adversity Mode (zone type 1002), then the three regular bosses (1001)."""
    def zone(n, name, vid, mid, image, hp):
        return {"name": name, "stage_num": n, "monster_level": 70, "goal_type": 2, "layer_room": {
            "r": {"monster_icon": ICONS + "Icon" + image, "monster_list": {vid: _zzz_monster(mid, name, image, hp)}}}}
    return {"id": 690501, "modes": [
        {"id": 690502, "zone_type": 1002, "zone": {"69050201": zone(1, *hard)}},
        {"id": 690501, "zone_type": 1001, "zone": {f"6905010{i}": zone(i, *b) for i, b in enumerate(regular, 1)}}]}


class ZzzEnemiesTest(unittest.TestCase):
    KUSARIKKU = ("Kusarikku", "31711", 40010, "Monster_Larval.png", 26755094.34)
    REVENANT = ("Infernal Revenant", "31635", 30052, "Monster_SymbioticEtherealSinner.png", 22538010.33)
    PHAETHON = ("Phaethon of the Scorched Horizon", "31431", 40005, "Monster_Mutant.png", 23723285.715)
    GIRTABLULLU = ("Integrated - Girtablullu", "31662", 40009, "Monster_Girtablu_HC.png", 37045515.24)

    def test_shiyu_defense_final_battles_by_their_boss(self):
        from bot.zzz_enemies import season_bosses
        found = season_bosses("sd", _shiyu(62061))
        self.assertEqual(found.keys(), {"62061051", "62061052"})  # the final frontier's battles only
        self.assertEqual(found["62061051"], [{"id": 31531, "monster": 30048, "name": "Airspace Sentinel", "level": 70,
                                              "hp": 50615124, "art": "https://static.nanoka.cc/assets/zzz/Monster_Sentinel.webp"}])
        self.assertEqual(found["62061052"][0]["name"], "Miasmic - Doppelganger - The Defector")

    def test_deadly_assault_by_name_and_place(self):
        from bot.zzz_enemies import season_bosses
        found = season_bosses("da", _assault([self.KUSARIKKU, self.REVENANT, self.PHAETHON], self.GIRTABLULLU))
        self.assertEqual(found["2"][0]["name"], "Infernal Revenant")
        self.assertIs(found["name:kusarikku"][0], found["1"][0])
        self.assertEqual(found["adversity"][0]["hp"], 37045515)
        self.assertIn("adversity-name:integratedgirtablullu", found)
        self.assertNotIn("name:integratedgirtablullu", found)  # Adversity Mode's boss isn't a regular one
        rec = R.zzz_da(F.da())
        rec.teams[0].key = "name:nobodyknown|1"  # a name the game data doesn't know: by place
        rec.teams[1].key = "name:kusarikku|2"  # a known name first
        R.set_enemies(rec, found)
        self.assertEqual([t.enemies[0].name for t in rec.teams],
                         ["Kusarikku", "Kusarikku", "Phaethon of the Scorched Horizon", "Integrated - Girtablullu"])  # Adversity: by place
        self.assertEqual((rec.teams[0].enemies[0].level, rec.teams[0].enemies[0].hp), (70, 26755094))

    def test_seasons_found_and_ordered(self):
        from bot.zzz_enemies import earlier_seasons, find_season
        index = {"69040": {"live_begin": "2026-07-03 04:00:00"}, "69041": {"live_begin": "2026-07-17 04:00:00"},
                 "690421": {"live_begin": "2026-07-29 04:00:00"}, "690501": {"live_begin": "2026-11-20 04:00:00"},
                 "690511": {"begin": "2026-10-21 04:00:00"}}  # a beta's: after the live ones, whatever its date
        self.assertEqual(find_season(index, "690501"), "690501")
        self.assertEqual(find_season(index, 69050), "690501")
        self.assertEqual(find_season(index, "", "2026-11-20"), "690501")
        self.assertEqual(find_season(index, "1", "2026-01-01"), "")
        self.assertEqual(earlier_seasons(index, "690501"),
                         [("690421", "29 Jul · v3.1"), ("69041", "17 Jul · v3.0"), ("69040", "3 Jul · v3.0")])
        self.assertEqual(earlier_seasons({"62060": {"begin": "2026-10-30 04:00:00"}, "62061": {}, "620631": {}}, "62061"),
                         [("62060", "30 Oct · v3.3")])

    def test_game_version_by_date(self):
        from bot.zzz_enemies import game_version, season_label
        self.assertEqual(game_version("2026-10-09"), "3.2")
        self.assertEqual(game_version("2026-10-21"), "3.3")  # its first day
        self.assertEqual(game_version("2025-09-03"), "2.1")
        self.assertEqual(game_version("2024-07-04 04:00:00"), "1.0")
        self.assertEqual(game_version("2024-07-03"), "")  # before release
        self.assertEqual(game_version("2027-03-01"), "")  # past the last known version: not guessed
        self.assertEqual(season_label("2026-11-06"), "6 Nov · v3.3")
        self.assertEqual(season_label("2023-01-01"), "1 Jan")  # the date alone
        self.assertEqual(season_label(""), "")

    def test_hp_change_since_the_boss_last_came(self):
        from bot.zzz_enemies import add_changes, season_bosses, season_slots
        now = season_bosses("sd", _shiyu(62061))
        before = season_slots("sd", _shiyu(62060, boss_hp=40492099.58))
        self.assertEqual(before.keys(), {"final"})
        add_changes("sd", now, [("62060", "30 Oct", before)])
        sentinel, defector = now["62061051"][0], now["62061052"][0]
        self.assertEqual((round(sentinel["change"], 2), sentinel["prev_season"]), (25.0, "30 Oct"))
        self.assertAlmostEqual(defector["change"], 0)
        # Deadly Assault: regular bosses with regular bosses, Adversity Mode's with its own; the latest season wins
        found = season_bosses("da", _assault([self.KUSARIKKU, self.REVENANT, self.PHAETHON], self.GIRTABLULLU))
        older = season_slots("da", _assault([(*self.KUSARIKKU[:4], 22124405), self.PHAETHON, self.PHAETHON],
                                            ("Kusarikku", "31711", 40010, "Monster_Larval.png", 1)))
        newer = {"boss": [{"id": 1, "monster": 30052, "name": "Infernal Revenant", "hp": 19464645}]}
        add_changes("da", found, [("690491", "6 Nov", newer), ("690471", "9 Oct", older)])
        self.assertAlmostEqual(found["1"][0]["change"], 20.9302, 3)  # same variant, a season further back
        self.assertEqual(found["name:kusarikku"][0]["prev_season"], "9 Oct")  # the same boss under its name
        self.assertAlmostEqual(found["2"][0]["change"], 15.7895, 3)  # same monster, another variant
        self.assertNotIn("change", found["adversity"][0])  # never in Adversity Mode before
        rec = R.zzz_da(F.da())
        R.set_enemies(rec, found)
        self.assertEqual((round(rec.teams[0].enemies[0].change, 1), rec.teams[0].enemies[0].prev_season), (20.9, "9 Oct"))

    def test_cached_lookup(self):
        import asyncio
        import tempfile

        from bot.zzz_enemies import ZzzEnemies

        files = {"manifest.json": {"zzz": {"live": "3.3", "latest": "3.4"}},
                 "zzz/3.3/boss.json": {"690491": {"live_begin": "2026-11-06"}, "690501": {"live_begin": "2026-11-20"}},
                 "zzz/3.3/en/boss/690501.json": _assault([self.KUSARIKKU, self.REVENANT, self.PHAETHON], self.GIRTABLULLU),
                 "zzz/3.3/en/boss/690491.json": _assault([self.REVENANT, self.REVENANT, self.REVENANT], self.GIRTABLULLU)}
        asked = []

        class Resp:
            def __init__(self, body):
                self.status, self.body = (200 if body is not None else 404), body
            async def __aenter__(self): return self  # noqa: E301,E704
            async def __aexit__(self, *a): return False  # noqa: E301,E704
            async def json(self, content_type=None): return self.body  # noqa: E301,E704

        class Session:
            def get(self, url):
                asked.append(url)
                return Resp(files.get(url.split("static.nanoka.cc/")[1]))

        with tempfile.TemporaryDirectory() as tmp:
            found = asyncio.run(ZzzEnemies(tmp).enemies(Session(), "da", "69050", "2026-11-20"))
            self.assertAlmostEqual(found["adversity"][0]["change"], 0)
            self.assertNotIn("change", found["1"][0])  # Kusarikku: never before
            again = asyncio.run(ZzzEnemies(tmp).enemies(Session(), "da", "69050"))  # from the file, nothing asked
            self.assertEqual(again["2"][0]["hp"], 22538010)
            self.assertEqual(len([u for u in asked if "690501" in u]), 1)

    def test_draws_with_bosses(self):
        pic = Image.new("RGBA", (484, 668), (200, 40, 40, 255))
        sd, da = R.zzz_sd(F.sd()), R.zzz_da(F.da())
        for rec in (sd, da):
            for team in rec.teams:
                team.enemies = [R.Enemy("Lord of Saṃvartasthāyi", "boss.png", 70, 52688086)]
            rec.teams[0].enemies[0].change, rec.teams[0].enemies[0].prev_season = -8.5, "30 Oct"
            rec.teams[1].enemies = [R.Enemy("", "gone.png")]  # HoYoLAB's picture only, and it didn't load
            rec.teams[2].enemies = []  # not known at all
            img = Image.open(io.BytesIO(draw_records("zzz", "1300000001", [rec], {"boss.png": pic})))
            self.assertEqual(img.width, W)
            self.assertGreater(img.height, 800, rec.mode)

    def test_hp_change_written_and_coloured(self):
        from bot import card, card_zzz
        from bot.records_zzz import DOWN, SAME, UP, _change
        card.FONTS = card.FONTS or card.Fonts()
        f = card_zzz._rubik(16, 700)
        self.assertEqual(_change(12.5, f), ("+12.5%", UP))
        self.assertEqual(_change(-8, f)[1], DOWN)
        self.assertEqual(_change(0.04, f), ("±0%", SAME))


class HsrPerfectTest(unittest.TestCase):
    def test_max_scores_and_zero_cycles_are_perfect(self):
        from bot.records_hsr import _perfect
        self.assertTrue(_perfect("pf", "score", "40,000"))
        self.assertFalse(_perfect("pf", "score", "40,000", total=True))
        self.assertTrue(_perfect("pf", "score", "120,000", total=True))
        self.assertTrue(_perfect("apoc", "score", "4,000"))
        self.assertTrue(_perfect("apoc", "score", "3,850"))
        self.assertFalse(_perfect("apoc", "score", "3,849"))
        self.assertTrue(_perfect("apoc", "score", "11,550", total=True))
        self.assertTrue(_perfect("moc", "cycles", "0"))
        self.assertFalse(_perfect("aa", "cycles", "2"))


def _stage(level, group, elite, *waves):
    """A made-up Hakushin stage: its level, HP curve, elite group and waves of monster ids."""
    return {"level": level, "hard_level_group": group, "elite_group": elite,
            "monster_list": [{f"monster{i}": m for i, m in enumerate(w)} for w in waves]}


def _value(hp_base, *children, bars=None, phases=None):
    """A made-up monstervalue.json entry: (variant id, HPModifyRatio, its own EliteGroup) per variant."""
    out = {"HPBase": hp_base, "child": [{"Id": c, "HPModifyRatio": r, "EliteGroup": e} for c, r, e in children]}
    if bars:
        out["MaxMonsterPhase"] = bars
    if phases:
        out["PhaseList"] = [{"PhaseNum": i + 1, "PhaseMaxHPRatio": r} for i, r in enumerate(phases)]
    return out


class HsrEnemiesTest(unittest.TestCase):
    """HP worked out as hsr.nanoka.cc does it. The tables are made up in Hakushin's shapes, with the real rows the
    worked examples use (each matched against the site's own numbers)."""

    @classmethod
    def setUpClass(cls):
        from bot.hsr_enemies import Tables
        cls.TABLES = Tables(
            [{"HardLevelGroup": 1, "Level": 90, "HPRatio": 236.534716}, {"HardLevelGroup": 3, "Level": 95, "HPRatio": 375.438496},
             {"HardLevelGroup": 1, "Level": 85, "HPRatio": 188.263594},
             {"HardLevelGroup": 3, "Level": 120, "HPRatio": {"Value": 1938.763448}}],  # the raw files' {"Value": x} too
            [{"EliteGroup": 173, "HPRatio": 9.6}, {"EliteGroup": 164, "HPRatio": 6.5}, {"EliteGroup": 169, "HPRatio": 8},
             {"EliteGroup": 57, "HPRatio": 1}, {"EliteGroup": 2, "HPRatio": 1.7}],
            [{"EliteGroup": 349, "HPRatio": 8}],  # InfiniteEliteGroup.json: Anomaly Arbitration's wave groups
            {"3024013": _value(5812.5, (302401304, 1, 1), bars=2),
             "3024012": _value(5812.5, (302401204, 1, 1)),
             "4034014": _value(7672.5, (4034014, 1, 1)),
             "8015030": dict(_value(14880, (8015030, 1, 1), (801503006, 0.375, 1), bars=3),  # as Hakushin writes it now
                             PhaseList=[{"phase_num": i + 1, "phase_max_hp_ratio": r} for i, r in enumerate((1.0, 1.0, 1.9))]),
             "5034010": _value(2092.5, (5034010, 1, 2), bars=2),
             "2034010": _value(2557.5, (2034010, 1, 1), bars=2, phases=[1, 1.5])})
        cls.NAMES = {"3024013": {"en": "Silver Knight", "icon": "SpriteOutput/MonsterFigure/Monster_3024010.png"},
                     "8015030": {"en": "Lord of <i>Ash</i>", "icon": "SpriteOutput/MonsterFigure/Monster_8015030.png"},
                     "2034010": {"en": "Warhead"}, "5034010": {"en": "Yabuli"}}

    def test_hp_as_the_site_works_it_out(self):
        hp = lambda *a: self.TABLES.hp(*a)["hp"]  # noqa: E731
        # Silver Knight, Apocalyptic Shadow 3022 Starward: 5812.5 x 1 x 9.6 x 236.534716 = 13,198,637 (site: same)
        self.assertEqual(hp(302401304, _stage(90, 1, 173)), 13198637)
        self.assertEqual(self.TABLES.hp(302401304, _stage(90, 1, 173))["bars"], 2)  # the site: "x 2"
        # Flame Reaver, Pure Fiction 2027 floor 4: 7672.5 x 1 x 1 x 188.263594 x (1 + 45) = 66,444,812 (site: same)
        self.assertEqual(hp(4034014, _stage(85, 1, None), {"elite_group": 57, "param_list": [0.12, 45]}), 66444812)
        # Yabuli, Anomaly Arbitration 11 Knight I: 2092.5 x 1 x InfiniteEliteGroup[349] 8 x 375.438496 = 6,284,840
        self.assertEqual(hp(5034010, _stage(95, 3, None), {"elite_group": 349, "param_list": []}), 6284840)
        # Asat Pramad on Plight: 14880 x 0.375 x 8 x 1938.763448 = 86,546,400 (site: same)
        self.assertEqual(hp(801503006, _stage(120, 3, None), {"elite_group": 169}), 86546400)

    def test_the_sites_fallbacks(self):
        hp = lambda *a: self.TABLES.hp(*a)["hp"]  # noqa: E731
        # an elite group in neither table: the variant's own group (Yabuli's is 2, x1.7), then x1
        self.assertEqual(hp(5034010, _stage(95, 3, 999)), round(2092.5 * 1.7 * 375.438496))
        self.assertEqual(hp(2034010, _stage(95, 3, 999)), round(2557.5 * 375.438496))
        self.assertIsNone(self.TABLES.hp(1234567, _stage(95, 3, 1)))  # not in monstervalue.json
        self.assertEqual(hp(302401299, _stage(90, 1, 173)), 13198637)  # a variant not listed: the monster's own
        self.assertEqual(hp(5034010, _stage(95, 3, None), {"elite_group": 349, "param_list": [0, 3]}), round(2092.5 * 8 * 375.438496 * 4))
        # InfiniteEliteGroup is only for waves
        self.assertEqual(hp(5034010, _stage(95, 3, 349)), round(2092.5 * 1.7 * 375.438496))

    def test_memory_of_chaos_floor_by_id_or_number(self):
        from bot.hsr_enemies import floor_enemies
        season = [{"id": 5511, "event_id_list1": [_stage(92, 3, 164, [2034010])], "event_id_list2": [_stage(92, 3, 164, [2034010])]},
                  {"id": 5512, "event_id_list1": [_stage(95, 3, 164, [8012030, 2034010, 8012030], [2034010, 2034010])],
                   "event_id_list2": [_stage(95, 3, 164, [302401304])]},
                  {"id": 5513, "event_id_list": [_stage(90, 1, 173, [8012030], [302401304])]}]
        found = floor_enemies("moc", season, self.NAMES, self.TABLES, "5512")
        self.assertEqual(found.keys(), {"1", "2", "3"})
        self.assertEqual([(e["name"], e["level"]) for e in found["1"]], [("Warhead", 95)])  # the last wave, each kind once
        self.assertEqual(found["1"][0]["hp"], round(2557.5 * 375.438496 * 6.5))
        self.assertEqual((found["1"][0]["bars"], found["1"][0]["phases"]), (2, [1, 1.5]))  # bars of different size
        self.assertIsNone(found["1"][0]["art"])
        self.assertEqual((found["3"][0]["hp"], found["3"][0]["phases"]), (13198637, []))
        self.assertTrue(found["3"][0]["art"].endswith("/assets/hsr/monsterfigure/Monster_3024010.webp"))
        by_number = floor_enemies("moc", season, self.NAMES, self.TABLES, "9999", 2)  # an unknown id: the 2nd floor
        self.assertEqual(by_number["2"], found["2"])
        self.assertEqual(floor_enemies("moc", season, self.NAMES, self.TABLES, "9999").keys(), {"3"})

    def test_pure_fiction_takes_the_last_waves_elite_group_and_hp_bonus(self):
        from bot.hsr_enemies import floor_enemies
        ability = "FantasticStory_Wave_Ability_0001"
        stage = _stage(85, 1, None, [8012030], [8012030], [4034014])
        waves = {"2": {"elite_group": 57, "ability": ability, "param_list": [0.05, 9]},
                 "1": {"elite_group": 57, "ability": ability, "param_list": [0, 4]},
                 "3": {"elite_group": 57, "ability": ability, "param_list": [0.12, 45]}}
        season = {"level": [{"id": 20274, "event_id_list1": [stage], "infinite_list1": waves}]}
        self.assertEqual(floor_enemies("pf", season, self.NAMES, self.TABLES, "20274")["1"][0]["hp"], 66444812)

    def test_anomaly_arbitration_knights_and_the_king(self):
        from bot.hsr_enemies import floor_enemies
        from bot.records_hsr import _hp
        season = {"pre_level": [{"id": 1101, "event_id_list": [_stage(95, 3, None, [5034010])],
                                 "infinite_list": {"1": {"elite_group": 349, "param_list": []}}}],
                  "boss_level": {"id": 1104, "event_id_list": [_stage(100, 3, None, [801503006])]},
                  "boss_config": {"event_id_list": [_stage(120, 3, None, [801503006])], "infinite_list": {"9": {"elite_group": 169}}}}
        found = floor_enemies("aa", season, self.NAMES, self.TABLES)
        self.assertEqual(found["1101"], found["K1"])
        self.assertEqual(found["K1"][0]["hp"], 6284840)
        self.assertEqual((found["PLIGHT"][0]["hp"], found["PLIGHT"][0]["bars"]), (86546400, 3))
        self.assertEqual(found["PLIGHT"][0]["phases"], [1, 1, 1.9])  # the site: P1 86,546,400 / P2 86,546,400 / P3 164,438,160
        self.assertEqual(_hp(R.Enemy("a", hp=86546400, bars=3, phases=[1, 1, 1.9])), "86,546,400 / 86,546,400 / 164,438,160")
        self.assertEqual(found["PLIGHT"][0]["name"], "Lord of Ash")  # markup dropped
        rec = R.hsr_aa(F.aa())
        rec.teams[3].key = "1104:plight|PLIGHT"
        R.set_enemies(rec, {"K2": found["K1"], "PLIGHT": found["PLIGHT"]})
        self.assertEqual((rec.teams[1].enemies[0].name, rec.teams[1].enemies[0].level), ("Yabuli", 95))  # by place
        self.assertEqual((rec.teams[3].enemies[0].hp, rec.teams[3].enemies[0].bars), (86546400, 3))
        self.assertEqual(rec.teams[0].enemies[0].name, "Wolf Knight")  # not found: HoYoLAB's stays

    def test_hp_written_like_the_site(self):
        from bot.records_hsr import _hp
        self.assertEqual(_hp(R.Enemy("a", hp=6241196)), "6,241,196")
        self.assertEqual(_hp(R.Enemy("a", hp=6241196, bars=2)), "6,241,196 ×2")
        self.assertEqual(_hp(R.Enemy("a", hp=1000, bars=2, phases=[1, 1.5])), "1,000 / 1,500")

    def test_floor_numbers(self):
        from bot.hsr_enemies import base_id, floor_number
        self.assertEqual([floor_number(n) for n in ("Survival of the Fittest (XII)Starward Mode", "Pure Fiction (4)", "04", "(IX)")],
                         [12, 4, 4, 9])
        self.assertEqual((base_id(501402404), base_id(5014024)), (5014024, 5014024))

    def test_readers_note_the_floor_to_look_up(self):
        data = F.moc()
        data.season, data.floors[0].id = 1036, 5512
        rec = R.hsr_moc(data)
        self.assertEqual((rec.season_id, rec.floor_id, rec.floor_no), ("1036", "5512", 12))
        self.assertEqual([t.key for t in rec.teams], ["1", "2", "3"])
        self.assertEqual([t.label for t in rec.teams], ["Node 1", "Node 2", "Starward"])
        R.set_enemies(rec, {"1": [{"name": "Warhead", "art": "a", "level": 95, "hp": 6241196}]})
        self.assertEqual(rec.teams[0].enemies, [R.Enemy("Warhead", "a", 95, 6241196)])
        self.assertEqual(rec.teams[1].enemies, [])

    def test_apocalyptic_shadow_starts_with_hoyolabs_bosses(self):
        from types import SimpleNamespace as NS
        data = F.apoc()
        data.seasons[0].id, data.seasons[0].upper_boss = 3022, NS(name="The Conductor", icon="boss.png")
        rec = R.hsr_apoc(data)
        self.assertEqual(rec.teams[0].enemies, [R.Enemy("The Conductor", "boss.png")])
        self.assertEqual((rec.season_id, rec.floor_no), ("3022", 4))

    def test_hp_change_since_the_enemy_last_came(self):
        from bot.hsr_enemies import add_changes, hp_change
        now = {"1": [{"id": 302401304, "name": "Silver Knight", "hp": 1125, "bars": 2, "phases": []}],
               "2": [{"id": 4034014, "name": "Flame Reaver", "hp": 920, "bars": 1, "phases": []}],
               "3": [{"id": 8015030, "name": "Lord of Ash", "hp": 500, "bars": 1, "phases": []}]}
        history = [("3021", "Newer", {"floor": [{"id": 9999999, "name": "Someone Else", "hp": 1}]}),
                   ("3020", "Older", {"floor": [{"id": 302401399, "name": "Silver Knight", "hp": 1000, "bars": 2},  # same monster
                                                {"id": 1234567, "name": "Flame Reaver", "hp": 1000, "bars": 1}]}),  # same name
                   ("3015", "Oldest", {"floor": [{"id": 302401304, "name": "Silver Knight", "hp": 10, "bars": 2}],
                                       "starward": [{"id": 4034014, "name": "Flame Reaver", "hp": 1, "bars": 1}]})]
        add_changes("apoc", now, history)
        knight, reaver, lord = now["1"][0], now["2"][0], now["3"][0]
        self.assertEqual((knight["change"], knight["prev_season"], knight["prev_season_id"]), (12.5, "Older", "3020"))  # the latest
        self.assertEqual((reaver["change"], reaver["prev_season"]), (-8.0, "Older"))  # a drop
        self.assertNotIn("change", lord)  # starward only: never on a floor before
        self.assertIsNone(R.Enemy("x").change)
        # bars changed: all of them compared; unchanged: 0
        self.assertEqual(hp_change({"hp": 100, "bars": 3}, {"hp": 150, "bars": 2}), 0)
        self.assertEqual(hp_change({"hp": 100, "bars": 2, "phases": [1, 1.5]}, {"hp": 100, "bars": 1}), 150)
        self.assertIsNone(hp_change({"hp": 100}, {"hp": 0}))
        # Anomaly Arbitration: by place, any knight
        aa = {"K2": [{"id": 5034010, "name": "Yabuli", "hp": 110, "bars": 2}], "KING": [{"id": 8015030, "hp": 5}]}
        add_changes("aa", aa, [("9", "Past", {"knight": [{"id": 5034010, "name": "Yabuli", "hp": 100, "bars": 2}],
                                              "plight": [{"id": 8015030, "hp": 1}]})])
        self.assertAlmostEqual(aa["K2"][0]["change"], 10)
        self.assertNotIn("change", aa["KING"][0])  # the King isn't the King on Plight
        rec = R.hsr_aa(F.aa())
        R.set_enemies(rec, aa)
        self.assertEqual((rec.teams[1].enemies[0].change, rec.teams[1].enemies[0].prev_season), (10.0, "Past"))

    def test_voracity_corrosion(self):
        from bot.hsr_enemies import floor_enemies, voracity, voracity_extra
        from bot.records_hsr import CHANGE_H, _foes_h, FOE_H, VOR_H, _voracity
        lv2, lv3, lv4 = [0.4, 0.4, 1, 1, 0.72], [0.6, 0.8, 1, 3, 1.44], [0.77, 1.2, 1, 3, 1.8]  # monster_param
        invasion = {"level": 3, "maze_buff_param": [0.65, 0.3, 0.5, 1, 0.5], "monster_param": lv3,
                    "monster_list": [{"monster_id": 302401304, "param_list": []}, {"monster_id": 4062010, "param_list": [1, 0]}]}
        stage = dict(_stage(90, 1, 173, [302401304, 2034010]), invasion=invasion)
        self.assertEqual(voracity(302401304, stage), {"voracity": lv3, "corrosion": 3})  # monster_param, not the maze buff's
        self.assertEqual(voracity(2034010, stage), {})  # in the stage, but not corroded
        self.assertEqual(voracity(302401304, _stage(90, 1, 173)), {})  # no corrosion on the stage
        found = floor_enemies("moc", [{"id": 5513, "event_id_list": [stage]}], self.NAMES, self.TABLES)["3"]
        knight, warhead = found
        self.assertEqual((knight["hp"], knight["voracity"], knight["corrosion"]), (13198637, lv3, 3))  # HP as it was
        self.assertNotIn("voracity", warhead)
        # HealR x s_n / CR of the last bar's HP (Elation DMG, any other DMG): the community table for several bars
        for level, params, multi, single in ((2, lv2, (0.36, 0.36), (0.2, 0.2)), (3, lv3, (0.36, 1.08), (0.2, 0.6)),
                                             (4, lv4, (0.5625, 1.575), (0.375, 1.05))):
            with self.subTest(level=level):
                self.assertEqual(voracity_extra(1000000, 2, [], params, level), [(round(1e6 * s), s) for s in multi])
                self.assertEqual(voracity_extra(1000000, 1, [], params, level), [(round(1e6 * s), s) for s in single])
        self.assertEqual(voracity_extra(7258991, 2, [], lv3, 3), [(2613237, 0.36), (7839710, 1.08)])  # Judge of Oblivion
        plight = R.Enemy("a", hp=86546400, bars=3, phases=[1, 1, 1.9], voracity=lv4, corrosion=4)  # last bar 164,438,160
        self.assertEqual(_voracity(plight), ["+92,496,465 (56.25%)", "+258,990,102 (157.5%)"])
        self.assertEqual(_voracity(R.Enemy("a", hp=1000000, bars=2, voracity=lv2, corrosion=2)),
                         ["+360,000 (36%)", "+360,000 (36%)"])  # Lv 2: the same, still both lines
        self.assertEqual(_voracity(R.Enemy("a", hp=1000000, voracity=lv3, corrosion=3)),
                         ["+200,000 (20%)", "+600,000 (60%)"])  # one bar
        # Lv 1 and 2 have no Elation branch: p[2] for both
        self.assertEqual(voracity_extra(1000000, 2, [], [0.4, 0.4, 1, 3, 0.72], 2), [(360000, 0.36), (360000, 0.36)])
        self.assertEqual(_voracity(R.Enemy("a", hp=1000000)), [])
        rec = R.hsr_moc(F.moc())
        R.set_enemies(rec, {"1": found})
        self.assertEqual((rec.teams[0].enemies[0].voracity, rec.teams[0].enemies[0].corrosion), (lv3, 3))
        self.assertEqual(_foes_h(rec), FOE_H + 2 * VOR_H)  # two lines: other DMG and Elation
        rec.teams[1].enemies = [R.Enemy("b", hp=1, change=5.0)]  # the tallest stack sets the row: no slot is shared
        self.assertEqual(_foes_h(rec), FOE_H + 2 * VOR_H)
        rec.teams[0].enemies[0].change = 1.0
        self.assertEqual(_foes_h(rec), FOE_H + 2 * VOR_H + CHANGE_H)

    def test_earlier_seasons_newest_first(self):
        from bot.hsr_enemies import earlier_seasons, season_slots
        index = {"1035": {"en": "Last (1.0)"}, "1036": {"en": "Now"}, "1034": {"en": None}, "120": {"en": "Old mode"},
                 "1037": {"en": "Next"}}
        self.assertEqual(earlier_seasons(index, "1036", ({"1034": {"en": "Before"}},)),
                         [("1035", "Last"), ("1034", "Before")])
        self.assertEqual(earlier_seasons({"9": {"en": "Nine"}, "10": {"en": "Ten"}, "11": {}}, 11), [("10", "Ten"), ("9", "Nine")])
        self.assertEqual(earlier_seasons(index, "now"), [])
        season = [{"id": 5511, "event_id_list1": [_stage(92, 3, 164, [2034010])], "event_id_list2": [_stage(92, 3, 164, [5034010])]},
                  {"id": 5513, "event_id_list": [_stage(90, 1, 173, [302401304])]}]
        slots = season_slots("moc", season, self.NAMES, self.TABLES, 1)
        self.assertEqual([e["name"] for e in slots["floor"]], ["Warhead", "Yabuli"])
        self.assertEqual([e["name"] for e in slots["starward"]], ["Silver Knight"])
        self.assertEqual(season_slots("moc", season, self.NAMES, self.TABLES, 2).keys(), {"starward"})  # no 2nd floor then

    def test_hp_change_written_and_coloured(self):
        from bot import card, card_hsr
        from bot.records_hsr import DIM, DOWN, UP, _change
        card.FONTS = card.FONTS or card.Fonts()
        f = card_hsr._raj("Bold", 14)
        self.assertEqual(_change(12.5, f), ("(+12.5%)", UP))
        self.assertEqual(_change(-8, f)[1], DOWN)
        self.assertIn(_change(-8, f)[0], ("(−8.0%)", "(-8.0%)"))
        self.assertEqual(_change(0.04, f), ("(±0%)", DIM))
        self.assertEqual(_change(1234.5, f)[0], "(+1,234.5%)")


class HsrDrawTest(unittest.TestCase):
    def test_every_mode_draws_with_enemies(self):
        from bot.hsr_enemies import ELATION_ICON
        pic = Image.new("RGBA", (300, 500), (200, 40, 40, 255))
        for rec in (R.hsr_moc(F.moc()), R.hsr_pf(F.pf()), R.hsr_apoc(F.apoc()), R.hsr_aa(F.aa())):
            for i, team in enumerate(rec.teams):
                team.enemies = [R.Enemy("Lord of Saṃvartasthāyi, Asat Pramad", "boss.png", 120, 86546400, 3),
                                R.Enemy("Missing Picture", "gone.png", 95, 12345678, 2, [1, 1.25])][: 1 + i % 2]
            rec.teams[0].enemies[0].change, rec.teams[0].enemies[0].prev_season = 12.5, "A Long Season Name Over Its Screen"
            rec.teams[0].enemies[0].voracity, rec.teams[0].enemies[0].corrosion = [0.77, 1.2, 1, 3, 1.8], 4
            rec.teams[-1].enemies = []  # not known yet: an empty screen saying so
            img = Image.open(io.BytesIO(draw_records("hsr", "800069903", [rec], {"boss.png": pic, ELATION_ICON: pic})))
            self.assertEqual(img.width, W)
            self.assertGreater(img.height, 700, rec.mode)

    def test_a_mode_not_played(self):
        rec = R.hsr_pf(F.pf())
        rec.teams, rec.empty = [], "No Pure Fiction runs this season yet."
        img = Image.open(io.BytesIO(draw_records("hsr", "800069903", [rec], {})))
        self.assertLess(img.height, 400)

    def test_letters_the_font_lacks(self):
        from bot import card, card_hsr
        from bot.records_hsr import _typeable
        card.FONTS = card.FONTS or card.Fonts()
        self.assertEqual(_typeable("Saṃvartasthāyi", card_hsr._raj("Bold", 15)), "Samvartasthāyi")


class StatsTest(unittest.TestCase):
    def test_profiles_and_cards(self):
        import io
        import json
        import sys
        from types import SimpleNamespace as NS
        from PIL import Image
        sys.path.insert(0, "tests")
        import stats_fakes as F
        from bot import stats
        from bot.stats_card import draw_stats, image_urls
        locs = {"TitleText_3800101": "Phaethon Returns", "MedalName2004": "Endless Ascension IV"}
        assets = NS(data={
            "gi_namecards": {"210189": {"Icon": "/ui/UI_NameCardPic_Chenyu1_P.jpg"}, "210001": {"Icon": "/ui/UI_NameCardPic_0_P.jpg"}},
            "gi_pfps": {"4600": {"IconPath": "/ui/UI_AvatarIcon_Yae_Circle.png"}},
            "hsr_head_icons": {"201308": {"Icon": "SpriteOutput/AvatarRoundIcon/Avatar/1308.png"}},
            "zzz_pfps": {"3201004": {"Icon": "/ui/zzz/IconInterKnot1004.png"}},
            "zzz_namecards": {"3300012": {"Icon": "/ui/zzz/ImgCardBP11.png"}},
            "zzz_titles": {"Titles": {"3800101": {"TitleText": "TitleText_3800101", "ColorA": "00cefb", "ColorB": "0263e5"}}},
            "zzz_medals": {"2004": {"Name": "MedalName2004", "Icon": "/ui/zzz/Tower04.png"}},
        }, zzz_text=locs.get)
        gi = stats.add_enka(stats.genshin_profile("618285856", F.genshin()), assets, F.GI_PLAYER)
        self.assertEqual(gi.headline[0], ("Days active", "812"))
        self.assertEqual(len(gi.regions), 10)
        self.assertEqual(gi.avatar, "https://enka.network/ui/UI_AvatarIcon_Yae_Circle.png")  # the picture picked in game
        self.assertEqual(gi.banner, "https://enka.network/ui/UI_NameCardPic_Chenyu1_P.jpg")
        self.assertEqual(gi.world_level, ("World Level", "9"))
        self.assertEqual(len(gi.namecards), 2)  # unknown name cards are left out
        hsr = stats.add_enka(stats.hsr_profile("800069903", *F.hsr()), assets, F.HSR_PLAYER)
        self.assertEqual(hsr.nickname, "Trailblazer")
        self.assertIn(("Memory of Chaos", "Eternal Stage 12"), hsr.headline)
        self.assertEqual(hsr.avatar, "https://enka.network/ui/hsr/SpriteOutput/AvatarRoundIcon/Avatar/1308.png")
        self.assertEqual(hsr.banner, F.SRR_WALL)  # the phone wallpaper from HoYoLAB
        self.assertIn(("Relics", "2,878"), dict(hsr.groups)["Collection"])
        zzz = stats.add_enka(stats.zzz_profile("1300003409", F.zzz()), assets, F.ZZZ_PLAYER)
        self.assertEqual((zzz.nickname, zzz.level), ("Proxy", 60))
        self.assertEqual(zzz.title, "Phaethon Returns")
        self.assertEqual(zzz.title_colors, ("00cefb", "0263e5"))
        self.assertIn(("Reputation", "Virtuoso"), dict(zzz.groups)["Records"])
        self.assertEqual([m.value for m in zzz.medals], ["30", "6", "12"])
        self.assertEqual(zzz.medals[1].name, "Endless Ascension IV")
        empty = stats.add_enka(stats.zzz_profile("1300003409", F.zzz()), assets, None)  # Enka down: still drawn
        for p in (gi, hsr, zzz, empty):
            self.assertTrue(image_urls(p) or p is empty)
            self.assertEqual(Image.open(io.BytesIO(draw_stats(p, {}))).width, 1200)
        json.dumps(stats.Profile("genshin", "1").__dict__)  # plain data
