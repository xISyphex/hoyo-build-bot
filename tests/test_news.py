import tempfile
import unittest
from pathlib import Path

from bot import news

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
 <title>Zenless Zone Zero</title>
 {}
</feed>"""


def entry(vid, title, shorts=False):
    link = f"https://www.youtube.com/{'shorts/' if shorts else 'watch?v='}{vid}"
    return f"<entry><yt:videoId>{vid}</yt:videoId><title>{title}</title><link rel=\"alternate\" href=\"{link}\"/></entry>"


class NewsTest(unittest.TestCase):
    def test_parse(self):
        xml = FEED.format(entry("b", "Agent Demo - Miyabi | Zenless Zone Zero") + entry("s", "Agent Demo", True)
                          + entry("a", "Version 2.0 Special Program"))
        videos = news.parse_feed(xml)
        self.assertEqual([v[0] for v in videos], ["b", "s", "a"])  # Shorts included
        self.assertEqual(videos[0][2], "https://www.youtube.com/watch?v=b")
        self.assertEqual(videos[1][2], "https://www.youtube.com/shorts/s")

    def test_shorts_from_before_the_switch_are_not_posted(self):
        path = Path(tempfile.mkdtemp()) / "news.json"
        path.write_text('{"channels": {}, "seen": {"zzz": ["1"]}}', encoding="utf-8")  # saved when Shorts were skipped
        store = news.NewsStore(path)
        old_short = ("s1", "Short", "https://www.youtube.com/shorts/s1")
        video = ("2", "Special Program", "https://www.youtube.com/watch?v=2")
        self.assertEqual(store.new_videos("zzz", [video, old_short, ("1", "Old", "u1")]), [video])
        new_short = ("s2", "New Short", "https://www.youtube.com/shorts/s2")
        self.assertEqual(news.NewsStore(path).new_videos("zzz", [new_short, video, old_short]), [new_short])

    def test_first_read_posts_nothing_then_each_new_video_once(self):
        store = news.NewsStore(Path(tempfile.mkdtemp()) / "news.json")
        old = [("1", "Agent Demo - Old", "u1")]
        self.assertEqual(store.new_videos("zzz", old), [])  # no backlog when it's switched on
        new = [("3", "EP: New Song", "u3"), ("2", "Special Program", "u2")] + old
        self.assertEqual(store.new_videos("zzz", new), [("2", "Special Program", "u2"), ("3", "EP: New Song", "u3")])
        self.assertEqual(store.new_videos("zzz", new), [])  # posted once
        store.set("zzz", 10, 20)
        again = news.NewsStore(store.path)
        self.assertEqual(again.targets("zzz"), [20])
        self.assertEqual(again.seen["zzz"][:3], ["3", "2", "1"])
        self.assertEqual(again.set("zzz", 10, None), 20)
        self.assertEqual(again.targets("zzz"), [])


if __name__ == "__main__":
    unittest.main()
