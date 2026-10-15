"""The pull minigame's rules and storage, without Discord."""

from __future__ import annotations

import datetime as dt
import random
import tempfile
import unittest
from pathlib import Path

from bot import gacha
from bot.patch import Banner, Patch

UTC = dt.timezone.utc
CHAR = gacha.BannerChoice("character", "Furina", ["Furina"], ["Bennett", "Xingqiu", "Sucrose"], set())
WEAPON = gacha.BannerChoice("weapon", "Splendor & Dreams", ["Splendor", "Dreams"], ["The Flute", "Rust"], {"The Flute", "Rust"})
EXTRA = gacha.Pool(["Fischl", "Noelle"], ["Favonius Codex"])


class ResetTests(unittest.TestCase):
    def test_day_turns_at_four_utc_plus_two(self) -> None:
        # 04:00 UTC+2 is 02:00 UTC
        self.assertEqual(gacha.day_key(dt.datetime(2026, 10, 14, 1, 59, tzinfo=UTC)), "2026-10-13")
        self.assertEqual(gacha.day_key(dt.datetime(2026, 10, 14, 2, 0, tzinfo=UTC)), "2026-10-14")
        self.assertEqual(gacha.next_reset(dt.datetime(2026, 10, 14, 1, 0, tzinfo=UTC)),
                         dt.datetime(2026, 10, 14, 2, 0, tzinfo=UTC))
        self.assertEqual(gacha.next_reset(dt.datetime(2026, 10, 14, 20, 0, tzinfo=UTC)),
                         dt.datetime(2026, 10, 15, 2, 0, tzinfo=UTC))


class RollTests(unittest.TestCase):
    def run_pulls(self, game: str, banner, n: int, seed: int = 1) -> tuple[list[gacha.Pull], dict]:
        pity: dict = {}
        rng = random.Random(seed)
        rule = gacha.RULES[(game, banner.kind)]
        return [gacha.roll(rule, banner.kind, banner, game, pity, EXTRA, rng) for _ in range(n)], pity

    def test_hard_pity_and_ten_pull_four_star(self) -> None:
        for seed in range(30):
            results, _ = self.run_pulls("genshin", CHAR, 400, seed)
            fives = [i for i, r in enumerate(results) if r.rarity == 5]
            gaps = [b - a for a, b in zip([-1] + fives, fives)]
            self.assertTrue(all(g <= 90 for g in gaps), gaps)
            streak = 0
            for r in results:
                streak = 0 if r.rarity >= 4 else streak + 1
                self.assertLess(streak, 10)

    def test_lost_fifty_fifty_guarantees_the_next(self) -> None:
        for seed in range(30):
            results, _ = self.run_pulls("hsr", gacha.BannerChoice("character", "Acheron", ["Acheron"], ["Asta"], set()), 1500, seed)
            fives = [r for r in results if r.rarity == 5]
            for a, b in zip(fives, fives[1:]):
                if not a.featured:
                    self.assertTrue(b.featured)
                    self.assertEqual(b.name, "Acheron")
                else:
                    self.assertIn(b.name, ("Acheron",) + gacha.STANDARD[("hsr", "character")])

    def test_rates_roughly_match(self) -> None:
        results, _ = self.run_pulls("genshin", CHAR, 200_000, 7)
        fives = sum(r.rarity == 5 for r in results) / len(results)
        fours = sum(r.rarity == 4 for r in results) / len(results)
        self.assertAlmostEqual(fives, 0.016, delta=0.002)  # Genshin's consolidated 5-star rate is 1.6%
        self.assertAlmostEqual(fours, 0.13, delta=0.01)  # and 13% for 4-stars

    def test_weapon_banner_items(self) -> None:
        results, _ = self.run_pulls("zzz", WEAPON, 2000)
        for r in results:
            if r.rarity == 5:
                self.assertTrue(r.weapon)
                self.assertIn(r.name, ["Splendor", "Dreams", *gacha.STANDARD[("zzz", "weapon")]])
            if r.rarity == 4 and r.featured:
                self.assertTrue(r.weapon)
            if r.rarity == 3:
                self.assertEqual(r.name, "B-rank W-Engine")


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "gacha.json"

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_daily_once_per_reset_and_pulls_spent(self) -> None:
        store = gacha.GachaStore(self.path)
        morning = dt.datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
        self.assertEqual(store.daily(1, ["genshin", "hsr"], morning), {"genshin": 1, "hsr": 1})
        self.assertIsNone(store.daily(1, ["genshin", "hsr"], morning + dt.timedelta(hours=19)))
        self.assertEqual(store.daily(1, ["genshin"], morning + dt.timedelta(hours=20)), {"genshin": 2})
        self.assertIsNone(store.pull(1, "genshin", CHAR, 3, EXTRA))
        results = store.pull(1, "genshin", CHAR, 2, EXTRA, random.Random(3))
        self.assertEqual(len(results), 2)
        self.assertEqual(store.pulls(1, "genshin"), 0)
        self.assertEqual(store.pulls(1, "hsr"), 1)

        # Saved: a new store reads the same pulls, pity and box back
        again = gacha.GachaStore(self.path)
        self.assertEqual(again.pulls(1, "hsr"), 1)
        self.assertEqual(again.pity(1, "genshin", "character"), store.pity(1, "genshin", "character"))
        self.assertEqual(again.box(1, "genshin"), store.box(1, "genshin"))

    def test_box_keeps_only_four_and_five_stars_with_copies(self) -> None:
        store = gacha.GachaStore(self.path)
        store._user(1)["pulls"] = {"genshin": 200}
        results = []
        for _ in range(20):
            results += store.pull(1, "genshin", CHAR, 10, EXTRA, random.Random(len(results)))
        box = store.box(1, "genshin")
        kept = [r for r in results if r.rarity >= 4]
        self.assertEqual(sum(c for page in box.values() for _, c in page.values()), len(kept))
        self.assertTrue(all(r in (4, 5) for page in box.values() for r, _ in page.values()))
        self.assertLess(self.path.stat().st_size, 2000)


