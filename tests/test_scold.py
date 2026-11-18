import json
import tempfile
import unittest
from pathlib import Path

from bot import scold

# Made-up Discord IDs, only for the tests.
ALICE, BOB = 111111111111111111, 222222222222222222
NAMES = {"1308": "Acheron", "1407": "Castorice", "1408": "Phainon", "1001": "March 7th", "1224": "March 7th",
         "1102": "Seele"}


class ParseUsersTest(unittest.TestCase):
    def test_mentions_and_ids(self):
        text = f"<@{ALICE}>, <@!{BOB}> {ALICE} and 12345"
        self.assertEqual(scold.parse_users(text), [ALICE, BOB])

    def test_empty(self):
        self.assertEqual(scold.parse_users(None), [])
        self.assertEqual(scold.parse_users("nobody"), [])


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "scold.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_enable_replace_disable_and_reload(self):
        store = scold.ScoldStore(self.path)
        self.assertIsNone(store.text(ALICE))
        store.enable([ALICE, BOB], "shame on you")
        store.enable([ALICE], "how could you")
        store.set_mvp(["1308", "1407", "1308"])
        again = scold.ScoldStore(self.path)
        self.assertEqual(again.text(ALICE), "how could you")
        self.assertEqual(again.text(BOB), "shame on you")
        self.assertEqual(again.mvp, ["1308", "1407"])
        self.assertEqual(again.disable([BOB, 333]), [BOB])
        self.assertIsNone(scold.ScoldStore(self.path).text(BOB))
        self.assertEqual(json.loads(self.path.read_text())["enabled"], {str(ALICE): "how could you"})

    def test_broken_file_is_kept_aside(self):
        self.path.write_text("{not json")
        store = scold.ScoldStore(self.path)
        self.assertEqual((store.enabled, store.mvp), ({}, []))
        self.assertTrue(self.path.with_suffix(".broken.json").exists())


class MissingTest(unittest.TestCase):
    def test_missing_in_list_order(self):
        mvp = ["1408", "1308", "1407"]
        self.assertEqual(scold.missing(mvp, {"1308"}, NAMES), ["Phainon", "Castorice"])
        self.assertEqual(scold.missing(mvp, {"1308", "1407", "1408", "1102"}, NAMES), [])

    def test_shared_names_count_once(self):
        mvp = ["1001", "1224"]
        self.assertEqual(scold.missing(mvp, {"1224"}, NAMES), [])
        self.assertEqual(scold.missing(mvp, set(), NAMES), ["March 7th"])

    def test_unknown_id_keeps_id(self):
        self.assertEqual(scold.missing(["9999"], set(), NAMES), ["9999"])

    def test_name_ids(self):
        ids = scold.name_ids({**NAMES, "8009": "{NICKNAME}"})
        self.assertEqual(ids["March 7th"], ["1001", "1224"])
        self.assertNotIn("{NICKNAME}", ids)


class MessageTest(unittest.TestCase):
    def test_join(self):
        self.assertEqual(scold.join_names(["Acheron"]), "Acheron")
        self.assertEqual(scold.join_names(["Acheron", "Phainon"]), "Acheron and Phainon")
        self.assertEqual(scold.join_names(["Acheron", "Castorice", "Phainon"]), "Acheron, Castorice and Phainon")

    def test_scold_text(self):
        text = scold.scold_text(ALICE, "shame on you.", ["Acheron", "Castorice", "Phainon"])
        self.assertEqual(text, f"<@{ALICE}> shame on you for not pulling **Acheron, Castorice and Phainon**.")

    def test_showcase_note(self):
        text = scold.scold_text(ALICE, "", ["Acheron"], showcase=True)
        self.assertTrue(text.startswith(f"<@{ALICE}> {scold.DEFAULT_TEXT} for not pulling **Acheron**."))
        self.assertIn("\n-# ", text)


if __name__ == "__main__":
    unittest.main()
