"""The access list and the checks that use it, without Discord."""

from __future__ import annotations

import asyncio
import tempfile
import unicodedata
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord

from bot.access import PRIVATE, AccessList
from bot.main import AccessGroup, CharacterView, PrivateTree, help_command

OWNER, FRIEND, STRANGER = 1, 2, 3


class _Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, content, **kwargs):
        self.sent.append((content, kwargs.get("ephemeral")))


def _interaction(access, user_id, kind=discord.InteractionType.application_command):
    return SimpleNamespace(
        client=SimpleNamespace(access=access), user=SimpleNamespace(id=user_id), type=kind, response=_Response()
    )


class AccessListTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "access.json"
        self.access = AccessList(self.path)
        self.access.owners = {OWNER}

    def tearDown(self):
        self.dir.cleanup()

    def test_only_owner_and_added_users_are_allowed(self):
        self.assertTrue(self.access.allowed(OWNER))
        self.assertFalse(self.access.allowed(FRIEND))
        self.assertTrue(self.access.add(FRIEND, "friend"))
        self.assertFalse(self.access.add(FRIEND, "friend"))
        self.assertTrue(self.access.allowed(FRIEND))
        self.assertFalse(self.access.allowed(STRANGER))
        self.assertTrue(self.access.remove(FRIEND))
        self.assertFalse(self.access.remove(FRIEND))
        self.assertFalse(self.access.allowed(FRIEND))

    def test_list_survives_a_restart(self):
        self.access.add(FRIEND, "friend")
        again = AccessList(self.path)
        self.assertEqual(again.users, {FRIEND: "friend"})
        self.assertFalse(again.allowed(OWNER))  # owners come from Discord at startup, not the file

    def test_broken_file_is_kept_and_nobody_but_the_owner_gets_in(self):
        self.path.write_text("{not json", encoding="utf-8")
        access = AccessList(self.path)
        self.assertEqual(access.users, {})
        self.assertTrue(self.path.with_suffix(".broken.json").exists())


class AccessCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.access = AccessList(Path(self.dir.name) / "access.json")
        self.access.owners = {OWNER}
        self.access.add(FRIEND, "friend")
        self.tree = PrivateTree.__new__(PrivateTree)
        self.tree.client = SimpleNamespace(access=self.access)

    def tearDown(self):
        self.dir.cleanup()

    def test_commands_answer_strangers_privately(self):
        for user, ok in ((OWNER, True), (FRIEND, True), (STRANGER, False)):
            interaction = _interaction(self.access, user)
            self.assertEqual(asyncio.run(self.tree.interaction_check(interaction)), ok)
            self.assertEqual(interaction.response.sent, [] if ok else [(PRIVATE, True)])

    def test_autocomplete_gives_strangers_nothing(self):
        interaction = _interaction(self.access, STRANGER, discord.InteractionType.autocomplete)
        self.assertFalse(asyncio.run(self.tree.interaction_check(interaction)))
        self.assertEqual(interaction.response.sent, [])

    def test_buttons_on_a_card_are_private_too(self):
        view = CharacterView.__new__(CharacterView)
        interaction = _interaction(self.access, STRANGER, discord.InteractionType.component)
        self.assertFalse(asyncio.run(view.interaction_check(interaction)))
        self.assertTrue(asyncio.run(view.interaction_check(_interaction(self.access, FRIEND))))

    def test_only_the_owner_manages_the_list(self):
        group = AccessGroup()
        self.assertTrue(asyncio.run(group.interaction_check(_interaction(self.access, OWNER))))
        friend = _interaction(self.access, FRIEND)
        self.assertFalse(asyncio.run(group.interaction_check(friend)))
        self.assertIn("owner", friend.response.sent[0][0])

    def _add(self, user):
        """Runs /access add as the owner; returns the owner's reply."""
        it = _interaction(self.access, OWNER)
        it.client.user = SimpleNamespace(name="Build Bot")
        it.client.lookups = SimpleNamespace(per_hour=15)
        it.client.application_id = 123
        asyncio.run(AccessGroup().add.callback(AccessGroup(), it, user))
        return it.response.sent[0][0]

    def test_new_users_get_a_guide_without_the_access_commands(self):
        user = _User(STRANGER)
        reply = self._add(user)
        self.assertIn("sent them a DM", reply)
        self.assertEqual(len(user.dms), 1)
        embeds, files = user.dms[0]
        guide = str([e.to_dict() for e in embeds])
        self.assertEqual([f.filename for f in files], ["fairy-guide.jpg", "fairy-goodbye.jpg"])
        self.assertIn("attachment://fairy-guide.jpg", str(embeds[0].to_dict()))  # Fairy with her guide book first
        self.assertIn("attachment://fairy-goodbye.jpg", str(embeds[-1].to_dict()))  # and the goodbye picture at the end
        self.assertIn("I am looking forward to working with you, Proxy~", str(embeds[-1].to_dict()))
        self.assertEqual([e.footer.text[:10] for e in embeds[1:3]], ["Page 1 / 2", "Page 2 / 2"])  # a two-page guide book
        credits = unicodedata.normalize("NFKC", embeds[-1].footer.text)  # slanted letters back to plain ones
        self.assertIn("@nobawns", credits)  # the artists are credited under the goodbye picture
        self.assertIn("@yasiro_hayate", credits)
        self.assertNotIn("Master", guide)
        for command in ("/genshin", "/hsr", "/zzz", "/genshin-claim", "/hsr-claim", "/zzz-claim", "15"):
            self.assertIn(command, guide)
        self.assertNotIn("/access", guide)
        self.assertIn("client_id=123&integration_type=1", guide)  # the link to add it to their account
        self._add(user)  # adding them again doesn't send it twice
        self.assertEqual(len(user.dms), 1)

    def test_closed_dms_still_add_the_user(self):
        reply = self._add(_User(STRANGER, closed=True))
        self.assertTrue(self.access.allowed(STRANGER))
        self.assertIn("couldn't DM", reply)

    def test_help_shows_the_guide_and_access_only_to_the_owner(self):
        for user_id, sees_access in ((OWNER, True), (STRANGER, False)):
            it = _interaction(self.access, user_id)
            it.client.user = SimpleNamespace(name="Build Bot")
            it.client.lookups = SimpleNamespace(per_hour=15)
            it.client.application_id = 123
            it.response = _EmbedResponse()
            asyncio.run(help_command.callback(it))
            embeds, files, ephemeral = it.response.sent[0]
            self.assertTrue(ephemeral)
            self.assertEqual(len(files), 2)
            self.assertIn("refresher", embeds[0].description)
            self.assertEqual("/access" in str([e.to_dict() for e in embeds]), sees_access)


class _EmbedResponse:
    def __init__(self):
        self.sent = []

    async def send_message(self, content=None, embeds=(), files=(), **kwargs):
        self.sent.append((embeds, files, kwargs.get("ephemeral")))


class _User:
    def __init__(self, uid, closed=False):
        self.id, self.name, self.mention, self.closed, self.dms = uid, "friend", f"<@{uid}>", closed, []

    async def send(self, embeds=(), files=()):
        if self.closed:
            raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Cannot send messages to this user")
        self.dms.append((embeds, files))


if __name__ == "__main__":
    unittest.main()
