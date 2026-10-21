"""HoYoLAB characters as build cards, from responses shaped like the Battle Chronicle API (run through genshin.py)."""

from __future__ import annotations

import asyncio
import copy
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import genshin

from bot.assets import Assets
from bot.card import draw_card
from bot.hoyolab import NOTE, HoyolabClient, HoyolabError, genshin_build, starrail_build, zzz_build
import json

from bot.hoyolab_links import LinkStore, cookie_string, games_of, load_key
from bot.main import pick, with_hoyolab
from bot.models import PlayerProfile


def _prop(t, name, filter_name=None):
    return {"property_type": t, "name": name, "icon": "", "filter_name": filter_name or name}


GI_PROPS = {
    "2000": _prop(2000, "Max HP"), "2001": _prop(2001, "ATK"), "2002": _prop(2002, "DEF"),
    "28": _prop(28, "Elemental Mastery"), "20": _prop(20, "CRIT Rate"), "22": _prop(22, "CRIT DMG"),
    "23": _prop(23, "Energy Recharge"), "42": _prop(42, "Hydro DMG Bonus"), "26": _prop(26, "Healing Bonus"),
    "2": _prop(2, "HP"), "4": _prop(4, "Base ATK"), "5": _prop(5, "ATK"), "3": _prop(3, "HP"),
}


def _val(t, final, base="", add=""):
    return {"property_type": t, "base": base, "add": add, "final": final}


def _relic(pos, set_name, main, subs):
    return {
        "id": 80000 + pos, "icon": f"https://example.invalid/relic{pos}.png", "name": f"Piece {pos}",
        "pos_name": "", "pos": pos, "rarity": 5, "level": 20,
        "set": {"id": 1, "name": set_name, "affixes": []},
        "main_property": {"property_type": main[0], "value": main[1], "times": 0},
        "sub_property_list": [{"property_type": t, "value": v, "times": n} for t, v, n in subs],
    }


GENSHIN = {
    "list": [{
        "base": {"id": 10000089, "icon": "https://example.invalid/genshin/UI_AvatarIcon_Furina.png", "name": "Furina", "element": "Hydro", "fetter": 10, "level": 90,
                 "rarity": 5, "actived_constellation_num": 2, "image": "", "is_chosen": False, "weapon_type": 1,
                 "weapon": {}},
        "weapon": {"id": 11513, "icon": "https://example.invalid/sword.png", "name": "Splendor of Tranquil Waters",
                   "rarity": 5, "level": 90, "type": 1, "affix_level": 1, "promote_level": 6, "desc": "",
                   "main_property": _val(4, "542"), "sub_property": _val(22, "88.2%")},
        "relics": [
            _relic(1, "Golden Troupe", (2, "4780"), [(20, "10.5%", 3), (22, "14.0%", 1), (5, "19", 0), (28, "21", 0)]),
            _relic(2, "Golden Troupe", (5, "311"), [(20, "3.9%", 1)]),
            _relic(3, "Golden Troupe", (3, "46.6%"), []),
            _relic(4, "Golden Troupe", (3, "46.6%"), []),
            _relic(5, "Marechaussee Hunter", (22, "62.2%"), []),
        ],
        "constellations": [], "costumes": [],
        "skills": [
            {"skill_id": 1, "skill_type": 1, "name": "Normal", "level": 6, "desc": "", "skill_affix_list": [], "icon": "", "is_unlock": True},
            {"skill_id": 2, "skill_type": 1, "name": "Skill", "level": 10, "desc": "", "skill_affix_list": [], "icon": "", "is_unlock": True},
            {"skill_id": 3, "skill_type": 2, "name": "Passive", "level": 1, "desc": "", "skill_affix_list": [], "icon": "", "is_unlock": True},
            {"skill_id": 4, "skill_type": 1, "name": "Burst", "level": 9, "desc": "", "skill_affix_list": [], "icon": "", "is_unlock": True},
        ],
        "selected_properties": [_val(20, "75.3%"), _val(22, "201.2%")],
        "base_properties": [_val(2000, "38,421"), _val(2001, "1,105"), _val(2002, "780")],
        "extra_properties": [_val(28, "63"), _val(23, "140.2%"), _val(26, "0%")],
        "element_properties": [_val(42, "28.0%")],
    }],
    "property_map": GI_PROPS, "relic_property_options": {}, "relic_wiki": {}, "weapon_wiki": {}, "avatar_wiki": {},
}


