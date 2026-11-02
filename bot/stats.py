"""A player's profile for /genshin-stats, /hsr-stats and /zzz-stats: their profile picture, name card, signature and
levels, days active, achievements and the rest of the Battle Chronicle's front page.

Each game's page is read with genshin.py and boiled down to a Profile: a few big numbers, the smaller ones in groups
and Genshin's exploration per region. add_enka then fills in what only the in-game profile has (signature, world
level, the profile picture and name card the player picked, ZZZ's title and medals) from Enka.Network."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

ENKA = "https://enka.network"


@dataclass
class Region:
    name: str
    explored: float  # percent
    icon: str | None = None


@dataclass
class Medal:
    name: str
    icon: str | None
    value: str


@dataclass
class Profile:
    game: str
    uid: str
    nickname: str | None = None
    level: int | None = None
    level_label: str = "Level"  # Adventure Rank, Trailblaze Level, Inter-Knot Level
    world_level: tuple[str, str] | None = None  # ("World Level", "8"), ("Equilibrium", "6")
    title: str | None = None  # ZZZ's title, shown on a badge under the name
    title_colors: tuple[str, str] | None = None  # the title badge's two colours, as hex
    signature: str | None = None
    avatar: str | None = None  # the profile picture
    banner: str | None = None  # the name card / calling card / phone wallpaper behind the header
    headline: list[tuple[str, str]] = field(default_factory=list)  # the big numbers: ("Days active", "812")
    groups: list[tuple[str, list[tuple[str, str]]]] = field(default_factory=list)  # ("Chests", [("Luxurious", "190"), ...])
    regions: list[Region] = field(default_factory=list)  # Genshin's exploration
    namecards: list[str] = field(default_factory=list)  # Genshin's showcased name cards
    medals: list[Medal] = field(default_factory=list)  # ZZZ's showcased medals


def _num(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def _ui(path: str | None, prefix: str = "") -> str | None:
    """Enka's address for a picture path from its store files."""
    if not path:
        return None
    if path.startswith("http"):
        return path
    path = path if path.startswith("/") else "/ui/" + prefix + path
    return ENKA + path


def _hex(color: str | None) -> str | None:
    color = (color or "").strip().lstrip("#")
    return color[:6] if len(color) >= 6 else None


def genshin_profile(uid: str, data) -> Profile:
    s = data.stats
    info = data.info
    p = Profile("genshin", uid, info.nickname or None, info.level or None, "Adventure Rank",
                avatar=getattr(info, "in_game_avatar", None) or getattr(info, "icon", None) or None)
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
    return p


def hsr_profile(uid: str, data, info=None) -> Profile:
    s = data.stats
    p = Profile("hsr", uid, getattr(info, "nickname", None) or None, getattr(info, "level", None) or None, "Trailblaze Level",
                avatar=getattr(data, "in_game_avatar", None) or None, banner=getattr(data, "phone_background", None) or None)
    p.headline = [("Days active", _num(s.active_days)), ("Characters", _num(s.avatar_num)),
                  ("Achievements", _num(s.achievement_num)), ("Treasures", _num(s.chest_num)),
                  ("Memory of Chaos", s.abyss_process or "-"), ("Stickers", _num(s.dreamscape_pass_sticker))]
    return p


def zzz_profile(uid: str, data, nickname: str | None = None, level: int | None = None) -> Profile:
    s = data.stats
    p = Profile("zzz", uid, nickname, level, "Inter-Knot Level", avatar=getattr(data, "in_game_avatar", None) or None)
    p.headline = [("Days active", _num(s.active_days)), ("Agents", _num(s.character_num)),
                  ("Achievements", _num(s.achievement_count)), ("Bangboo", _num(s.bangboo_obtained))]
    more = [("Reputation", s.inter_knot_reputation or "-"), ("Shiyu frontiers", _num(s.shiyu_defense_frontiers))]
    if s.hia_coin:
        more.append((s.hia_coin.name or "HIA coins", _num(s.hia_coin.num)))
    p.groups = [("Records", more)]
    notes = [(n.name, f"{n.num}/{n.total}") for n in data.cat_notes if not n.is_lock]
    if notes:
        p.groups.append(("Notes", notes))
    game = getattr(data, "in_game_data", None)
    if game:
        p.banner = game.card_url or None
        p.title = game.personal_title or None
        a, b = _hex(game.title_main_color), _hex(game.title_bottom_color)
        p.title_colors = (a, b or a) if a else None
        p.medals = [Medal(m.name, m.icon or None, _num(m.number)) for m in game.medals if m.is_show][:3]
    return p


