import datetime as dt
import unittest

import genshin

from bot import patch

NOW = 1792000000
DAY = 86400


def _item(i, name, rarity, cone=False):
    d = {"item_id": i, "item_name": name, "avatar_base_type": 1, "rarity": rarity, "wiki_url": "", "is_forward": True}
    if cone:
        d["item_url"] = f"https://x/{i}.png"
    else:
        d.update(icon_url=f"https://x/{i}.png", item_avatar_icon_path="", damage_type=1)
    return d


def _time(start, end):
    return {"start_ts": str(start), "end_ts": str(end), "now": str(NOW), "start_time": {"year": 1}, "end_time": {"year": 1}}


def _warp(start, end, version, characters=(), cones=()):
    return {"time_info": _time(start, end), "name": "Warp", "type": "CardPoolRole", "avatar_list": list(characters),
            "equip_list": list(cones), "is_after_version": False, "version": version, "id": 1}


def calendar(events=()):
    end = NOW + 12 * DAY + 4 * 3600
    return genshin.models.HSREventCalendar(**{
        "avatar_card_pool_list": [
            _warp(NOW - 5 * DAY, end, "3.6", [_item(1415, "Cyrene", 5), _item(1101, "Bronya", 4), _item(1102, "Seele", 4)]),
            _warp(NOW - 5 * DAY, end, "3.6", [_item(1308, "Acheron", 5)]),
            _warp(NOW + 13 * DAY, NOW + 30 * DAY, "3.7", [_item(1500, "Next One", 5)]),
        ],
        "equip_card_pool_list": [_warp(NOW - 5 * DAY, end, "3.6", cones=[_item(23050, "A Cone", 5, True)])],
        "act_list": [*events], "challenge_list": [], "cur_game_version": "3.6", "now": str(NOW)})


def _event(start, end, version, kind="ActTimeTypeDefault"):
    return {"time_info": _time(start, end), "id": 9, "version": version, "name": "Event", "panel_desc": "",
            "act_type": "ActivityTypeOther", "act_time_type": kind, "act_status": "OtherActStatusUnFinish",
            "reward_list": [], "total_progress": 0, "current_progress": 0, "special_reward": {"item_id": 0, "name": "", "icon": "", "wiki_url": "", "num": 0, "rarity": 0},
            "is_after_version": False, "all_finished": False, "show_text": "", "strategy": "",
            "multiple_drop_type": 0, "multiple_drop_type_list": [], "count_refresh_type": 0, "count_value": 0,
            "drop_multiple": 0, "panel_id": 0, "sort_weight": 0}


class PatchTest(unittest.TestCase):
    def test_main_event_marks_the_version_end_in_the_first_half(self):
        events = [_event(NOW - 10 * DAY, NOW + 30 * DAY, "3.6"),  # the main event, the whole version
                  _event(NOW - 10 * DAY, NOW + 90 * DAY, "3.6", "ActTimeTypeLong"),  # e.g. Simulated Universe
                  _event(NOW - DAY, NOW + 40 * DAY, "3.7"),  # the next version's
                  _event(NOW - DAY, NOW + 3 * DAY, "3.6")]  # a short one
        info = patch.hsr_patch(calendar(events))
        self.assertEqual(int(info.end.timestamp()), NOW + 30 * DAY)

    def test_reads_version_end_and_running_warps(self):
        info = patch.hsr_patch(calendar())
        self.assertEqual(info.version, "3.6")
        self.assertEqual(int(info.end.timestamp()), NOW + 12 * DAY + 4 * 3600)
        self.assertEqual([(b.kind, b.featured, b.others) for b in patch._running(info.banners, info.now)], [
            ("Character warps", ["Cyrene"], ["Bronya", "Seele"]), ("Character warps", ["Acheron"], []), ("Light cone warps", ["A Cone"], [])])

    def test_mid_version_times_move_to_the_players_server(self):
        update, half, end = NOW - 5 * DAY, NOW + 2 * DAY, NOW + 20 * DAY
        cal = genshin.models.HSREventCalendar(**{
            "avatar_card_pool_list": [_warp(update, half, "3.6", [_item(1, "First", 5)]),
                                      _warp(half, end, "3.6", [_item(2, "Second", 5)])],
            "equip_card_pool_list": [], "act_list": [], "challenge_list": [], "cur_game_version": "3.6", "now": str(NOW)})
        info = patch.for_server(patch.hsr_patch(cal), "Europe", "Asia")  # Asia's clock is 7 hours ahead
        first, second = info.banners
        self.assertEqual(int(first.start.timestamp()), update)  # the update: the same moment everywhere
        self.assertEqual(int(first.end.timestamp()), half - 7 * 3600)
        self.assertEqual(int(second.start.timestamp()), half - 7 * 3600)
        self.assertEqual(int(second.end.timestamp()), end)
        self.assertIn("Asia servers", patch.patch_embed(info).footer.text)
        self.assertIs(patch.for_server(info, "Europe", None), info)

    def test_time_left(self):
        self.assertEqual(patch.time_left(dt.timedelta(days=12, hours=4, minutes=30)), "12 days 4 hours")
        self.assertEqual(patch.time_left(dt.timedelta(hours=5, minutes=12)), "5 hours 12 minutes")
        self.assertEqual(patch.time_left(dt.timedelta(days=1, hours=1)), "1 day 1 hour")

    def test_embed(self):
        cal = calendar()
        embed = patch.patch_embed(patch.hsr_patch(cal))
        self.assertEqual(embed.title, "Honkai: Star Rail · Version 3.6")
        self.assertIn("12 days 4 hours", embed.description)
        self.assertIn("**Cyrene**", embed.fields[0].value)
        self.assertNotIn("Next One", embed.fields[0].value)


