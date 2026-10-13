"""The access list and the checks that use it, without Discord."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord

from bot.access import PRIVATE, AccessList
from bot.main import AccessGroup, CharacterView, PrivateTree

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
        guide = str(user.dms[0].to_dict())
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


class _User:
    def __init__(self, uid, closed=False):
        self.id, self.name, self.mention, self.closed, self.dms = uid, "friend", f"<@{uid}>", closed, []

    async def send(self, embed=None):
        if self.closed:
            raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Cannot send messages to this user")
        self.dms.append(embed)


if __name__ == "__main__":
    unittest.main()
