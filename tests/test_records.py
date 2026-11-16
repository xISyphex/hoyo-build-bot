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
        self.assertEqual((da.teams[3].stage, da.teams[3].label), ("Adversity Mode", "Notorious - Miasma Priest"))
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


class ShiyuBossNameTest(unittest.TestCase):
    def test_rooms_are_named_by_their_boss_icon(self):
        from bot.shiyu_bosses import boss_names
        icons = "Assets/NapResources/UI/Sprite/A1DynamicLoad/IconBossGeneral/UnPacker/"
        season = {"zone": {"6205905": {"layer_room": {}}, "62059051": {"layer_room": {
            "62059051": {"monster_icon": icons + "IconMonster_MiasmaThracian.png"},
            "62059052": {"monster_icon": icons + "IconMonster_Unknown.png"}, "62059053": {"monster_icon": ""}}}}}
        monsters = {"930178": {"icon": "UI/Sprite/BossCard/Monster_MiasmaThracian.png", "en": "Miasmic - Thracian"},
                    "30023": {"icon": "UI/Sprite/BossCard/Monster_Thracian.png", "en": "Thracian"}}
        self.assertEqual(boss_names(season, monsters), {"62059051": "Miasmic - Thracian"})

    def test_labels_get_the_boss_name(self):
        rec = R.Record("sd", "Shiyu Defense", teams=[R.Team("Battle 1", key="62059051"), R.Team("Battle 2", key="62059052")])
        R.name_bosses(rec, {"62059051": "Miasmic - Thracian"})
        self.assertEqual([t.label for t in rec.teams], ["Battle 1 · Miasmic - Thracian", "Battle 2"])


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