def add_enka(p: Profile, assets, player: dict | None, nickname: str | None = None, level: int | None = None) -> Profile:
    """Fill what HoYoLAB left out from the in-game profile Enka.Network shows (its raw player block)."""
    p.nickname = p.nickname or nickname
    p.level = p.level or level
    player = player or {}
    data = getattr(assets, "data", {}) or {}
    try:
        if p.game == "genshin":
            _gi_enka(p, data, player)
        elif p.game == "hsr":
            _hsr_enka(p, data, player)
        else:
            _zzz_enka(p, assets, data, player)
    except Exception:  # a picture or a line less is better than no profile
        log.exception("Could not read Enka's %s profile for %s", p.game, p.uid)
    return p


def _gi_enka(p: Profile, data: dict, player: dict) -> None:
    p.signature = p.signature or player.get("signature") or None
    if player.get("worldLevel"):
        p.world_level = ("World Level", str(player["worldLevel"]))
    cards = data.get("gi_namecards", {})
    if (card := cards.get(str(player.get("nameCardId")))) and card.get("Icon"):
        p.banner = p.banner or _ui(card["Icon"])
    p.namecards = [u for i in player.get("showNameCardIdList", []) if (u := _ui(cards.get(str(i), {}).get("Icon")))]
    pic = player.get("profilePicture") or {}
    avatar = None
    if pic.get("id"):
        avatar = _ui(data.get("gi_pfps", {}).get(str(pic["id"]), {}).get("IconPath"))
    elif pic.get("avatarId"):
        avatar = _ui(data.get("gi_avatars", {}).get(str(pic["avatarId"]), {}).get("SideIconName"))
    p.avatar = avatar or p.avatar  # the picture they show in game, HoYoLAB's as a fallback


def _hsr_enka(p: Profile, data: dict, player: dict) -> None:
    p.signature = p.signature or player.get("signature") or None
    if player.get("worldLevel") is not None:
        p.world_level = ("Equilibrium Level", str(player["worldLevel"]))
    head = data.get("hsr_head_icons", {}).get(str(player.get("headIcon")), {}).get("Icon")
    p.avatar = _ui(head, "hsr/") or p.avatar
    record = player.get("recordInfo") or {}
    collection = [(label, _num(record[key])) for label, key in (("Light cones", "equipmentCount"), ("Relics", "relicCount"),
                                                                ("Books", "bookCount"), ("Music", "musicCount")) if key in record]
    blazer = []
    if "friendCount" in player:
        blazer.append(("Friends", _num(player["friendCount"])))
    if record.get("maxRogueChallengeScore"):
        blazer.append(("Simulated Universe", f"World {record['maxRogueChallengeScore']}"))
    p.groups = [g for g in (("Trailblazer", blazer), ("Collection", collection)) if g[1]]


def _zzz_enka(p: Profile, assets, data: dict, player: dict) -> None:
    social = player.get("SocialDetail") or {}
    detail = social.get("ProfileDetail") or {}
    p.signature = p.signature or social.get("Desc") or None
    p.nickname = p.nickname or detail.get("Nickname") or None
    p.level = p.level or detail.get("Level") or None
    p.avatar = _ui(data.get("zzz_pfps", {}).get(str(detail.get("ProfileId")), {}).get("Icon")) or p.avatar
    p.banner = p.banner or _ui(data.get("zzz_namecards", {}).get(str(detail.get("CallingCardId")), {}).get("Icon"))
    text = getattr(assets, "zzz_text", lambda key: None)
    if not p.title:
        title_id = (detail.get("TitleInfo") or {}).get("Title") or detail.get("Title")
        title = data.get("zzz_titles", {}).get("Titles", {}).get(str(title_id))
        if title and (name := text(title.get("TitleText"))):
            p.title = name
            a, b = _hex(title.get("ColorA")), _hex(title.get("ColorB"))
            p.title_colors = (a, b or a) if a else None
    if not p.medals:
        medals = data.get("zzz_medals", {})
        for m in social.get("MedalList", [])[:3]:
            info = medals.get(str(m.get("MedalIcon")), {})
            name = text(info.get("Name")) or "Medal"
            p.medals.append(Medal(name, _ui(info.get("Icon")), _num(m.get("Value", m.get("MedalScore", 0)))))


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
