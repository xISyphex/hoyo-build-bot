"""The relic search (bot/calc/search.py): against brute force on small inventories, and timed on 2,000 relics."""

from __future__ import annotations

import itertools
import random
import time
import unittest

import numpy as np
from test_parsers import load_assets

from bot.calc import EvaluateRequest, optimize
from bot.calc.prepare import prepare
from bot.calc.relics import ALLOWED_MAINS, SLOTS, SUB_KEYS, Relic, main_value

ROLL = {"hp": 42.34, "atk": 21.17, "def": 21.17, "spd": 2.6, "hp%": 0.0432, "atk%": 0.0432, "def%": 0.054,
        "cr": 0.0324, "cd": 0.0648, "ehr": 0.0432, "res": 0.0432, "be": 0.0648}
RELIC_SETS = ["102", "104", "108", "115", "116", "117", "122", "124"]
PLANAR_SETS = ["301", "302", "309", "310", "311", "312", "314", "316"]


def synthetic(assets, n: int, seed: int, relic_sets=RELIC_SETS, planar_sets=PLANAR_SETS) -> list[Relic]:
    """n random +15 five-star relics, spread over the six slots: four substats, nine rolls."""
    rng = random.Random(seed)
    meta = assets.data["hsr_meta"]
    out = []
    for i in range(n):
        slot = SLOTS[i % 6]
        main = rng.choice(ALLOWED_MAINS[slot])
        subs_keys = rng.sample([k for k in SUB_KEYS if k != main], 4)
        rolls = [1, 1, 1, 1]
        for _ in range(5):
            rolls[rng.randrange(4)] += 1
        subs = {k: round(r * ROLL[k] * rng.uniform(0.8, 1.0), 6) for k, r in zip(subs_keys, rolls)}
        sets = planar_sets if slot in SLOTS[4:] else relic_sets
        out.append(Relic(uid=f"r{i}", set_id=rng.choice(sets), slot=slot, rarity=5, level=15, main=main,
                         main_value=main_value(meta, 5, slot, main, 15), subs=subs))
    return out


def brute_force(assets, req: dict, inventory: list[Relic]) -> float:
    """The best total over every six-relic combination that meets the request's set constraint."""
    r = EvaluateRequest.from_dict(req)
    prep = prepare(assets, r, {x.set_id for x in inventory})
    by_slot = [[x for x in inventory if x.slot == s] for s in SLOTS]
    combos = list(itertools.product(*by_slot))
    keys = sorted({k for x in inventory for k in x.stats()})
    rs = [str(s) for s in r.relic_sets]
    best = -np.inf
    for start in range(0, len(combos), 50_000):
        chunk = combos[start:start + 50_000]
        stats = {k: np.array([sum(x.stats().get(k, 0.0) for x in c) for c in chunk]) for k in keys}
        sets = sorted({x.set_id for x in inventory})
        counts = {sid: np.array([sum(x.set_id == sid for x in c) for c in chunk], dtype=float) for sid in sets}
        ok = np.ones(len(chunk), dtype=bool)
        if len(rs) == 1:
            ok &= counts[rs[0]] >= 4
        elif len(rs) == 2 and "*" in rs:
            ok &= counts[next(s for s in rs if s != "*")] >= 2
        elif len(rs) == 2:
            ok &= (counts[rs[0]] >= 2) & (counts[rs[1]] >= 2)
        total, _ = prep.score(stats, counts, len(chunk))
        total = np.where(ok, total, -np.inf)
        best = max(best, float(np.max(total)))
    return best


class SearchVsBruteForce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        # 6 relics per slot (46,656 combinations), three relic sets and two planar sets
        cls.inventory = synthetic(cls.assets, 36, seed=7, relic_sets=["108", "122", "104"], planar_sets=["309", "311"])

    def check(self, extra: dict):
        req = {"character": {"id": "1102", "light_cone": {"id": "23001"}}, **extra}
        result = optimize(self.assets, req, self.inventory)
        expected = brute_force(self.assets, req, self.inventory)
        self.assertIsNotNone(result.best)
        self.assertAlmostEqual(result.alternatives[0].total, expected, delta=expected * 1e-9)
        self.assertAlmostEqual(result.best.total, expected, delta=expected * 1e-9)
        return result

    def test_any_sets(self):
        self.check({})

    def test_four_piece(self):
        result = self.check({"relic_sets": ["108"]})
        self.assertGreaterEqual(result.best.sets.get("108", 0), 4)

    def test_two_plus_two(self):
        result = self.check({"relic_sets": ["108", "122"]})
        self.assertGreaterEqual(result.best.sets.get("108", 0), 2)
        self.assertGreaterEqual(result.best.sets.get("122", 0), 2)

    def test_two_plus_any(self):
        self.check({"relic_sets": ["104", "*"]})

    def test_min_stats_and_current(self):
        inv = [Relic(**{**r.to_dict(), "location": "1102" if i < 6 else ""}) for i, r in enumerate(self.inventory)]
        req = {"character": {"id": "1102"}, "min_stats": {"spd": 150}}
        result = optimize(self.assets, req, inv)
        self.assertIsNotNone(result.current)
        if result.best is not None:
            self.assertGreaterEqual(result.best.stats["spd"], 150 - 1e-9)


    def test_progress_and_cancel(self):
        seen = []
        result = optimize(self.assets, {"character": {"id": "1102"}}, self.inventory, progress=seen.append)
        self.assertIsNotNone(result.best)
        self.assertEqual((seen[0], seen[-1]), (0.0, 1.0))
        self.assertEqual(seen, sorted(seen))  # never goes backwards

        class Stop(Exception):
            pass

        def stop(fraction):
            if fraction > 0:
                raise Stop()
        with self.assertRaises(Stop):  # an exception from the callback ends the search
            optimize(self.assets, {"character": {"id": "1102"}}, self.inventory, progress=stop)

class Timing(unittest.TestCase):
    """2,000 synthetic relics; the timings are printed (the bound only catches a pathological slowdown)."""

    def test_two_thousand_relics(self):
        assets = load_assets()
        inventory = synthetic(assets, 2000, seed=11)
        cases = {
            "Seele, any sets": {"character": {"id": "1102", "light_cone": {"id": "23001"}}},
            "Seele, 4pc Genius": {"character": {"id": "1102", "light_cone": {"id": "23001"}}, "relic_sets": ["108"]},
            "Kafka + Ruan Mei, 2+2": {"character": {"id": "1005"}, "teammates": [{"id": "1303"}],
                                      "relic_sets": ["116", "117"]},
        }
        for name, req in cases.items():
            t0 = time.perf_counter()
            result = optimize(assets, req, inventory)
            elapsed = time.perf_counter() - t0
            print(f"\n  search timing [{name}]: {elapsed:.2f} s, {result.candidates} candidates, "
                  f"{result.combinations:,} combinations")
            self.assertIsNotNone(result.best)
            self.assertLess(elapsed, 120)


if __name__ == "__main__":
    unittest.main()