class HsrEnemiesTest(unittest.TestCase):
    # Made-up tables in Hakushin's shape (HardLevelGroup.json / EliteGroup.json), with the real rows the worked
    # example uses: group 1 at level 90, elite group 173
    TABLES = None

    @classmethod
    def setUpClass(cls):
        from bot.hsr_enemies import Tables
        cls.TABLES = Tables(
            [{"HardLevelGroup": 1, "Level": 90, "HPRatio": 236.534716}, {"HardLevelGroup": 3, "Level": 95, "HPRatio": 375.438496},
             {"HardLevelGroup": 3, "Level": 120, "HPRatio": {"Value": 1938.763448}}],  # the raw files' {"Value": x} too
            [{"EliteGroup": 173, "HPRatio": 9.6}, {"EliteGroup": 164, "HPRatio": 6.5}, {"EliteGroup": 169, "HPRatio": 8}])
        cls.DETAILS = {
            3024013: {"name": "Silver Knight", "hp_base": 5812.5, "image_path": "SpriteOutput/MonsterFigure/Monster_3024010.png",
                      "child": [{"id": 302401304, "hp_modify_ratio": 1}]},
            8015030: {"name": "Lord of <i>Ash</i>", "hp_base": 14880, "image_path": "SpriteOutput/MonsterFigure/Monster_8015030.png",
                      "child": [{"id": 801503006, "hp_modify_ratio": 0.375}]},
            2034010: {"name": "Warhead", "hp_base": 2557.5, "image_path": None, "child": [{"id": 2034010, "hp_modify_ratio": 1}]},
        }

    def test_hp_as_hakushin_works_it_out(self):
        # Silver Knight, Apocalyptic Shadow's Starward: 5812.5 x 1 x 236.534716 x 9.6 = 13,198,637
        self.assertEqual(self.TABLES.hp(5812.5, 1, 1, 90, 173), 13198637)
        self.assertEqual(self.TABLES.hp(14880, 0.375, 3, 120, 169), 86546400)
        self.assertEqual(self.TABLES.hp(1000, 1, 3, 95, 999), 375438)  # an elite group the table lacks scales by 1
        self.assertIsNone(self.TABLES.hp(1000, 1, 1, 77, 1))  # no curve for that level: unknown, not made up

    def test_memory_of_chaos_floor_by_id_or_number(self):
        from bot.hsr_enemies import floor_enemies
        season = [{"id": 5511, "event_id_list1": [_stage(92, 3, 164, [2034010])], "event_id_list2": [_stage(92, 3, 164, [2034010])]},
                  {"id": 5512, "event_id_list1": [_stage(95, 3, 164, [8012030, 2034010, 8012030], [2034010, 2034010])],
                   "event_id_list2": [_stage(95, 3, 164, [302401304])]},
                  {"id": 5513, "event_id_list": [_stage(90, 1, 173, [8012030], [302401304])]}]
        found = floor_enemies("moc", season, self.DETAILS, self.TABLES, "5512")
        self.assertEqual(found.keys(), {"1", "2", "3"})
        self.assertEqual([(e["name"], e["level"]) for e in found["1"]], [("Warhead", 95)])  # the last wave, each kind once
        self.assertEqual(found["1"][0]["hp"], round(2557.5 * 375.438496 * 6.5))
        self.assertIsNone(found["1"][0]["art"])
        self.assertEqual(found["3"][0]["hp"], 13198637)
        self.assertTrue(found["3"][0]["art"].endswith("/assets/hsr/monsterfigure/Monster_3024010.webp"))
        by_number = floor_enemies("moc", season, self.DETAILS, self.TABLES, "9999", 2)  # an unknown id: the 2nd floor
        self.assertEqual(by_number["2"], found["2"])
        self.assertEqual(floor_enemies("moc", season, self.DETAILS, self.TABLES, "9999").keys(), {"3"})

    def test_pure_fiction_takes_the_wave_elite_group(self):
        from bot.hsr_enemies import floor_enemies
        stage = _stage(90, 1, None, [8012030], [8012030], [302401304])
        season = {"level": [{"id": 20274, "event_id_list1": [stage], "infinite_list1": {"2": {"elite_group": 173}, "1": {"elite_group": 1}, "3": {"elite_group": 173}}}]}
        found = floor_enemies("pf", season, self.DETAILS, self.TABLES, "20274")
        self.assertEqual(found["1"][0]["hp"], 13198637)

    def test_anomaly_arbitration_knights_and_the_king(self):
        from bot.hsr_enemies import floor_enemies
        season = {"pre_level": [{"id": 1101, "event_id_list": [_stage(95, 3, None, [2034010])], "infinite_list": {"1": {"elite_group": 164}}}],
                  "boss_level": {"id": 1104, "event_id_list": [_stage(100, 3, None, [801503006])]},
                  "boss_config": {"event_id_list": [_stage(120, 3, None, [801503006])], "infinite_list": {"9": {"elite_group": 169}}}}
        found = floor_enemies("aa", season, self.DETAILS, self.TABLES)
        self.assertEqual(found["1101"], found["K1"])
        self.assertEqual(found["PLIGHT"][0]["hp"], 86546400)
        self.assertEqual(found["PLIGHT"][0]["name"], "Lord of Ash")  # markup dropped
        self.assertIsNone(found["KING"][0]["hp"])  # level 100 isn't in these tables
        rec = R.hsr_aa(F.aa())
        rec.teams[3].key = "1104:plight|PLIGHT"
        R.set_enemies(rec, {"K2": found["K1"], "PLIGHT": found["PLIGHT"]})
        self.assertEqual((rec.teams[1].enemies[0].name, rec.teams[1].enemies[0].level), ("Warhead", 95))  # by place
        self.assertEqual(rec.teams[3].enemies[0].hp, 86546400)
        self.assertEqual(rec.teams[0].enemies[0].name, "Wolf Knight")  # not found: HoYoLAB's stays

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


class HsrDrawTest(unittest.TestCase):
    def test_every_mode_draws_with_enemies(self):
        pic = Image.new("RGBA", (300, 500), (200, 40, 40, 255))
        for rec in (R.hsr_moc(F.moc()), R.hsr_pf(F.pf()), R.hsr_apoc(F.apoc()), R.hsr_aa(F.aa())):
            for i, team in enumerate(rec.teams):
                team.enemies = [R.Enemy("Lord of Saṃvartasthāyi, Asat Pramad", "boss.png", 120, 86546400),
                                R.Enemy("Missing Picture", "gone.png", 95, 1234)][: 1 + i % 2]
            rec.teams[-1].enemies = []  # not known yet: an empty screen saying so
            img = Image.open(io.BytesIO(draw_records("hsr", "800069903", [rec], {"boss.png": pic})))
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