def _sr_info(t, name, relic_name=None):
    return {"property_type": t, "name": name, "icon": "", "property_name_relic": relic_name or name,
            "property_name_filter": name}


SR_INFO = {"12": _sr_info(12, "Outgoing Healing Boost"), "1": _sr_info(1, "HP"), "27": _sr_info(27, "HP"), "5": _sr_info(5, "CRIT Rate"),
           "6": _sr_info(6, "CRIT DMG"), "7": _sr_info(7, "SPD"), "9": _sr_info(9, "Energy Regeneration Rate")}


def _sr_relic(pos, rid, detailed):
    relic = {"id": rid, "pos": pos, "rarity": 5, "level": 15, "name": f"Piece {pos}", "desc": "",
             "icon": "", "wiki": ""}
    if detailed:
        relic["main_property"] = {"property_type": 1, "value": "705", "times": 0}
        relic["properties"] = [{"property_type": 5, "value": "6.4%", "times": 2},
                               {"property_type": 27, "value": "4.3%", "times": 1}]
    else:
        relic["main_property"] = None
        relic["properties"] = []
    return relic


def _starrail(detailed):
    char = {
        "id": 1212, "element": "ice", "rarity": 5, "icon": "", "name": "Jingliu", "level": 80, "rank": 2,
        "image": "", "figure_path": "", "base_type": 1, "ranks": [],
        "equip": {"id": 23014, "level": 80, "rank": 1, "name": "I Shall Be My Own Sword", "desc": "", "icon": "",
                  "rarity": 5},
        "relics": [_sr_relic(1, 61041, detailed), _sr_relic(2, 61042, detailed)],
        "ornaments": [_sr_relic(5, 63045, detailed)],
    }
    char["properties"] = []  # other players: HoYoLAB sends empty lists
    if detailed:
        char["properties"] = [
            {"property_type": 1, "base": "", "add": "", "final": "4,302"},
            {"property_type": 7, "base": "", "add": "", "final": "134.0"},
            {"property_type": 5, "base": "", "add": "", "final": "72.4%"},
            {"property_type": 9, "base": "", "add": "", "final": "100.0%"},
            {"property_type": 12, "base": "", "add": "", "final": "0.0%"},
        ]
        char["skills"] = [
            {"point_id": "1", "point_type": 2, "item_url": "", "level": 6, "is_activated": True, "is_rank_work": False,
             "pre_point": "0", "anchor": "Point01", "remake": "", "skill_stages": []},
            {"point_id": "2", "point_type": 2, "item_url": "", "level": 12, "is_activated": True, "is_rank_work": True,
             "pre_point": "0", "anchor": "Point03", "remake": "", "skill_stages": []},
        ]
        char["servant_detail"] = None
    return {
        "avatar_list": [char], "equip_wiki": {}, "relic_wiki": {}, "property_info": SR_INFO,
        "recommend_property": {"1212": {"recommend_relic_properties": [], "custom_relic_properties": [],
                                        "is_custom_property_valid": False}},
        "relic_properties": [],
    }


def _zzz_prop(pid, name, base, final=None):
    return {"property_name": name, "property_id": pid, "base": base, "add": "", "final": final if final is not None else base}


