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


if __name__ == "__main__":
    unittest.main()
