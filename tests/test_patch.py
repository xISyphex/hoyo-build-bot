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


def calendar():
    end = NOW + 12 * DAY + 4 * 3600
    return genshin.models.HSREventCalendar(**{
        "avatar_card_pool_list": [
            _warp(NOW - 5 * DAY, end, "3.6", [_item(1415, "Cyrene", 5), _item(1101, "Bronya", 4), _item(1102, "Seele", 4)]),
            _warp(NOW - 5 * DAY, end, "3.6", [_item(1308, "Acheron", 5)]),
            _warp(NOW + 13 * DAY, NOW + 30 * DAY, "3.7", [_item(1500, "Next One", 5)]),
        ],
        "equip_card_pool_list": [_warp(NOW - 5 * DAY, end, "3.6", cones=[_item(23050, "A Cone", 5, True)])],
        "act_list": [], "challenge_list": [], "cur_game_version": "3.6", "now": str(NOW)})


class PatchTest(unittest.TestCase):
    def test_reads_version_end_and_running_warps(self):
        info = patch.hsr_patch(calendar())
        self.assertEqual(info.version, "3.6")
        self.assertEqual(int(info.end.timestamp()), NOW + 12 * DAY + 4 * 3600)
        self.assertEqual([(b.kind, b.featured, b.others) for b in info.banners], [
            ("character", ["Cyrene"], ["Bronya", "Seele"]), ("character", ["Acheron"], []), ("light cone", ["A Cone"], [])])

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


if __name__ == "__main__":
    unittest.main()
