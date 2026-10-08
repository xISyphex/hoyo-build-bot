"""The per-person lookup limit."""

from __future__ import annotations

import unittest

from bot.ratelimit import LookupLimit


class LookupLimitTest(unittest.TestCase):
    def test_fifteen_per_hour_then_wait_for_the_oldest_to_expire(self):
        limit = LookupLimit(15)
        for i in range(15):
            self.assertIsNone(limit.take(1, now=1000 + i))
        self.assertEqual(limit.take(1, now=1100), 1000 + 3600)
        self.assertIsNone(limit.take(2, now=1100))  # everyone has their own count
        self.assertEqual(limit.take(1, now=4599), 4600)  # refused tries don't count
        self.assertIsNone(limit.take(1, now=4600))  # the first lookup has aged out
        self.assertEqual(limit.take(1, now=4600), 1001 + 3600)


if __name__ == "__main__":
    unittest.main()