class BannerChoiceTests(unittest.TestCase):
    def test_running_banners_character_first_no_chronicled(self) -> None:
        from bot.minigame import banner_choices, pick_banner

        now = dt.datetime(2026, 10, 14, 12, tzinfo=UTC)
        start, end = now - dt.timedelta(days=1), now + dt.timedelta(days=5)
        banners = [
            Banner("Weapon event wish", ["Splendor", "Dreams"], ["The Flute"], start, end),
            Banner("Character event wishes", ["Furina"], ["Bennett"], start, end),
            Banner("Character event wishes", ["Nahida"], ["Bennett"], start, end),
            Banner("Chronicled wish", ["Diluc"], [], start, end),
            Banner("Character event wishes", ["Old"], [], start - dt.timedelta(days=30), start),
        ]
        choices = banner_choices(Patch("genshin", "7.1", now, end, banners))
        self.assertEqual([c.title for c in choices], ["Furina", "Nahida", "Splendor & Dreams"])
        self.assertEqual(choices[2].weapons_4, {"The Flute"})
        self.assertEqual(pick_banner(choices, None).title, "Furina")
        self.assertEqual(pick_banner(choices, "nahi").title, "Nahida")
        self.assertEqual(pick_banner(choices, "Splendor & Dreams").kind, "weapon")


if __name__ == "__main__":
    unittest.main()


class CardTests(unittest.TestCase):
    def test_pull_and_box_cards_draw_without_pictures(self) -> None:
        from io import BytesIO

        from PIL import Image

        from bot.gacha_card import draw_box, draw_pulls

        for game in ("genshin", "hsr", "zzz"):
            results = [gacha.Pull("Furina", 5, False, False, 77), gacha.Pull("Bennett", 4, False, True),
                       gacha.Pull("Debate Club", 3, True)]
            box = {"characters": {"Furina": [5, 1], "Bennett": [4, 3]}}
            pulls = Image.open(BytesIO(draw_pulls(game, CHAR, results, {"five": 0, "guarantee": True}, 4, box, "Hi", {})))
            self.assertEqual(pulls.width, 1200)
            for page in (0, 1):
                self.assertEqual(Image.open(BytesIO(draw_box(game, "Proxy", box, page, 4, {}))).width, 1200)
