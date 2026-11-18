import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from cryptography.fernet import Fernet

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


class _Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, content, **kwargs):
        self.sent.append((content, kwargs.get("ephemeral")))

    async def defer(self, **kwargs):
        pass


class _Followup:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append(content)


class ScoldLookupTest(unittest.TestCase):
    """/scold reads HoYoLAB the same way the other commands do, so the owner's own account (served by the bot-wide
    HOYOLAB_COOKIES, not a /hoyolab link) gets their whole roster, not the Enka showcase."""

    UID = "800000001"  # made up

    def setUp(self):
        from bot.access import AccessList
        from bot.claims import ClaimStore
        from bot.hoyolab import HoyolabClient
        from bot.hoyolab_links import LinkStore

        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        self.access = AccessList(d / "access.json")
        self.access.owners = {ALICE}
        self.store = scold.ScoldStore(d / "scold.json")
        self.store.set_mvp(["1308", "1407"])
        self.claims = ClaimStore(d / "claims.json")
        self.claims.set(ALICE, "hsr", self.UID)  # claimed with /hsr-claim; nothing linked with /hoyolab link
        self.links = LinkStore(d / "links.json", Fernet.generate_key())
        assets = SimpleNamespace(data={"hsr_characters": {c: {"Name": n} for c, n in NAMES.items()}},
                                 hsr_text=lambda h: None)
        self.hoyolab = HoyolabClient("ltuid_v2=1; ltoken_v2=x", assets, self.links)  # the bot's HOYOLAB_COOKIES
        self.enka = SimpleNamespace(fetch=mock.AsyncMock(return_value=SimpleNamespace(
            characters=[SimpleNamespace(character_id="1102")])))
        self.bot = SimpleNamespace(access=self.access, scold=self.store, claims=self.claims, links=self.links,
                                   hoyolab=self.hoyolab, enka=self.enka, assets=assets)

    def tearDown(self):
        self.dir.cleanup()

    def _run(self):
        from bot.main import scold_command
        me = SimpleNamespace(id=ALICE, mention=f"<@{ALICE}>")
        it = SimpleNamespace(client=self.bot, user=me, response=_Response(), followup=_Followup())
        asyncio.run(scold_command.callback(it, None))
        return it.followup.sent

    def test_owner_on_server_cookies_gets_their_hoyolab_roster(self):
        builds = [SimpleNamespace(character_id="1308"), SimpleNamespace(character_id="1102")]
        with mock.patch.object(self.hoyolab, "_fetch", mock.AsyncMock(return_value=builds)) as fetch:
            sent = self._run()
        fetch.assert_awaited_once_with(self.hoyolab.client, "hsr", int(self.UID))
        self.enka.fetch.assert_not_awaited()
        self.assertIn("**Castorice**", sent[0])
        self.assertNotIn("showcase", sent[0])

    def test_hoyolab_failure_falls_back_to_the_showcase_and_logs_why(self):
        import genshin
        with mock.patch.object(self.hoyolab, "_fetch", mock.AsyncMock(side_effect=genshin.DataNotPublic({}))), \
                self.assertLogs("hoyo-bot", "WARNING") as logs:
            sent = self._run()
        self.enka.fetch.assert_awaited_once_with("hsr", self.UID)
        self.assertIn("showcase", sent[0])
        self.assertTrue(any("/scold" in line and self.UID in line for line in logs.output))


    def test_only_the_owner_manages_scold(self):
        from bot.main import hsr_mvp_command, scold_disable_command, scold_enable_command, scold_list_command
        calls = ((scold_enable_command, (f"<@{BOB}>", "shame")), (scold_disable_command, (f"<@{BOB}>",)),
                 (scold_list_command, ()), (hsr_mvp_command, ("Seele",)), (hsr_mvp_command, (None,)))
        for command, args in calls:
            it = SimpleNamespace(client=self.bot, user=SimpleNamespace(id=BOB), response=_Response())
            asyncio.run(command.callback(it, *args))
            self.assertEqual(len(it.response.sent), 1, command.name)
            self.assertIn("owner", it.response.sent[0][0], command.name)
            self.assertTrue(it.response.sent[0][1], command.name)
        self.assertEqual(self.store.mvp, ["1308", "1407"])
        self.assertIsNone(self.store.text(BOB))


if __name__ == "__main__":
    unittest.main()
