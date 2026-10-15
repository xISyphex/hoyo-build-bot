"""The pull minigame: /daily hands out one pull for each game you've claimed a UID in, /<game>-pull spends them on a
banner that's running in the real game right now, and /<game>-box shows the 4-star and 5-star items pulled so far.

The odds follow each game's published rates and pity (soft pity, the 50/50 and its guarantee, a 4-star at least every
10 pulls). Simplified on purpose: no Capturing Radiance or Epitomized Path, and off-banner 4-stars come from every
4-star in the game data. Only counts are saved (pulls, pity, and how many of each 4/5-star item), so the file stays
small: even a player with every 4- and 5-star in all three games takes a few kilobytes.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import os
import random
from pathlib import Path

log = logging.getLogger("hoyo-bot")

# The daily reset: 04:00 at UTC+2, all year (no summer time), the same moment for everyone
RESET_UTC_OFFSET = dt.timedelta(hours=2)
RESET_HOUR = 4
MAX_PULLS = 10  # per /<game>-pull


def day_key(now: dt.datetime) -> str:
    """The minigame day `now` falls in: it starts at the 04:00 UTC+2 reset."""
    return (now.astimezone(dt.timezone.utc) + RESET_UTC_OFFSET - dt.timedelta(hours=RESET_HOUR)).date().isoformat()


def next_reset(now: dt.datetime) -> dt.datetime:
    day = dt.date.fromisoformat(day_key(now)) + dt.timedelta(days=1)
    local = dt.datetime.combine(day, dt.time(RESET_HOUR), tzinfo=dt.timezone(RESET_UTC_OFFSET))
    return local.astimezone(dt.timezone.utc)


@dataclasses.dataclass(frozen=True)
class Rule:
    """One banner type's odds. top/mid are the base 5-star and 4-star rates; from pull `soft` on, the 5-star rate
    climbs by `step` a pull until `hard` makes it certain. `featured` is the chance a 5-star is the banner's own."""
    top: float
    mid: float
    soft: int
    hard: int
    step: float
    featured: float
    mid_hard: int = 10
    mid_featured: float = 0.5


RULES = {
    ("genshin", "character"): Rule(0.006, 0.051, 74, 90, 0.06, 0.5),
    ("genshin", "weapon"): Rule(0.007, 0.060, 63, 80, 0.07, 0.75, mid_featured=0.75),
    ("hsr", "character"): Rule(0.006, 0.051, 74, 90, 0.06, 0.5),
    ("hsr", "weapon"): Rule(0.008, 0.066, 66, 80, 0.07, 0.75, mid_featured=0.75),
    ("zzz", "character"): Rule(0.006, 0.094, 74, 90, 0.06, 0.5),
    ("zzz", "weapon"): Rule(0.010, 0.150, 65, 80, 0.07, 0.75, mid_featured=0.75),
}

# Which pity a banner uses; Genshin's Chronicled Wish isn't offered
BANNER_KINDS = {
    "Character event wishes": "character", "Weapon event wish": "weapon",
    "Character warps": "character", "Light cone warps": "weapon",
    "Exclusive channels": "character", "Exclusive rescreening": "character",
    "W-Engine channels": "weapon", "W-Engine reverberation": "weapon",
}

# What a lost 50/50 (or 75/25) gives: the standard banner's 5-stars
STANDARD = {
    ("genshin", "character"): ("Diluc", "Jean", "Keqing", "Mona", "Qiqi", "Tighnari", "Dehya"),
    ("genshin", "weapon"): ("Amos' Bow", "Skyward Harp", "Skyward Blade", "Skyward Pride", "Skyward Spine",
                            "Skyward Atlas", "Aquila Favonia", "Lost Prayer to the Sacred Winds",
                            "Primordial Jade Winged-Spear", "Wolf's Gravestone"),
    ("hsr", "character"): ("Himeko", "Welt", "Bronya", "Gepard", "Clara", "Yanqing", "Bailu"),
    ("hsr", "weapon"): ("Night on the Milky Way", "In the Name of the World", "Something Irreplaceable",
                        "But the Battle Isn't Over", "Time Waits for No One", "Moment of Victory",
                        "Sleep Like the Dead"),
    ("zzz", "character"): ("Grace", "Koleda", "Lycaon", "Nekomata", "Rina", "Soldier 11"),
    ("zzz", "weapon"): ("Fusion Compiler", "Hellfire Gears", "The Restrained", "Steel Cushion", "The Brimstone",
                        "Weeping Cradle"),
}
# Genshin's game data has many 4-star weapons that are never in wishes (event, shop, battle pass), so its wish pool
# is listed here; the other games' 4-stars come from the game data.
GENSHIN_WEAPONS_4 = (
    "The Flute", "Lion's Roar", "Sacrificial Sword", "Favonius Sword", "The Bell", "Rainslasher",
    "Sacrificial Greatsword", "Favonius Greatsword", "Dragon's Bane", "Favonius Lance", "Eye of Perception",
    "The Widsith", "Sacrificial Fragments", "Favonius Codex", "Rust", "The Stringless", "Sacrificial Bow",
    "Favonius Warbow",
)
NOT_IN_WISHES = {"Amber", "Kaeya", "Lisa"}  # Genshin's starter 4-stars
THREE_STAR = {"genshin": "3★ weapon", "hsr": "3★ light cone", "zzz": "B-rank W-Engine"}


