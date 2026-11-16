"""The optimizer website (bot/web): sessions, the JSON API and the command's two modes. The account is the made-up
test fixture; nothing reaches Discord, Enka or HoYoLAB."""

from __future__ import annotations

import io
import json
import time
import unittest

from aiohttp.test_utils import TestClient, TestServer

from bot import optimize, web
from bot.main import make_optimize_command, optimize_preselect, web_link_text
from bot.web import schema
from bot.web.dev import SAMPLE_SETS, sample_builds
from bot.web.sessions import SessionStore
from tests.test_parsers import load_assets


class Effective:
    """EffectiveStats without its file: no wanted stats, one recommended pair of sets for everyone."""

    updated = 1.0

    def __init__(self, relic: int, planar: int):
        self.sets = {False: [relic], True: [planar]}

    def wanted(self, build):
        return None

    def recommended_sets(self, character_id, planar):
        return self.sets[planar]


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class SessionStoreTest(unittest.TestCase):
    def test_lifecycle(self):
        clock = Clock()
        store = SessionStore(ttl=7200, clock=clock)
        first = store.create(1, "800000001", [])
        self.assertGreaterEqual(len(first.token), 40)
        self.assertIs(store.get(first.token), first)
        self.assertIsNone(store.get(first.token[:-1] + ("A" if first.token[-1] != "A" else "B")))
        self.assertIsNone(store.get(""))
        self.assertIsNone(store.get("x" * 500))
        # a new command replaces the old link; another user's session is untouched
        other = store.create(2, "800000002", [])
        second = store.create(1, "800000001", [], {"character": "1212"})
        self.assertIsNone(store.get(first.token))
        self.assertIs(store.get(second.token), second)
        self.assertIs(store.for_user(1), second)
        self.assertEqual(len(store), 2)
        # expiry after 2 hours
        clock.now += 7199
        self.assertIs(store.get(second.token), second)
        clock.now += 1
        self.assertIsNone(store.get(second.token))
        self.assertIsNone(store.get(other.token))
        self.assertEqual(len(store), 0)

    def test_rate_limit(self):
        session = SessionStore().create(1, "800000001", [])
        for i in range(20):
            self.assertIsNone(session.take_call(100.0 + i))
        self.assertAlmostEqual(session.take_call(130.0), 600 - 30)
        self.assertIsNone(session.take_call(700.0))  # the first call left the window


class ConfigTest(unittest.TestCase):
    def test_off_without_base_url(self):
        self.assertIsNone(web.config_from_env({}))
        self.assertIsNone(web.config_from_env({"WEB_BASE_URL": "  ", "WEB_PORT": "9000"}))

    def test_settings(self):
        config = web.config_from_env({"WEB_BASE_URL": "https://example.ts.net/", "WEB_PORT": "9000"})
        self.assertEqual(config, web.WebConfig("https://example.ts.net", "127.0.0.1", 9000))
        with self.assertRaises(ValueError):
            web.config_from_env({"WEB_BASE_URL": "example.ts.net"})


class CommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()

    def test_web_off_keeps_the_command(self):
        command = make_optimize_command()
        self.assertEqual([(p.name, p.required) for p in command.parameters],
                         [("character", True), ("relic_set", False), ("planar_set", False), ("speed", False), ("uid", False),
                          ("server", False), ("exclude", False)])
        self.assertIn("best relics", command.description)

    def test_web_on_needs_no_options(self):
        command = make_optimize_command(web_on=True)
        self.assertFalse(any(p.required for p in command.parameters))
        self.assertEqual({p.name for p in command.parameters},
                         {"character", "relic_set", "planar_set", "speed", "uid", "server", "exclude"})

    def test_options_become_the_pages_preselection(self):
        _, builds = sample_builds(self.assets)
        chosen, unknown = optimize_preselect(self.assets, builds, "jingliu", "scholar lost", "rutilant", "on",
                                             "castorice, Nobody Here")
        ids = optimize.set_ids(self.assets)
        self.assertEqual(chosen, {"character": "1212", "relic_set": ids[SAMPLE_SETS[0]], "planar_set": ids[SAMPLE_SETS[1]],
                                  "speed": True, "exclude": ["1407"]})
        self.assertEqual(unknown, ["Nobody Here"])
        self.assertEqual(optimize_preselect(self.assets, builds, None, None, None, None, None), ({}, []))
        text = web_link_text("800000001", 8, False, ["Nobody Here"])
        self.assertIn("2 hours", text)
        self.assertIn("/hoyolab link", text)
        self.assertIn("Nobody Here", text)


class ApiTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = load_assets()
        cls.ids = optimize.set_ids(cls.assets)

    async def asyncSetUp(self):
        self.clock = Clock()
        effective = Effective(int(self.ids[SAMPLE_SETS[0]]), int(self.ids[SAMPLE_SETS[1]]))
        self.ctx = web.WebContext(self.assets, effective, None, SessionStore(clock=self.clock), "https://example.ts.net")
        self.uid, builds = sample_builds(self.assets)
        self.session = self.ctx.sessions.create(42, self.uid, builds)
        self.client = TestClient(TestServer(web.make_app(self.ctx)))
        await self.client.start_server()
        self.auth = {"Authorization": f"Bearer {self.session.token}"}

    async def asyncTearDown(self):
        await self.client.close()

    async def post(self, path, body, headers=None):
        data = body if isinstance(body, (bytes, str, io.BytesIO)) else json.dumps(body)
        return await self.client.post(f"/api/hsr/{path}", data=data, headers=self.auth if headers is None else headers)

    def test_link(self):
        self.assertEqual(self.ctx.link(self.session), f"https://example.ts.net/hsr/optimize#{self.session.token}")

    async def test_meta(self):
        resp = await self.client.get("/api/hsr/meta")
        self.assertEqual(resp.status, 200)
        meta = await resp.json()
        self.assertEqual(set(meta), {"version", "characters", "light_cones", "relic_sets", "planar_sets", "slots", "max_level"})
        jingliu = next(c for c in meta["characters"] if c["id"] == "1212")
        self.assertEqual((jingliu["name"], jingliu["rarity"], jingliu["path"], jingliu["element"], jingliu["max_level"]),
                         ("Jingliu", 5, "Destruction", "Ice", 80))
        self.assertTrue(jingliu["icon"].startswith("https://"))
        self.assertEqual([a["type"] for a in jingliu["abilities"]], ["Basic ATK", "Skill", "Ultimate", "Talent"])
        self.assertEqual({a["max_level"] for a in jingliu["abilities"]}, {6, 10})
        self.assertEqual(sum(t["kind"] == "major" for t in jingliu["traces"]), 3)
        self.assertTrue(all(t["stat"]["value"] > 0 for t in jingliu["traces"] if t["kind"] == "stat"))
        self.assertEqual(len(jingliu["eidolons"]), 6)
        self.assertEqual(jingliu["recommended"]["relic"], [self.ids[SAMPLE_SETS[0]]])
        self.assertTrue(all(c["path"] and c["icon"] for c in meta["light_cones"]))
        self.assertTrue(all(int(s["id"]) < 300 and "bonus_4pc" in s for s in meta["relic_sets"]))
        self.assertTrue(all(int(s["id"]) >= 300 and "bonus_4pc" not in s for s in meta["planar_sets"]))
        self.assertIn("max-age", resp.headers["Cache-Control"])
        again = await self.client.get("/api/hsr/meta", headers={"If-None-Match": resp.headers["ETag"]})
        self.assertEqual(again.status, 304)

    async def test_security_headers(self):
        for path in ("/api/hsr/meta", "/hsr/optimize", "/static/js/main.js", "/api/hsr/session", "/nothing"):
            resp = await self.client.get(path)
            with self.subTest(path=path):
                csp = resp.headers["Content-Security-Policy"]
                self.assertIn("frame-ancestors 'none'", csp)
                self.assertIn("https://enka.network", csp)
                self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(resp.headers["Referrer-Policy"], "no-referrer")
                self.assertNotIn("Access-Control-Allow-Origin", resp.headers)
        page = await self.client.get("/hsr/optimize")
        self.assertEqual(page.status, 200)
        self.assertIn("/static/js/main.js", await page.text())
        self.assertEqual((await self.client.get("/static/fonts/Rajdhani-Bold.ttf")).status, 200)
        self.assertEqual((await self.client.get("/static/fonts/Rubik-Variable.ttf")).status, 404)
        self.assertEqual((await self.client.get("/static/../web/app.py")).status, 404)

    async def test_auth_failures(self):
        cases = [({}, "missing token"), ({"Authorization": "Basic abc"}, "missing token"),
                 ({"Authorization": "Bearer nope"}, "session expired")]
        for headers, message in cases:
            for method, path in (("GET", "session"), ("POST", "optimize"), ("POST", "relics/import")):
                with self.subTest(headers=headers, path=path):
                    resp = await self.client.request(method, f"/api/hsr/{path}", headers=headers, data="{}")
                    self.assertEqual(resp.status, 401)
                    self.assertEqual((await resp.json())["error"], message)
        self.clock.now += 2 * 3600
        resp = await self.client.get("/api/hsr/session", headers=self.auth)
        self.assertEqual(resp.status, 401)
        self.assertIn("/hsr-optimize", (await resp.json())["hint"])

    async def test_unknown_routes_are_json(self):
        resp = await self.client.get("/api/hsr/nothing")
        self.assertEqual((resp.status, await resp.json()), (404, {"error": "not found"}))
        resp = await self.client.delete("/api/hsr/meta")
        self.assertEqual((resp.status, await resp.json()), (405, {"error": "method not allowed"}))

    async def test_session(self):
        resp = await self.client.get("/api/hsr/session", headers=self.auth)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(set(data), {"player", "expires_at", "preselect", "characters", "relics"})
        self.assertEqual(data["player"], {"uid": self.uid})
        self.assertEqual(len(data["characters"]), 8)
        self.assertEqual(len(data["relics"]), 48)
        castorice = next(c for c in data["characters"] if c["id"] == "1407")
        self.assertEqual((castorice["level"], castorice["eidolon"], castorice["ascension"]), (80, 2, 6))
        self.assertEqual(castorice["light_cone"]["name"], "Make Farewells More Beautiful")
        self.assertEqual(castorice["abilities"]["1407002"], 10)
        self.assertIn("1407101", castorice["traces"])
        self.assertEqual(len(castorice["relics"]), 6)
        relic = next(r for r in data["relics"] if r["id"] == castorice["relics"][0])
        self.assertEqual(set(relic), {"id", "set_id", "set_name", "slot", "rarity", "level", "main", "subs", "icon", "owner",
                                      "owner_name", "readable"})
        self.assertEqual((relic["owner"], relic["slot"], relic["set_id"]), ("1407", "Head", self.ids[SAMPLE_SETS[0]]))
        self.assertEqual(set(relic["subs"][0]), {"name", "value", "rolls"})
        self.assertEqual(len({r["id"] for r in data["relics"]}), 48)
        again = await (await self.client.get("/api/hsr/session", headers=self.auth)).json()
        self.assertEqual([r["id"] for r in again["relics"]], [r["id"] for r in data["relics"]])  # stable

    def config(self, **options):
        return {"character": {"id": "1212", "level": 80, "ascension": 6, "eidolon": 0, "abilities": {"1212002": 10},
                              "traces": ["1212101"], "light_cone": {"id": "23014", "level": 80, "rank": 1}},
                "teammates": [{"id": "1306", "eidolon": 0, "light_cone": None, "relic_set": None, "planar_set": None}],
                "options": {"relic_set": self.ids[SAMPLE_SETS[0]], "planar_set": self.ids[SAMPLE_SETS[1]], "speed": None,
                            "exclude": [], **options}}

    async def test_optimize_round_trip(self):
        resp = await self.post("optimize", self.config(exclude=["1407"]))
        self.assertEqual(resp.status, 200, await resp.text())
        result = await resp.json()
        self.assertEqual(result["character"], {"id": "1212", "name": "Jingliu", "source": "enka"})
        self.assertEqual([r["slot"] for r in result["relics"]], ["Head", "Hands", "Body", "Feet", "Planar Sphere", "Link Rope"])
        self.assertNotIn("1407", {r["owner"] for r in result["relics"]})
        session = await (await self.client.get("/api/hsr/session", headers=self.auth)).json()
        self.assertTrue({r["id"] for r in result["relics"]} <= {r["id"] for r in session["relics"]})
        self.assertGreater(result["score"], 0)
        self.assertAlmostEqual(result["score_gain"], (result["score"] / result["current_score"] - 1) * 100)
        self.assertIn("CRIT Rate", [s["name"] for s in result["stats"]])
        self.assertEqual(result["relic_set"]["name"], SAMPLE_SETS[0])
        self.assertEqual(result["ignored"], ["character.abilities", "character.ascension", "character.eidolon",
                                             "character.level", "character.light_cone", "character.traces", "teammates"])
        # the same as the engine run directly
        builds = self.session.builds
        target = next(b for b in builds if b.character_id == "1212")
        direct = optimize.optimize(self.assets, target, builds, *SAMPLE_SETS, optimize.with_speed(None, None), {"Castorice"})
        self.assertAlmostEqual(result["score"], direct.index)

    async def test_optimize_defaults_and_unowned(self):
        body = {"character": {"id": "1006"}}  # Silver Wolf isn't on the account: fully built, game's sets
        resp = await self.post("optimize", body)
        self.assertEqual(resp.status, 200, await resp.text())
        result = await resp.json()
        self.assertEqual((result["character"]["source"], result["current_score"], result["ignored"]), ("unowned", None, []))
        self.assertEqual(result["planar_set"]["name"], SAMPLE_SETS[1])
        resp = await self.post("optimize", {"character": {"id": "1006"}, "options": {"relic_set": self.ids["Musketeer of Wild Wheat"]}})
        self.assertEqual(resp.status, 422)
        self.assertIn("Musketeer of Wild Wheat", (await resp.json())["error"])
        resp = await self.post("optimize", {"character": {"id": "1006"}, "options": {"exclude": ["1006"]}})
        self.assertEqual(resp.status, 422)

    async def test_validation(self):
        bad = self.config()
        bad["character"].update(level=81, ascension=2, bogus=True, abilities={"1212002": 11, "9999": 1},
                                traces=["1006101"], light_cone={"id": "1", "rank": 6})
        bad["teammates"] = [{"id": "1212"}, {"id": "1306", "eidolon": 7}, {"id": "1407"}, {"id": "1409"}]
        bad["options"].update(relic_set=self.ids[SAMPLE_SETS[1]], speed="yes")
        resp = await self.post("optimize", bad)
        self.assertEqual(resp.status, 400)
        data = await resp.json()
        fields = {d["field"] for d in data["details"]}
        self.assertEqual(data["error"], "invalid request")
        self.assertTrue({"character.bogus", "character.level", "character.abilities.1212002", "character.abilities.9999",
                         "character.traces[0]", "character.light_cone.id", "character.light_cone.rank", "teammates",
                         "options.relic_set", "options.speed"} <= fields, fields)
        bad = self.config()
        bad["teammates"] = [{"id": "1212"}, {"id": "1306", "eidolon": 7}]
        bad["character"]["ascension"] = 3
        details = (await (await self.post("optimize", bad)).json())["details"]
        self.assertEqual({d["field"] for d in details}, {"teammates[0].id", "teammates[1].eidolon", "character.ascension"})
        for body, status in ((b"not json", 400), ([], 400), ({}, 400), ({"character": {"id": "99999"}}, 400),
                             (b"{" + b" " * (70 * 1024) + b"}", 413)):
            with self.subTest(body=str(body)[:30]):
                self.assertEqual((await self.post("optimize", body)).status, status)

    def test_ascension_rules(self):
        self.assertEqual([schema.ascension_for(n) for n in (1, 20, 21, 30, 31, 79, 80)], [0, 0, 1, 1, 2, 6, 6])
        self.assertTrue(schema.ascension_fits(20, 1))
        self.assertFalse(schema.ascension_fits(21, 0))
        self.assertFalse(schema.ascension_fits(50, 6))

    async def test_one_run_at_a_time_and_rate_limit(self):
        self.session.busy = True
        self.assertEqual((await self.post("optimize", self.config())).status, 409)
        self.session.busy = False
        self.session.calls.extend([time.time()] * 20)  # the limit counts real time
        resp = await self.post("optimize", self.config())
        self.assertEqual(resp.status, 429)
        self.assertIn("Retry-After", resp.headers)

    async def test_relic_import_placeholder(self):
        resp = await self.post("relics/import", b'{"relics": []}')
        self.assertEqual((resp.status, await resp.json()), (501, {"error": "not implemented"}))
        self.assertEqual((await self.post("relics/import", b"nope")).status, 400)
        resp = await self.post("relics/import", io.BytesIO(b"x" * (5 * 1024 * 1024 + 1)))
        self.assertEqual(resp.status, 413)


if __name__ == "__main__":
    unittest.main()
