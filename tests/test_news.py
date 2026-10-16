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
        self.assertEqual([v[0] for v in videos], ["b", "a"])  # Shorts left out
        self.assertEqual(videos[0][2], "https://www.youtube.com/watch?v=b")

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