ZZZ = {
    "id": 1191, "element_type": 201, "rarity": "S", "name_mi18n": "Ellen", "full_name_mi18n": "Ellen Joe",
    "avatar_profession": 1, "group_icon_path": "", "hollow_icon_path": "", "role_square_url": "",
    "camp_name_mi18n": "", "level": 60, "rank": 1, "role_vertical_painting_url": "",
    "properties": [_zzz_prop(1, "HP", "7,673"), _zzz_prop(2, "ATK", "2,965"), _zzz_prop(5, "CRIT Rate", "", "68.2%")],
    "equip": [{
        "id": 31441, "level": 15, "name": "Woodpecker Electro [1]", "icon": "", "rarity": "S", "equipment_type": 1,
        "main_properties": [_zzz_prop(11103, "HP", "2,200")],
        "properties": [_zzz_prop(20103, "CRIT Rate", "7.2%"), _zzz_prop(12102, "ATK", "6%"), _zzz_prop(23203, "PEN", "9")],
        "equip_suit": {"suit_id": 314, "name": "Woodpecker Electro", "own": 4, "desc1": "", "desc2": ""},
    }],
    "weapon": {"id": 14119, "level": 60, "name": "Deep Sea Visitor", "icon": "", "star": 1, "rarity": "S",
               "properties": [_zzz_prop(20103, "CRIT Rate", "24%")], "main_properties": [_zzz_prop(12101, "Base ATK", "713")],
               "talent_title": "", "talent_content": "", "profession": 1},
    "skills": [{"level": 12, "skill_type": 0, "items": []}, {"level": 7, "skill_type": 5, "items": []}],
    "ranks": [],
    "skill_awaken": {"has_awaken_system": False, "awaken_level": 0, "awaken_max_level": 0, "skill_awaken_items": []},
}


class HoyolabBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = Assets("data")
        cls.assets.load()

    def test_genshin(self):
        data = genshin.models.GenshinDetailCharacters(**GENSHIN)
        build = genshin_build(self.assets, data.characters[0])
        stats = {s.name: s.value for s in build.stats}
        self.assertEqual(build.name, "Furina")
        self.assertEqual((build.level, build.constellation), (90, 2))
        self.assertEqual(stats["HP"], "38,421")
        self.assertEqual(stats["CRIT DMG"], "201.2%")
        self.assertEqual(stats["Hydro DMG Bonus"], "28.0%")
        self.assertNotIn("Healing Bonus", stats)  # 0% is left out, as on Enka cards
        self.assertEqual([t.value for t in build.talents], ["6", "10", "9"])  # passives skipped
        self.assertEqual(build.weapon.stats[1].name, "CRIT DMG")
        flower = build.gear[0]
        self.assertEqual((flower.slot, flower.main.name, flower.main.value), ("Flower", "HP", "4,780"))
        self.assertEqual([(s.name, s.value, s.rolls) for s in flower.subs[:3]],
                         [("CRIT Rate", "10.5%", 4), ("CRIT DMG", "14.0%", 2), ("ATK", "19", 1)])
        self.assertEqual(build.gear[2].main.name, "HP%")
        self.assertEqual(build.set_bonuses, ["4pc Golden Troupe"])
        self.assertEqual(build.notes, [NOTE])
        self.assertTrue(build.art_url)  # same art as the Enka cards

    def test_starrail_with_details(self):
        data = genshin.models.StarRailDetailCharacterResponse(**_starrail(True))
        build = starrail_build(self.assets, data.avatar_list[0])
        stats = {s.name: s.value for s in build.stats}
        self.assertEqual(build.name, "Jingliu")
        self.assertEqual(build.constellation, 2)
        # 0% Outgoing Healing is left out
        self.assertEqual(stats, {"HP": "4,302", "SPD": "134", "CRIT Rate": "72.4%", "Energy Regen Rate": "100.0%"})
        self.assertEqual([(t.name, t.value) for t in build.talents], [("Basic ATK", "6"), ("Ultimate", "12")])
        self.assertEqual(build.weapon.name, "I Shall Be My Own Sword")
        head = build.gear[0]
        self.assertEqual((head.slot, head.main.name, head.main.value), ("Head", "HP", "705"))
        self.assertEqual([(s.name, s.value) for s in head.subs], [("CRIT Rate", "6.4%"), ("HP%", "4.3%")])
        self.assertEqual(build.gear[-1].slot, "Planar Sphere")

    def test_starrail_without_details(self):
        # Other players' relics come without stats; genshin.py's detailed model can't read that.
        with self.assertRaises(Exception):
            genshin.models.StarRailDetailCharacterResponse(**_starrail(False))
        data = genshin.models.StarRailSimpleCharacterResponse(**_starrail(False))
        build = starrail_build(self.assets, data.avatar_list[0])
        self.assertEqual(build.stats, [])
        self.assertEqual(len(build.gear), 3)
        self.assertEqual((build.gear[0].main.name, build.gear[0].main.value), ("Head", "+15"))
        self.assertIn("doesn't share", build.notes[-1])

    def test_zzz(self):
        build = zzz_build(self.assets, genshin.models.ZZZFullAgent(**ZZZ))
        # HoYoLAB gives only totals, so rolls come from the value: 7.2% CRIT Rate is 3 rolls of 2.4%.
        self.assertEqual([(s.name, s.rolls) for s in build.gear[0].subs], [("CRIT Rate", 3), ("ATK%", 2), ("PEN", 1)])
        self.assertEqual(build.name, "Ellen")
        self.assertEqual((build.level, build.constellation), (60, 1))
        self.assertEqual({s.name: s.value for s in build.stats}["CRIT Rate"], "68.2%")
        disc = build.gear[0]
        self.assertEqual((disc.slot, disc.set_name, disc.main.name, disc.main.value),
                         ("Disc 1", "Woodpecker Electro", "HP", "2,200"))
        self.assertEqual([(s.name, s.value) for s in disc.subs], [("CRIT Rate", "7.2%"), ("ATK%", "6.0%"), ("PEN", "9")])
        self.assertEqual([(s.name, s.value) for s in build.weapon.stats], [("ATK", "713"), ("CRIT Rate", "24.0%")])
        self.assertEqual([(t.name, t.value) for t in build.talents], [("Basic", "12"), ("Core", "F")])

    def _all(self):
        return [
            genshin_build(self.assets, genshin.models.GenshinDetailCharacters(**GENSHIN).characters[0]),
            starrail_build(self.assets, genshin.models.StarRailDetailCharacterResponse(**_starrail(True)).avatar_list[0]),
            starrail_build(self.assets, genshin.models.StarRailSimpleCharacterResponse(**_starrail(False)).avatar_list[0]),
            zzz_build(self.assets, genshin.models.ZZZFullAgent(**ZZZ)),
        ]

    def test_cards_draw(self):
        for build in self._all():
            with self.subTest(build.game):
                self.assertEqual(build.source, "hoyolab")
                self.assertTrue(draw_card(build, {}, uid="618285856").startswith(b"\x89PNG"))

    def test_showcase_wins_and_hoyolab_fills_in(self):
        furina = self._all()[0]
        showcase = genshin_build(self.assets, genshin.models.GenshinDetailCharacters(**GENSHIN).characters[0])
        showcase.source, showcase.character_id = "enka", furina.character_id
        profile = PlayerProfile("genshin", "618285856", "Someone", 60, [showcase], 60, "")
        self.assertEqual(with_hoyolab(profile, [furina]).characters, [showcase])  # no duplicate
        bot = type("Bot", (), {"assets": self.assets})()
        empty = PlayerProfile("genshin", "618285856", "Someone", 60, [], 60, "")
        merged = with_hoyolab(empty, [furina])
        self.assertEqual(pick(bot, "genshin", merged, "furina"), "Furina")
        # A name that isn't in the profile isn't matched to a similar one that is.
        self.assertIsNone(pick(bot, "genshin", merged, "Fischl"))


