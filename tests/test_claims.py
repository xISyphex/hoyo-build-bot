"""Claim storage and UID resolution, without Discord."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bot.claims import ClaimStore


class ClaimStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "claims.json"

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_one_uid_per_game_and_new_claim_replaces_old(self) -> None:
        store = ClaimStore(self.path)
        self.assertIsNone(store.set(1, "hsr", "800069903"))
        self.assertIsNone(store.set(1, "genshin", "618285856"))
        self.assertEqual(store.set(1, "hsr", "800000001"), "800069903")
        self.assertEqual(store.get(1, "hsr"), "800000001")
        self.assertEqual(store.get(1, "genshin"), "618285856")
        self.assertIsNone(store.get(1, "zzz"))
        self.assertIsNone(store.get(2, "hsr"))

    def test_survives_restart(self) -> None:
        ClaimStore(self.path).set(1, "zzz", "1300003409")
        self.assertEqual(ClaimStore(self.path).get(1, "zzz"), "1300003409")
        self.assertEqual(json.loads(self.path.read_text()), {"1": {"zzz": "1300003409"}})

    def test_broken_file_is_set_aside(self) -> None:
        self.path.write_text("{not json")
        store = ClaimStore(self.path)
        self.assertIsNone(store.get(1, "hsr"))
        self.assertTrue(self.path.with_suffix(".broken.json").exists())
        store.set(1, "hsr", "800069903")
        self.assertEqual(ClaimStore(self.path).get(1, "hsr"), "800069903")


class ResolveUidTests(unittest.TestCase):
    def test_typed_uid_wins_over_claim(self) -> None:
        try:
            from bot.main import resolve_uid
        except ImportError:
            self.skipTest("discord.py not installed")
        with tempfile.TemporaryDirectory() as d:
            store = ClaimStore(Path(d) / "claims.json")
            self.assertIsNone(resolve_uid(store, 1, "hsr", None))
            store.set(1, "hsr", "800069903")
            self.assertEqual(resolve_uid(store, 1, "hsr", None), "800069903")
            self.assertEqual(resolve_uid(store, 1, "hsr", "  "), "800069903")
            self.assertEqual(resolve_uid(store, 1, "hsr", " 800000001 "), "800000001")
            self.assertIsNone(resolve_uid(store, 1, "zzz", None))


if __name__ == "__main__":
    unittest.main()
