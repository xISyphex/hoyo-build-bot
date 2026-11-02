"""A player's HoYoLAB profile for /genshin-stats, /hsr-stats and /zzz-stats: days active, characters owned,
achievements and the rest of the Battle Chronicle's front page, plus every character they own.

Each game's page is read with genshin.py and boiled down to a Profile: a few big numbers, the smaller ones in groups,
Genshin's exploration per region, and the characters as small tiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class Unit:
    name: str
    icon: str | None
    rarity: int  # 4 / 5 (ZZZ: A = 4, S = 5)
    level: int
    copies: int  # constellation / eidolon / mindscape


@dataclass
class Region:
    name: str
    explored: float  # percent
    icon: str | None = None


@dataclass
class Profile:
    game: str
    uid: str
    nickname: str | None = None
    level: int | None = None
    level_label: str = "Level"  # Adventure Rank, Trailblaze Level, Inter-Knot Level
    title: str | None = None  # ZZZ's Inter-Knot reputation, shown under the name
    headline: list[tuple[str, str]] = field(default_factory=list)  # the big numbers: ("Days active", "812")
    groups: list[tuple[str, list[tuple[str, str]]]] = field(default_factory=list)  # ("Chests", [("Luxurious", "190"), ...])
    regions: list[Region] = field(default_factory=list)  # Genshin's exploration
    units: list[Unit] = field(default_factory=list)  # every character owned, best first


def _num(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def _sorted(units: list[Unit]) -> list[Unit]:
    return sorted(units, key=lambda u: (-u.rarity, -u.level, -u.copies, u.name))


def genshin_profile(uid: str, data) -> Profile:
    s = data.stats
    info = data.info
    p = Profile("genshin", uid, info.nickname or None, info.level or None, "Adventure Rank")
    p.headline = [("Days active", _num(s.days_active)), ("Characters", _num(s.characters)),
                  ("Achievements", _num(s.achievements)), ("Spiral Abyss", s.spiral_abyss or "-")]
    theater = getattr(s, "theater", None)
    stygian = getattr(s, "stygian", None)
    end = [("Max friendship", _num(s.max_friendship_characters))]
    if theater and theater.unlocked:
        end.append(("Theater", f"Act {theater.max_act}" if theater.has_data else "-"))
    if stygian and stygian.unlocked:
        end.append(("Stygian", stygian.name or "-"))
    p.groups = [
        ("World", [("Waypoints", _num(s.unlocked_waypoints)), ("Domains", _num(s.unlocked_domains))] + end),
        ("Oculi", [("Anemo", _num(s.anemoculi)), ("Geo", _num(s.geoculi)), ("Electro", _num(s.electroculi)),
                   ("Dendro", _num(s.dendroculi)), ("Hydro", _num(s.hydroculi)), ("Pyro", _num(s.pyroculi))]
         + ([("Lunar", _num(s.lunoculi))] if getattr(s, "lunoculi", 0) else [])),
        ("Chests", [("Common", _num(s.common_chests)), ("Exquisite", _num(s.exquisite_chests)),
                    ("Precious", _num(s.precious_chests)), ("Luxurious", _num(s.luxurious_chests)),
                    ("Remarkable", _num(s.remarkable_chests))]),
    ]
    if data.teapot:
        p.groups.append(("Serenitea Pot", [("Trust rank", _num(data.teapot.level)), ("Comfort", _num(data.teapot.comfort)),
                                          ("Furnishings", _num(data.teapot.items)), ("Visitors", _num(data.teapot.visitors))]))
    # top-level regions only (Chasm's underground and the like are a region's own sub-area)
    p.regions = [Region(e.name, e.explored, e.icon or None) for e in sorted(data.explorations, key=lambda e: e.id)
                 if not getattr(e, "parent_id", 0)]
    p.units = _sorted([Unit(c.name, c.icon, c.rarity if c.rarity < 6 else 5, c.level, c.constellation)
                       for c in data.characters])
    return p


def hsr_profile(uid: str, data, info=None) -> Profile:
    s = data.stats
    p = Profile("hsr", uid, getattr(info, "nickname", None) or None, getattr(info, "level", None) or None, "Trailblaze Level")
    p.headline = [("Days active", _num(s.active_days)), ("Characters", _num(s.avatar_num)),
                  ("Achievements", _num(s.achievement_num)), ("Treasures", _num(s.chest_num)),
                  ("Memory of Chaos", s.abyss_process or "-"), ("Stickers", _num(s.dreamscape_pass_sticker))]
    p.units = _sorted([Unit(c.name, c.icon, c.rarity, c.level, c.rank) for c in data.characters])
    return p


def zzz_profile(uid: str, data, nickname: str | None = None, level: int | None = None) -> Profile:
    s = data.stats
    p = Profile("zzz", uid, nickname, level, "Inter-Knot Level", title=s.inter_knot_reputation or None)
    p.headline = [("Days active", _num(s.active_days)), ("Agents", _num(s.character_num)),
                  ("Achievements", _num(s.achievement_count)), ("Bangboo", _num(s.bangboo_obtained))]
    more = [("Shiyu frontiers", _num(s.shiyu_defense_frontiers))]
    if s.hia_coin:
        more.append((s.hia_coin.name or "HIA coins", _num(s.hia_coin.num)))
    p.groups = [("Records", more)]
    notes = [(n.name, f"{n.num}/{n.total}") for n in data.cat_notes if not n.is_lock]
    if notes:
        p.groups.append(("Notes", notes))
    p.units = _sorted([Unit(a.name, a.square_icon, 5 if a.rarity == "S" else 4, a.level, a.rank) for a in data.agents])
    return p


async def read_profile(client, game: str, uid: int) -> Profile:
    """The player's HoYoLAB profile page."""
    if game == "genshin":
        return genshin_profile(str(uid), await client.get_genshin_user(uid))
    if game == "hsr":
        import genshin

        index = await client._request_starrail_record("index", uid)
        try:  # the name and level come with the player's own login only
            info = genshin.models.StarRailUserInfo(**await client._request_starrail_record("role/basicInfo", uid))
        except Exception as exc:
            log.info("No Star Rail basic info for %s: %s", uid, exc)
            info = None
        return hsr_profile(str(uid), genshin.models.PartialStarRailUserStats(**index), info)
    data = await client.get_zzz_user(uid)
    card = None
    try:  # the name and level are on the HoYoLAB record card, readable with the player's own login only
        cards = await client.get_record_cards()
        card = next((c for c in cards if str(c.uid) == str(uid)), None)
    except Exception as exc:
        log.info("No ZZZ record card for %s: %s", uid, exc)
    return zzz_profile(str(uid), data, getattr(card, "nickname", None), getattr(card, "level", None))