@dataclasses.dataclass
class Pool:
    """The off-banner 4-stars of a game."""
    characters: list[str]
    weapons: list[str]
    threes: list[str] = dataclasses.field(default_factory=list)  # 3-star / B-rank weapons


def pool(assets, game: str) -> Pool:
    """Every 4-star (A-rank) character and weapon in the game data, minus the never-pullable ones."""
    d = assets.data
    chars: set[str] = set()
    weapons: set[str] = set()
    threes: set[str] = set()
    if game == "genshin":
        for info in d.get("gi_weapons", {}).values():
            if info.get("Rarity") == 3:
                threes.add(assets.gi_text(info.get("NameTextMapHash")) or "")
        for info in d.get("gi_avatars", {}).values():
            if info.get("QualityType") == "QUALITY_PURPLE":
                chars.add(assets.gi_text(info.get("NameTextMapHash")) or "")
        chars -= NOT_IN_WISHES
        weapons.update(GENSHIN_WEAPONS_4)
    elif game == "hsr":
        for cid, info in d.get("hsr_characters", {}).items():
            if info.get("Rarity") == 4 and int(cid) < 8000:  # 8xxx are the Trailblazer
                chars.add(info.get("Name") or assets.hsr_text(info.get("AvatarName", {}).get("Hash")) or "")
        for info in d.get("hsr_weapons", {}).values():
            name = info.get("Name") or assets.hsr_text(info.get("EquipmentName", {}).get("Hash")) or ""
            if info.get("Rarity") == 4:
                weapons.add(name)
            elif info.get("Rarity") == 3:
                threes.add(name)
    elif game == "zzz":
        for info in d.get("zzz_avatars", {}).values():
            if info.get("Rarity") == 3:  # A-rank
                chars.add(assets.zzz_text(info.get("Name")) or "")
        for info in d.get("zzz_weapons", {}).values():
            if info.get("Rarity") == 3:
                weapons.add(assets.zzz_text(info.get("ItemName")) or "")
            elif info.get("Rarity") == 2:  # B-rank
                threes.add(assets.zzz_text(info.get("ItemName")) or "")

    def clean(names: set[str]) -> list[str]:
        return sorted(n for n in names if n and "{" not in n)

    return Pool(clean(chars), clean(weapons), clean(threes))


@dataclasses.dataclass
class Pull:
    name: str
    rarity: int  # 5, 4 or 3 (ZZZ: S, A, B)
    weapon: bool
    featured: bool = False
    pity: int = 0  # for 5-stars: the pull it came on


@dataclasses.dataclass
class BannerChoice:
    """A running banner as the pull command sees it."""
    kind: str  # "character" or "weapon"
    title: str  # e.g. "Furina" or "Splendor of Tranquil Waters & A Thousand Floating Dreams"
    featured: list[str]
    featured_4: list[str]
    weapons_4: set[str]  # which of featured_4 are weapons (Genshin and Star Rail mix them)
    icons: dict[str, str] = dataclasses.field(default_factory=dict)  # HoYoLAB's pictures of the banner's items


def roll(rule: Rule, kind: str, banner: BannerChoice, game: str, pity: dict, extra: Pool,
         rng: random.Random) -> Pull:
    """One pull. `pity` holds counts since the last 5-star and 4-star and whether the next is guaranteed featured;
    it's updated in place."""
    n = pity.get("five", 0) + 1
    chance = rule.top + max(0, n - rule.soft + 1) * rule.step
    if n >= rule.hard or rng.random() < chance:
        pity["five"] = 0
        pity["four"] = pity.get("four", 0) + 1
        win = pity.get("guarantee", False) or rng.random() < rule.featured
        pity["guarantee"] = not win
        name = rng.choice(banner.featured) if win and banner.featured else rng.choice(STANDARD[(game, kind)])
        return Pull(name, 5, kind == "weapon", win, n)
    pity["five"] = n
    m = pity.get("four", 0) + 1
    if m >= rule.mid_hard or rng.random() < rule.mid / (1 - chance):
        pity["four"] = 0
        win = pity.get("guarantee4", False) or rng.random() < rule.mid_featured
        if win and banner.featured_4:
            pity["guarantee4"] = False
            name = rng.choice(banner.featured_4)
            return Pull(name, 4, name in banner.weapons_4, True)
        pity["guarantee4"] = bool(banner.featured_4)
        weapon = rng.random() < 0.5 if extra.characters and extra.weapons else not extra.characters
        names = extra.weapons if weapon else extra.characters
        if names:
            return Pull(rng.choice(names), 4, weapon)
    else:
        pity["four"] = m
    return Pull(rng.choice(extra.threes) if extra.threes else THREE_STAR[game], 3, True)


