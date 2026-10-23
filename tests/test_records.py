import io
import unittest

from PIL import Image, ImageDraw

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

    def test_scores(self):
        self.assertEqual(dict(R.hsr_pf(F.pf()).headline)["Score"], "114,632")
        self.assertEqual(R.hsr_apoc(F.apoc()).teams[1].chips, [("score", "3,720")])
        self.assertNotIn("Floor", dict(R.hsr_apoc(F.apoc()).headline))  # the season line already names it

    def test_anomaly_arbitration_knights_then_king(self):
        rec = R.hsr_aa(F.aa())
        self.assertEqual([t.label for t in rec.teams],
                         ["Wolf Knight", "Lion Knight", "Stag Knight", "Sovereign of Thrones · Plight"])
        self.assertEqual(rec.teams[3].left, [("Cycles", "4")])
        self.assertTrue(rec.teams[3].plight)
        self.assertEqual(dict(rec.headline), {"Stars": "9", "Cycles": "7"})  # the knights only
        self.assertEqual([t.stage for t in rec.teams], ["", "", "", "King"])

    def test_zzz_ranking(self):
        sd, da = R.zzz_sd(F.sd()), R.zzz_da(F.da())
        self.assertEqual(dict(sd.headline)["Top"], "4.21%")
        self.assertEqual(dict(da.headline)["Top"], "2.8%")
        self.assertEqual(sd.teams[0].chips, [("rating", "S"), ("score", "31,890"), ("time", "1:44")])
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

    def test_round_icons_are_spotted(self):
        from bot.records_zzz import _round
        round_icon = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(round_icon).ellipse((0, 0, 39, 39), fill=(200, 100, 50, 255))
        self.assertTrue(_round(round_icon))
        self.assertFalse(_round(Image.new("RGBA", (40, 40), (200, 100, 50, 255))))
