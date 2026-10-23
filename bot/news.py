"""New videos from the games' official YouTube channels, posted to the Discord channels picked with
/genshin-news, /hsr-news and /zzz-news.

YouTube's public feed for a channel (no key, no login) lists its latest uploads; it is read every few minutes and
every new upload, Shorts included, is posted once. Check what the feed sees with
`python -m bot.news game`."""

from __future__ import annotations

import json
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

log = logging.getLogger(__name__)

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
# The official English channels: @GenshinImpact, @HonkaiStarRail, @ZZZ_Official
CHANNELS = {"genshin": "UCiS882YPwZt1NfaM0gR0D9Q", "hsr": "UC2PeMPA8PAOp-bynLoCeMLA", "zzz": "UC2SpC8rL9LaeQriE4YNdyzA"}
SEEN_KEEP = 200
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def parse_feed(xml: str) -> list[tuple[str, str, str]]:
    """(video id, title, link) of a channel feed's entries, newest first. A Short keeps its /shorts/ link."""
    videos = []
    for entry in ET.fromstring(xml).findall("a:entry", NS):
        vid = entry.findtext("yt:videoId", "", NS)
        title = entry.findtext("a:title", "", NS)
        link = (entry.find("a:link", NS).get("href") if entry.find("a:link", NS) is not None else "") or ""
        if vid:
            short = "/shorts/" in link
            videos.append((vid, title, f"https://www.youtube.com/{'shorts/' if short else 'watch?v='}{vid}"))
    return videos


class NewsStore:
    """Which Discord channel each server wants each game's videos in, and the videos already handled."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.channels: dict[str, dict[str, int]] = {game: {} for game in CHANNELS}  # game -> guild id -> channel id
        self.seen: dict[str, list[str]] = {}  # game -> video ids; a game is missing until its feed was first read
        self.shorts_seen: set[str] = set(CHANNELS)  # games whose seen list already counts Shorts
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for game in CHANNELS:
                self.channels[game].update({str(g): int(c) for g, c in data.get("channels", {}).get(game, {}).items()})
            self.seen = {g: list(ids) for g, ids in data.get("seen", {}).items()}
            # Shorts used to be skipped, so they never made it into seen: those already in the feed aren't news
            self.shorts_seen = set(data.get("shorts_seen", ()))
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            log.exception("Could not read %s", self.path)

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps({"channels": self.channels, "seen": self.seen,
                                       "shorts_seen": sorted(self.shorts_seen)}, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            log.exception("Could not save %s", self.path)

    def set(self, game: str, guild_id: int, channel_id: int | None) -> int | None:
        """Points a server's posts for a game at a channel (None stops them); returns the channel it replaced."""
        old = self.channels[game].pop(str(guild_id), None)
        if channel_id is not None:
            self.channels[game][str(guild_id)] = channel_id
        self._save()
        return old

    def targets(self, game: str) -> list[int]:
        return list(self.channels[game].values())

    def new_videos(self, game: str, videos: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """The videos not handled yet, oldest first, and marks every listed video handled. The first read of
        a game only remembers what's there, so turning the feature on doesn't post a backlog."""
        first = game not in self.seen
        seen = self.seen.setdefault(game, [])
        fresh = [v for v in videos if v[0] not in seen]
        catch_up = game not in self.shorts_seen  # Shorts from before they were posted: marked handled, not posted
        self.shorts_seen.add(game)
        if not fresh and not first:
            if catch_up:
                self._save()
            return []
        self.seen[game] = ([v[0] for v in fresh] + seen)[:SEEN_KEEP]
        self._save()
        if catch_up:
            fresh = [v for v in fresh if "/shorts/" not in v[2]]
        return [] if first else list(reversed(fresh))


def message(game_name: str, title: str, url: str) -> str:
    return f"New {game_name} video: **{title}**\n{url}"


if __name__ == "__main__":  # python -m bot.news zzz: what the feed lists
    import urllib.request

    game = sys.argv[1] if len(sys.argv) > 1 else "zzz"
    req = urllib.request.Request(FEED.format(CHANNELS[game]), headers={"User-Agent": "Mozilla/5.0"})
    xml = urllib.request.urlopen(req, timeout=20).read().decode()
    root = ET.fromstring(xml)
    print("Channel:", root.findtext("a:title", "", NS))
    for _, title, _ in parse_feed(xml):
        print(title)