class GachaStore:
    """Everyone's pulls, pity and box, saved to one small JSON file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._users: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            log.exception("Could not read %s; starting the minigame afresh", self.path)
            self.path.replace(self.path.with_suffix(".broken.json"))
            return
        if isinstance(data, dict):
            self._users = {str(k): v for k, v in data.items() if isinstance(v, dict)}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._users, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic, so a crash never leaves half a file

    def _user(self, user_id: int) -> dict:
        return self._users.setdefault(str(user_id), {})

    def pulls(self, user_id: int, game: str) -> int:
        return self._users.get(str(user_id), {}).get("pulls", {}).get(game, 0)

    def pity(self, user_id: int, game: str, kind: str) -> dict:
        return dict(self._users.get(str(user_id), {}).get("pity", {}).get(game, {}).get(kind, {}))

    def box(self, user_id: int, game: str) -> dict[str, dict[str, list[int]]]:
        """{"characters"|"weapons": {name: [rarity, copies]}}"""
        return self._users.get(str(user_id), {}).get("box", {}).get(game, {})

    def daily(self, user_id: int, games: list[str], now: dt.datetime) -> dict[str, int] | None:
        """Today's pulls: one per game. None if already collected since the last reset."""
        user = self._user(user_id)
        today = day_key(now)
        if user.get("day") == today:
            return None
        user["day"] = today
        pulls = user.setdefault("pulls", {})
        for game in games:
            pulls[game] = pulls.get(game, 0) + 1
        self._save()
        return {game: pulls[game] for game in games}

    def pull(self, user_id: int, game: str, banner: BannerChoice, count: int, extra: Pool,
             rng: random.Random | None = None) -> list[Pull] | None:
        """Spend `count` pulls on the banner. None if the user hasn't that many."""
        user = self._user(user_id)
        pulls = user.setdefault("pulls", {})
        if count < 1 or pulls.get(game, 0) < count:
            return None
        rng = rng or random.Random()
        rule = RULES[(game, banner.kind)]
        pity = user.setdefault("pity", {}).setdefault(game, {}).setdefault(banner.kind, {})
        results = [roll(rule, banner.kind, banner, game, pity, extra, rng) for _ in range(count)]
        pulls[game] -= count
        box = user.setdefault("box", {}).setdefault(game, {})
        for r in results:
            if r.rarity >= 4:
                entry = box.setdefault("weapons" if r.weapon else "characters", {}).setdefault(r.name, [r.rarity, 0])
                entry[1] += 1
        self._save()
        return results


ENKA = "https://enka.network"


def icon_index(assets, game: str) -> dict[str, str]:
    """Picture URLs for every character and weapon in the game data, by name (for the pull and box cards)."""
    from .games.starrail import SRR_IMAGES

    d = assets.data
    out: dict[str, str] = {}
    if game == "genshin":
        for info in d.get("gi_avatars", {}).values():
            name, side = assets.gi_text(info.get("NameTextMapHash")), info.get("SideIconName")
            if name and side:
                out[name] = ENKA + side.replace("_Side", "")
        for info in d.get("gi_weapons", {}).values():
            name = assets.gi_text(info.get("NameTextMapHash"))
            if name and info.get("Icon"):
                out[name] = ENKA + info["Icon"]
    elif game == "hsr":
        for cid, info in d.get("hsr_characters", {}).items():
            name = info.get("Name") or assets.hsr_text(info.get("AvatarName", {}).get("Hash"))
            if name and int(cid) < 8000:
                out[name] = f"{SRR_IMAGES}character_preview/{cid}.png"
        for lid, info in d.get("hsr_weapons", {}).items():
            name = info.get("Name") or assets.hsr_text(info.get("EquipmentName", {}).get("Hash"))
            if name:
                out[name] = f"{SRR_IMAGES}light_cone_preview/{lid}.png"
    elif game == "zzz":
        for info in d.get("zzz_avatars", {}).values():
            name = assets.zzz_text(info.get("Name"))
            if name and info.get("Image"):
                out[name] = ENKA + info["Image"]
        for info in d.get("zzz_weapons", {}).values():
            name = assets.zzz_text(info.get("ItemName"))
            if name and info.get("ImagePath"):
                out[name] = ENKA + info["ImagePath"]
    return {k: v for k, v in out.items() if "{" not in k}