def _gi_pool(i, version, start, end, characters=(), weapons=()):
    return {"pool_id": i, "version_name": version, "pool_name": "Wish", "pool_type": 1, "avatars": list(characters),
            "weapon": list(weapons), "start_timestamp": str(start), "end_timestamp": str(end),
            "start_time": {"year": 2026, "month": 10, "day": 9, "hour": 18, "minute": 0, "second": 0}, "end_time": {"year": 2026, "month": 10, "day": 26, "hour": 14, "minute": 59, "second": 0}, "jump_url": "", "pool_status": 1,
            "countdown_seconds": 0}


def _gi_char(i, name, rarity):
    return {"id": i, "icon": f"https://x/{i}.png", "name": name, "element": "Hydro", "rarity": rarity}


class GenshinPatchTest(unittest.TestCase):
    def test_version_from_running_wishes(self):
        end = NOW + 12 * DAY
        cal = genshin.models.GenshinEventCalendar(**{
            "avatar_card_pool_list": [_gi_pool(1, "6.1", NOW - 5 * DAY, end, [_gi_char(1, "Furina", 5), _gi_char(2, "Xingqiu", 4)])],
            "weapon_card_pool_list": [_gi_pool(2, "6.1", NOW - 5 * DAY, end, weapons=[
                {"id": 9, "icon": "", "rarity": 5, "name": "Splendor", "wiki_url": ""}])],
            "mixed_card_pool_list": [], "act_list": [], "fixed_act_list": []})
        info = patch.genshin_patch(cal, patch._utc(NOW))
        self.assertEqual(info.version, "6.1")
        self.assertEqual(int(info.end.timestamp()), end)
        self.assertEqual([(b.kind, b.featured, b.others) for b in info.banners], [
            ("Character event wishes", ["Furina"], ["Xingqiu"]), ("Weapon event wish", ["Splendor"], [])])


class ZzzPatchTest(unittest.TestCase):
    def test_channels_with_reruns_and_engine_names(self):
        def pool(kind, version, start, end, key, items):
            return {"gacha_type": kind, "gacha_state": "GACHA_STATE_IN_PROGRESS", "version": version,
                    "start_ts": str(start), "end_ts": str(end), "left_start_ts": "0", "left_end_ts": "0",
                    "sup_lock_show": False, "insurance_id": 0, key: items}

        def agent(i, name, rarity):
            return {"avatar_id": i, "avatar_name": name, "full_name": name, "rarity": rarity, "icon": "",
                    "avatar_profession": 1, "avatar_element_type": 200, "avatar_sub_element_type": 0, "wiki_url": "",
                    "jump_cultivate": False, "is_forward": True, "show_upon": True}

        end = NOW + 10 * DAY
        gacha = genshin.models.ZZZGachaCalendar(**{
            "avatar_gacha_schedule_list": [
                pool("GACHA_TYPE_CHARACTER_UP", "2.3", NOW - DAY, end, "avatar_list", [agent(1, "Yixuan", "S"), agent(2, "Pan", "A")]),
                pool("GACHA_TYPE_CHARACTER_RETURN", "2.3", NOW - DAY, end, "avatar_list", [agent(3, "Miyabi", "S")])],
            "weapon_gacha_schedule_list": [pool("GACHA_TYPE_WEAPON_UP", "2.3", NOW - DAY, end, "weapon_list", [
                {"weapon_id": 14000, "rarity": "S", "icon": "", "profession": 1, "talent_title": "Some Skill",
                 "talent_content": "", "wiki_url": "", "show_upon": True}])]})
        event = genshin.models.ZZZEvent(**{"activity_id": 1, "state": "STATE_IN_PROGRESS", "name": "Main",
                                           "monochrome_got_cnt": 0, "monochrome_cnt": 0, "start_ts": str(NOW - 10 * DAY),
                                           "end_ts": str(NOW + 25 * DAY), "left_start_ts": "0", "left_end_ts": "0"})
        info = patch.zzz_patch(gacha, [event], {14000: "Qingming Birdcage"}.get, patch._utc(NOW))
        self.assertEqual(info.version, "2.3")
        self.assertEqual(int(info.end.timestamp()), NOW + 25 * DAY)  # the main event outlasts the first half's channels
        self.assertEqual([(b.kind, b.featured, b.others) for b in info.banners], [
            ("Exclusive channels", ["Yixuan"], ["Pan"]), ("Exclusive rescreening", ["Miyabi"], []),
            ("W-Engine channels", ["Qingming Birdcage"], [])])
        self.assertIn("Exclusive rescreening", [f.name for f in patch.patch_embed(info).fields])
        self.assertEqual(info.banners[0].traits["Yixuan"], [
            "https://static.nanoka.cc/assets/zzz/IconPhysical.webp", "https://enka.network/ui/zzz/IconAttack.png"])
        self.assertEqual(info.banners[2].traits["Qingming Birdcage"], ["https://enka.network/ui/zzz/IconAttack.png"])