class HoyolabClientTest(unittest.TestCase):
    def setUp(self):
        self.client = HoyolabClient("ltuid_v2=1; ltoken_v2=v2_x; ltmid_v2=y", Assets("data"))
        self.client.assets.load()
        self.calls = 0

    def _answer(self, result):
        async def call(uid, **kwargs):
            self.calls += 1
            if isinstance(result, Exception):
                raise result
            return result
        return call

    def test_characters_are_kept_for_a_while(self):
        self.client.client.get_genshin_detailed_characters = self._answer(copy.deepcopy(GENSHIN))  # raw data
        for _ in range(2):
            builds = asyncio.run(self.client.fetch("genshin", "618285856"))
        self.assertEqual([b.name for b in builds], ["Furina"])
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.client.cached("genshin", "618285856"), builds)

    def test_records_read_only_the_zzz_agents_they_show(self):
        asked = []

        async def info(ids, uid):
            asked.append(list(ids))
            return [genshin.models.ZZZFullAgent(**ZZZ) for _ in ids]

        self.client.client.get_zzz_agent_info = info
        ellen = str(ZZZ["id"])
        builds = asyncio.run(self.client.zzz_agents("1300003409", [ellen, "1021", "1031", "1041", "1061", "1071"]))
        self.assertEqual(asked, [[int(ellen), 1021, 1031, 1041, 1061], [1071]])  # five at a time, nothing else
        self.assertEqual(builds[0].name, "Ellen")
        # With every agent already read for a lookup, nothing is asked again
        self.client._cache[("zzz", "1300003409")] = (float("inf"), builds[:1])
        asked.clear()
        self.assertEqual([b.name for b in asyncio.run(self.client.zzz_agents("1300003409", [ellen]))], ["Ellen"])
        self.assertEqual(asked, [])

    def test_private_profiles_are_remembered(self):
        private = genshin.DataNotPublic({"retcode": 10102, "message": "Data is not public for the user"})
        self.client.client.get_genshin_detailed_characters = self._answer(private)
        for _ in range(2):
            with self.assertRaisesRegex(HoyolabError, "private"):
                asyncio.run(self.client.fetch("genshin", "618285856"))
        self.assertEqual(self.calls, 1)  # asking again would only use up the 30 UIDs a day

    def test_other_players_builds_are_refused_and_remembered(self):
        refused = genshin.errors.UserNotesAccessDenied({"retcode": 10104, "message": "Cannot view real-time notes of other users."})
        self.client.client.get_genshin_detailed_characters = self._answer(refused)
        for _ in range(2):
            with self.assertRaisesRegex(HoyolabError, "only shares these builds with the player"):
                asyncio.run(self.client.fetch("genshin", "618285856"))
        self.assertEqual(self.calls, 1)

    def test_daily_limit_is_explained(self):
        limit = genshin.TooManyRequests({"retcode": 10101, "message": "Cannot get data for more than 30 accounts"})
        self.client.client.get_starrail_characters = self._answer(limit)
        with self.assertRaisesRegex(HoyolabError, "30 players"):
            asyncio.run(self.client.fetch("hsr", "800069903"))


class LinkTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "data" / "hoyolab_links.json"
        self.key_file = Path(self.dir.name) / ".hoyolab.key"
        self.key = load_key(self.key_file)
        self.links = LinkStore(self.path, self.key)

    def tearDown(self):
        self.dir.cleanup()

    def test_game_accounts_become_uids_per_game(self):
        accounts = [SimpleNamespace(game_biz="hk4e_global", uid=700000001), SimpleNamespace(game_biz="hkrpg_global", uid=714485603),
                    SimpleNamespace(game_biz="bh3_global", uid=1), SimpleNamespace(game_biz="nap_global", uid=1500000001)]
        self.assertEqual(games_of(accounts), {"genshin": ["700000001"], "hsr": ["714485603"], "zzz": ["1500000001"]})
        self.assertEqual(cookie_string(" 1 ", "v2_x", "m"), "ltuid_v2=1; ltoken_v2=v2_x; ltmid_v2=m")

    def test_links_are_private_and_survive_a_restart(self):
        self.links.link(42, "ltuid_v2=1; ltoken_v2=v2_x; ltmid_v2=m", {"hsr": ["714485603"]})
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)  # only the bot's own user can read it
        again = LinkStore(self.path, load_key(self.key_file))  # the same key is read back
        self.assertEqual(again.cookies_for("hsr", "714485603"), "ltuid_v2=1; ltoken_v2=v2_x; ltmid_v2=m")
        self.assertIsNone(again.cookies_for("genshin", "714485603"))
        self.assertEqual(again.unlink(42), {"hsr": ["714485603"]})
        self.assertIsNone(LinkStore(self.path, self.key).cookies_for("hsr", "714485603"))
        self.assertIsNone(again.unlink(42))

    def test_cookies_are_encrypted_with_a_key_outside_the_data_folder(self):
        self.links.link(42, "ltuid_v2=1; ltoken_v2=v2_secret; ltmid_v2=m", {"hsr": ["714485603"]})
        self.assertNotIn("v2_secret", self.path.read_text())
        self.assertEqual(stat.S_IMODE(os.stat(self.key_file).st_mode), 0o600)
        self.assertNotEqual(self.key_file.parent, self.path.parent)
        # With another key (say the data folder was copied to a new server) the links can't be read.
        other = LinkStore(self.path, load_key(Path(self.dir.name) / "other.key"))
        self.assertIsNone(other.cookies_for("hsr", "714485603"))
        self.assertEqual(load_key(self.key_file, env_key="abc="), b"abc=")

    def test_links_saved_before_encryption_get_encrypted(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"42": {"cookies": "ltoken_v2=v2_old", "uids": {"hsr": ["714485603"]}}}))
        links = LinkStore(self.path, self.key)
        self.assertEqual(links.cookies_for("hsr", "714485603"), "ltoken_v2=v2_old")
        self.assertNotIn("v2_old", self.path.read_text())

    def test_a_linked_uid_uses_its_owners_login(self):
        client = HoyolabClient(None, Assets("data"), self.links)
        self.assertFalse(client.available("hsr", "714485603"))  # no server login and nobody linked it
        self.links.link(42, "ltuid_v2=1; ltoken_v2=v2_x; ltmid_v2=m", {"hsr": ["714485603"]})
        self.assertTrue(client.available("hsr", "714485603"))
        linked, own = client._client_for("hsr", "714485603")
        self.assertTrue(own)
        self.assertEqual(dict(linked.cookie_manager.cookies)["ltuid_v2"], "1")
        self.assertFalse(client.available("hsr", "800069903"))
        self.links.unlink(42)
        client.forget({"hsr": ["714485603"]})
        self.assertFalse(client.available("hsr", "714485603"))


if __name__ == "__main__":
    unittest.main()


class ZzzOutfitTest(unittest.TestCase):
    def test_outfit_picture_comes_from_enka_when_known(self):
        assets = Assets("data")
        assets.load()
        plain = zzz_build(assets, genshin.models.ZZZFullAgent(**ZZZ))
        # HoYoLAB names the outfit at the end of the picture's file name
        banner = "https://example.invalid/role_vertical_painting_1191_{}.png"
        known = zzz_build(assets, genshin.models.ZZZFullAgent(**{**ZZZ, "role_vertical_painting_url": banner.format(3111911)}))
        unknown = zzz_build(assets, genshin.models.ZZZFullAgent(**{**ZZZ, "role_vertical_painting_url": banner.format(3119999)}))
        self.assertTrue(known.art_url.startswith("https://enka.network/ui/zzz/"))
        self.assertNotEqual(known.art_url, plain.art_url)
        self.assertEqual(unknown.art_url, banner.format(3119999))
