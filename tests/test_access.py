"""The access list and the checks that use it, without Discord."""

from __future__ import annotations

import asyncio
import re
import tempfile
import unicodedata
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord

from bot.access import PRIVATE, AccessList
from bot.guide import OpenGuideButton, PageButton
from bot.main import AccessGroup, CharacterView, PrivateTree, help_command, pat_command

OWNER, FRIEND, STRANGER = 1, 2, 3


class _Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, content, **kwargs):
        self.sent.append((content, kwargs.get("ephemeral")))


def _interaction(access, user_id, kind=discord.InteractionType.application_command):
    return SimpleNamespace(
        client=SimpleNamespace(access=access), user=SimpleNamespace(id=user_id), type=kind, response=_Response(),
        followup=_Followup(),
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
        embeds, files, view = user.dms[0]
        self.assertEqual([f.filename for f in files], ["fairy-guide.jpg"])  # page 1: Fairy with her guide book
        self.assertIn("attachment://fairy-guide.jpg", str(embeds[0].to_dict()))
        self.assertEqual(embeds[-1].footer.text[:10], "Page 1 / 2")
        self.assertEqual(view.children[0].item.label, "Next page ▶")
        embeds2, files2, view2 = self._flip(view, STRANGER)
        self.assertEqual([f.filename for f in files2], ["fairy-goodbye.jpg"])  # page 2 ends with the goodbye picture
        self.assertEqual(embeds2[0].footer.text[:10], "Page 2 / 2")
        self.assertIn("attachment://fairy-goodbye.jpg", str(embeds2[-1].to_dict()))
        self.assertIn("I am looking forward to working with you, Proxy~", str(embeds2[-1].to_dict()))
        credits = unicodedata.normalize("NFKC", embeds2[-1].footer.text)  # slanted letters back to plain ones
        self.assertIn("@nobawns", credits)  # the artists are credited under the goodbye picture
        self.assertIn("@yasiro_hayate", credits)
        self.assertIn("Fairy's Guide for Proxy", str(self._flip(view2, STRANGER)[0][0].to_dict()))  # and back again
        guide = str([e.to_dict() for e in embeds + embeds2])
        self.assertNotIn("Master", guide)
        for command in ("/genshin", "/hsr", "/zzz", "/genshin-claim", "/hsr-claim", "/zzz-claim", "/pat", "/help", "/hsr-records", "15"):
            self.assertIn(command, guide)
        self.assertEqual(guide.count("Example: "), 5)  # one usage example per kind of command
        self.assertNotIn("/access", guide)
        self.assertIn("client_id=123&integration_type=1", guide)  # the link to add it to their account
        self._add(user)  # adding them again doesn't send it twice
        self.assertEqual(len(user.dms), 1)

    def _flip(self, view, user_id):
        """Presses the guide's page button the way Discord would after a restart: rebuilt from its ID alone."""
        button = view.children[0]
        match = re.fullmatch(PageButton.__discord_ui_compiled_template__, button.custom_id)
        item = asyncio.run(PageButton.from_custom_id(None, button, match))
        it = _interaction(self.access, user_id)
        it.client.user = SimpleNamespace(name="Build Bot")
        it.client.lookups = SimpleNamespace(per_hour=15)
        it.client.application_id = 123
        it.response = _EmbedResponse()
        asyncio.run(item.callback(it))
        return it.response.edited[0]

    def test_closed_dms_still_add_the_user(self):
        reply = self._add(_User(STRANGER, closed=True))
        self.assertTrue(self.access.allowed(STRANGER))
        self.assertIn("couldn't DM", reply)

    def test_closed_dms_tag_them_with_a_private_guide_button(self):
        it = _interaction(self.access, OWNER)
        it.client.user = SimpleNamespace(name="Build Bot")
        it.client.lookups = SimpleNamespace(per_hour=15)
        it.client.application_id = 123
        it.followup = _Followup()
        asyncio.run(AccessGroup().add.callback(AccessGroup(), it, _User(STRANGER, closed=True)))
        self.assertIn("tagged them here", it.response.sent[0][0])
        content, kwargs = it.followup.sent[0]
        self.assertIn(f"<@{STRANGER}>", content)
        self.assertEqual([u.id for u in kwargs["allowed_mentions"].users], [STRANGER])
        button = kwargs["view"].children[0]
        match = re.fullmatch(OpenGuideButton.__discord_ui_compiled_template__, button.custom_id)
        item = asyncio.run(OpenGuideButton.from_custom_id(None, button, match))  # as after a restart

        def press(user_id):
            press_it = _interaction(self.access, user_id)
            press_it.client = it.client
            press_it.response = _EmbedResponse()
            asyncio.run(item.callback(press_it))
            return press_it.response.sent[0]

        embeds, files, view, ephemeral = press(STRANGER)
        self.assertTrue(ephemeral)  # only they see it
        self.assertIn("Fairy's Guide for Proxy", embeds[0].title)
        self.assertEqual(len(files), 1)
        self.assertIsNotNone(view)
        self.assertTrue(press(FRIEND)[3])  # someone else just gets a private note

    def test_help_shows_the_guide_and_access_only_to_the_owner(self):
        for user_id, sees_access in ((OWNER, True), (STRANGER, False)):
            it = _interaction(self.access, user_id)
            it.client.user = SimpleNamespace(name="Build Bot")
            it.client.lookups = SimpleNamespace(per_hour=15)
            it.client.application_id = 123
            it.response = _EmbedResponse()
            asyncio.run(help_command.callback(it))
            embeds, files, view, ephemeral = it.response.sent[0]
            self.assertTrue(ephemeral)
            self.assertEqual(len(files), 1)
            self.assertIn("refresher", embeds[0].description)
            page2 = self._flip(view, user_id)[0]  # the /access section is on page 2
            self.assertEqual("/access" in str([e.to_dict() for e in page2]), sees_access)
            self.assertIn("refresher", str(self._flip(self._flip(view, user_id)[2], user_id)[0][0].to_dict()))


class _Followup:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append((content, kwargs))


class _EmbedResponse:
    def __init__(self):
        self.sent = []

        self.edited = []

    async def send_message(self, content=None, embeds=(), files=(), view=None, **kwargs):
        self.sent.append((embeds, files, view, kwargs.get("ephemeral")))

    async def edit_message(self, embeds=(), attachments=(), view=None):
        self.edited.append((embeds, attachments, view))


class _User:
    def __init__(self, uid, closed=False):
        self.id, self.name, self.mention, self.closed, self.dms = uid, "friend", f"<@{uid}>", closed, []

    async def send(self, embeds=(), files=(), view=None):
        if self.closed:
            raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Cannot send messages to this user")
        self.dms.append((embeds, files, view))


if __name__ == "__main__":
    unittest.main()


class PatTest(unittest.TestCase):
    def test_pat_answers_once_with_thanks_and_fairys_picture(self):
        sent = []

        class Response:
            async def send_message(self, content, file):
                sent.append((content, file.filename))

        asyncio.run(pat_command.callback(SimpleNamespace(response=Response())))
        self.assertEqual(len(sent), 1)
        self.assertIn("Proxy", sent[0][0])
        self.assertEqual(sent[0][1], "fairy-happy.png")