if __name__ == "__main__":
    unittest.main()


class PatchCardTest(unittest.TestCase):
    def test_draws_without_pictures(self):
        import io
        from PIL import Image
        from bot.patch_card import draw_patch
        info = patch.hsr_patch(calendar([_event(NOW - 10 * DAY, NOW + 30 * DAY, "3.6")]))
        info.server = "Europe"
        png = draw_patch(info, {}, info.now)
        self.assertEqual(Image.open(io.BytesIO(png)).width, 1200)
        self.assertEqual(info.banners[0].items[0][:2], ("Cyrene", True))

    def test_zzz_dashboard_draws_without_pictures(self):
        import io
        from PIL import Image
        from bot.patch_card import draw_patch
        now = patch._utc(NOW)
        running = patch.Banner("Exclusive channels", ["Ellen", "Caesar"], ["Lucy"], now - dt.timedelta(days=5), now + dt.timedelta(days=5), None, "3.2",
                               [("Ellen", True, None), ("Caesar", True, None), ("Lucy", False, None)])
        coming = patch.Banner("W-Engine channels", ["Steel Cushion"], [], now + dt.timedelta(days=5), now + dt.timedelta(days=20), None, "3.2",
                              [("Steel Cushion", True, None)])
        info = patch.Patch("zzz", "3.2", now, now + dt.timedelta(days=20), [running, coming], "Europe")
        png = draw_patch(info, {}, now)
        self.assertEqual(Image.open(io.BytesIO(png)).width, 1200)


class UnknownCharactersTest(unittest.TestCase):
    def test_running_featured_not_in_game_data(self):
        info = patch.hsr_patch(calendar())
        self.assertEqual(patch.unknown_characters(info, ["Acheron", "Bronya"], info.now), ["Cyrene"])  # "Next One" isn't out yet
        self.assertEqual(patch.unknown_characters(info, ["Acheron", "Cyrene"], info.now), [])


class UnitTraitsTest(unittest.TestCase):
    def test_symbols(self):
        import tempfile
        from bot import unit_traits as ut
        traits = ut.UnitTraits(tempfile.mkdtemp())
        traits.table["hsr"]["1500"] = ["Quantum", "Memory"]
        traits.table["gi"]["10000150"] = ["Cryo", "WEAPON_SWORD_ONE_HAND"]
        # Star Rail: Hakushin's element and path; without an entry, only the calendar's path number
        self.assertEqual([u.rsplit("/", 1)[1] for u in traits.hsr(1500, 1)], ["Quantum.png", "Remembrance.png"])
        self.assertEqual([u.rsplit("/", 1)[1] for u in traits.hsr(23050, 2)], ["Hunt.png"])
        # Genshin: Cryo has no icon to download, so the card draws its snowflake
        self.assertEqual(traits.genshin(10000150)[0], ut.CRYO)
        self.assertIn("UI_Buff_Element_Fire", traits.genshin(1, "Pyro")[0])
        # ZZZ: a sub-element picks Frost / Auric Ink
        self.assertIn("IconFrost", ut.zzz_urls(202, 1, 3)[0])
        self.assertIn("IconAnomaly", ut.zzz_urls(202, 1, 3)[1])
        info = patch.hsr_patch(calendar(), traits)
        self.assertEqual(len(info.banners[0].traits["Cyrene"]), 1)  # path only: no Hakushin entry for 1415 here
