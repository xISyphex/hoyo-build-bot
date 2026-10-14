import io
import unittest

from PIL import Image

import records_fakes as F
from bot import records as R
from bot.models import CharacterBuild, Weapon
from bot.records_card import draw_records


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
        self.assertEqual(R.copies_label("zzz", R.Member("1", None, copies=6, weapon_copies=1)), "M6P1")


class ReadersTest(unittest.TestCase):
    def test_memory_of_chaos(self):
        rec = R.hsr_moc(F.moc())
        self.assertEqual(dict(rec.headline), {"Stars": "36 / 36", "Starward": "3★", "Floor": "12", "Cycles": "7"})
        self.assertEqual([t.label for t in rec.teams], ["Node 1", "Node 2", "Starward"])
        self.assertEqual(rec.teams[0].members[0].copies, 2)

    def test_two_nodes_without_starward(self):
        data = F.pf()
        data.floors[0].node_3 = None
        self.assertEqual([t.label for t in R.hsr_pf(data).teams], ["Node 1", "Node 2"])

    def test_scores(self):
        self.assertEqual(dict(R.hsr_pf(F.pf()).headline)["Score"], "114,632")
        self.assertEqual(R.hsr_apoc(F.apoc()).teams[1].result, "3,720 pts")

    def test_anomaly_arbitration_knights_then_king(self):
        rec = R.hsr_aa(F.aa())
        self.assertEqual([t.label for t in rec.teams],
                         ["Wolf Knight", "Lion Knight", "Stag Knight", "Sovereign of Thrones · Hard Mode"])
        self.assertEqual(rec.teams[3].result, "3★ · 4 cycles")
        self.assertEqual([t.stage for t in rec.teams], ["", "", "", "King"])

    def test_zzz_ranking(self):
        sd, da = R.zzz_sd(F.sd()), R.zzz_da(F.da())
        self.assertEqual(dict(sd.headline)["Top"], "4.21%")
        self.assertEqual(dict(da.headline)["Top"], "2.8%")
        self.assertEqual(sd.teams[0].result, "31,890 pts · S · 1:44")
        self.assertEqual(len(da.teams), 4)
        self.assertEqual((da.teams[3].stage, da.teams[3].label), ("Adversity Mode", "Notorious - Miasma Priest"))
        self.assertEqual(dict(da.headline)["Adversity top"], "11.3%")

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


class DrawTest(unittest.TestCase):
    def test_draws_every_game(self):
        for game, recs in (
            ("hsr", [R.hsr_moc(F.moc()), R.hsr_aa(F.aa()), R.Record("pf", "Pure Fiction", empty="No runs.")]),
            ("zzz", [R.zzz_sd(F.sd()), R.zzz_da(F.da())]),
            ("genshin", [R.gi_abyss(F.abyss())]),
        ):
            img = Image.open(io.BytesIO(draw_records(game, "800069903", recs, {})))
            self.assertEqual(img.width, 1200)
            self.assertGreater(img.height, 300)


if __name__ == "__main__":
    unittest.main()
