"""/genshin-patch, /hsr-patch, /zzz-patch: the game's current version, how long it has left, and the banners running now.

Everything comes from HoYoLAB's calendars, read with the bot's own HoYoLAB login (HOYOLAB_COOKIES). HoYoLAB doesn't
say when a version ends, so the end is taken as the last end time of the current version's banners, or of its main
event (the one that runs the whole version, 30-42 days) when that is later, e.g. while only the first half's banners
are listed.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
from collections import Counter

import discord
from genshin.models import HSREventTimeType, ZZZGachaEventType

from . import unit_traits

log = logging.getLogger(__name__)

TITLES = {"genshin": "Genshin Impact", "hsr": "Honkai: Star Rail", "zzz": "Zenless Zone Zero"}
COLOURS = {"genshin": 0xE8B25C, "hsr": 0x9680FF, "zzz": 0xFAC428}
# The headings banners are grouped under, in this order
KINDS = {
    "genshin": ("Character event wishes", "Weapon event wish", "Chronicled wish"),
    "hsr": ("Character warps", "Light cone warps"),
    "zzz": ("Exclusive channels", "W-Engine channels", "Exclusive rescreening", "W-Engine reverberation"),
}
MAIN_EVENT = dt.timedelta(days=28)  # an event this long runs the whole version


@dataclasses.dataclass
class Banner:
    kind: str  # one of KINDS[game]
    featured: list[str]  # the 5-star / S-rank items
    others: list[str]  # the 4-star / A-rank ones
    start: dt.datetime
    end: dt.datetime
    icon: str | None = None
    version: str = ""
    items: list[tuple[str, bool, str | None]] = dataclasses.field(default_factory=list)  # (name, 5-star / S, icon)
    traits: dict[str, list[str]] = dataclasses.field(default_factory=dict)  # item name -> element, path symbol urls


@dataclasses.dataclass
class Patch:
    game: str
    version: str
    now: dt.datetime
    end: dt.datetime | None
    banners: list[Banner]  # every banner HoYoLAB lists; the running ones are picked when shown
    server: str | None = None  # the server whose clock the mid-version times follow
    timezone: str | None = None  # the time zone of whoever asked (/timezone), for the times drawn on the card

    @property
    def clock(self) -> str | None:
        """Whose clock the card's times are drawn in: the person's own zone, else their server's."""
        return self.timezone or self.server


def _utc(stamp: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(stamp), tz=dt.timezone.utc)


def _real(when: dt.datetime) -> dt.datetime:
    """genshin.py reads Star Rail's Unix times as UTC and then swaps in China's time zone without converting, which
    puts them 8 hours early; this puts the UTC back."""
    return when.replace(tzinfo=dt.timezone.utc)


def version_start(patch: Patch) -> dt.datetime | None:
    """When the version came out: its first banners' start."""
    starts = [b.start for b in patch.banners if b.version == patch.version]
    return min(starts) if starts else None


def _running(banners: list[Banner], now: dt.datetime) -> list[Banner]:
    return [b for b in banners if b.start <= now < b.end]


def _version(banners: list[Banner], now: dt.datetime) -> str:
    """The version the running banners belong to (Genshin and ZZZ don't say which version is current)."""
    pool = _running(banners, now) or banners
    return Counter(b.version for b in pool).most_common(1)[0][0] if pool else "?"


def _finish(game: str, version: str, now: dt.datetime, banners: list[Banner], event_spans) -> Patch:
    version_ends = [b.end for b in banners if b.version == version]
    main = [end for start, end in event_spans if start <= now < end and end - start >= MAIN_EVENT]
    ends = version_ends + main
    log.info("%s %s: banner ends %s, main event ends %s", game, version,
             sorted({e.isoformat() for e in version_ends}), sorted({e.isoformat() for e in main}))
    return Patch(game, version, now, max(ends) if ends else None, banners)


def hsr_patch(calendar, traits=None) -> Patch:
    """Star Rail: HoYoLAB's event calendar (warps, events, the current version)."""
    version = str(calendar.cur_game_version)
    now = _real(calendar.now)
    banners = []
    for kind, pools in (("Character warps", calendar.character_warps), ("Light cone warps", calendar.light_cone_warps)):
        for warp in pools:
            t = warp.time_info
            if t is None:
                continue
            items = list(warp.characters) if kind == "Character warps" else list(warp.light_cones)
            top = [i for i in items if i.rarity >= 5]
            banners.append(Banner(kind, [i.name for i in top], [i.name for i in items if i.rarity < 5],
                                  _real(t.start), _real(t.end), top[0].icon if top else None, str(warp.version),
                                  [(i.name, i.rarity >= 5, i.icon) for i in items],
                                  {i.name: traits.hsr(i.id, i.path) for i in items} if traits else {}))
    spans = [(_real(e.time_info.start), _real(e.time_info.end)) for e in calendar.events
             if e.time_info and e.time_type != HSREventTimeType.LONG and str(e.version) == version]
    return _finish("hsr", version, now, banners, spans)


def genshin_patch(calendar, now: dt.datetime | None = None, traits=None) -> Patch:
    """Genshin: HoYoLAB's event calendar (wishes and events)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    banners = []
    groups = (("Character event wishes", calendar.character_banners), ("Weapon event wish", calendar.weapon_banners),
              ("Chronicled wish", calendar.chronicled_banners))
    for kind, pools in groups:
        for pool in pools:
            items = list(pool.characters) + list(pool.weapons)
            top = [i for i in items if i.rarity >= 5]
            banners.append(Banner(kind, [i.name for i in top], [i.name for i in items if i.rarity < 5],
                                  _utc(pool.start_timestamp), _utc(pool.end_timestamp), top[0].icon if top else None,
                                  str(pool.version), [(i.name, i.rarity >= 5, i.icon) for i in items],
                                  {i.name: traits.genshin(i.id, getattr(i, "element", None)) for i in items} if traits else {}))
    spans = [(_utc(e.start_timestamp), _utc(e.end_timestamp)) for e in calendar.events if e.end_timestamp]
    return _finish("genshin", _version(banners, now), now, banners, spans)


ZZZ_KINDS = {
    ZZZGachaEventType.CHARACTER: "Exclusive channels", ZZZGachaEventType.EXCLUSIVE_RESCREENING: "Exclusive rescreening",
    ZZZGachaEventType.WEAPON: "W-Engine channels", ZZZGachaEventType.REVERBERATION: "W-Engine reverberation",
}


def zzz_patch(gacha, events, weapon_name, now: dt.datetime | None = None, agent_name=lambda _: None) -> Patch:
    """ZZZ: HoYoLAB's channel calendar and event calendar. W-Engines come without names, so weapon_name(id) looks
    them up in the game data; an agent HoYoLAB sends without a name (seen on a coming one) gets agent_name(id)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    banners = []
    for pool in list(gacha.characters) + list(gacha.weapons):
        kind = ZZZ_KINDS.get(pool.type)
        if kind is None:  # the standard and Bangboo channels
            continue
        if hasattr(pool, "characters"):
            items = [(next((n.strip() for n in (c.name, c.full_name, agent_name(c.id)) if n and n.strip()), "New Agent"),
                      c.rarity, c.icon) for c in pool.characters]
            marks = [unit_traits.zzz_urls(c.element, c.sub_element, c.specialty) for c in pool.characters]
        else:
            items = [(weapon_name(w.id) or w.skill_name or "New W-Engine", w.rarity, w.icon) for w in pool.weapons]
            marks = [unit_traits.zzz_urls(None, None, w.specialty) for w in pool.weapons]
        top = [i for i in items if i[1] == "S"]
        banners.append(Banner(kind, [i[0] for i in top], [i[0] for i in items if i[1] != "S"], pool.start, pool.end,
                              top[0][2] if top else None, str(pool.version), [(i[0], i[1] == "S", i[2]) for i in items],
                              {i[0]: m for i, m in zip(items, marks)}))
    spans = [(e.start, e.end) for e in events]
    return _finish("zzz", _version(banners, now), now, banners, spans)


CHARACTER_KINDS = {"Character warps", "Character event wishes", "Chronicled wish", "Exclusive channels",
                   "Exclusive rescreening"}


def unknown_characters(info: Patch, known: list[str], now: dt.datetime | None = None) -> list[str]:
    """Featured characters on the running banners that aren't in the game data (one name containing the other counts
    as known, for the odd spelling difference between HoYoLAB and the game data)."""
    def norm(name: str) -> str:
        return "".join(ch for ch in name.lower() if ch.isalnum())

    now = now or dt.datetime.now(dt.timezone.utc)
    have = [norm(k) for k in known]
    names = {n for b in info.banners if b.kind in CHARACTER_KINDS and b.start <= now < b.end for n in b.featured}
    return sorted(n for n in names if not any(norm(n) in k or (k and k in norm(n)) for k in have))


# Each game server runs on its own fixed clock; mid-version banner switches happen at the same local time on each
SERVER_UTC = {"America": -5, "Europe": 1, "Asia": 8, "TW/HK/MO": 8, "China": 8}


def for_server(patch: Patch, read_on: str | None, server: str | None) -> Patch:
    """The patch with its mid-version times moved from the server it was read on to the player's. The version's
    start and end (the updates) happen at the same moment everywhere, so those stay."""
    if not (read_on and server) or SERVER_UTC.get(read_on) is None or SERVER_UTC.get(server) is None:
        return patch  # unknown: left as read (the footer then names the server it was read on)
    shift = dt.timedelta(hours=SERVER_UTC[read_on] - SERVER_UTC[server])
    if not shift:
        return dataclasses.replace(patch, server=server)
    update = version_start(patch)
    near = dt.timedelta(hours=1)

    def move(when: dt.datetime) -> dt.datetime:
        fixed = [m for m in (update, patch.end) if m is not None]
        return when if any(abs(when - m) <= near for m in fixed) else when + shift

    banners = [dataclasses.replace(b, start=move(b.start), end=move(b.end)) for b in patch.banners]
    return dataclasses.replace(patch, banners=banners, server=server)


def time_left(delta: dt.timedelta) -> str:
    """'12 days 4 hours', or under a day '5 hours 12 minutes'."""
    total = max(0, int(delta.total_seconds()))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60

    def unit(n: int, word: str) -> str:
        return f"{n} {word}{'' if n == 1 else 's'}"

    if days:
        return f"{unit(days, 'day')} {unit(hours, 'hour')}"
    return f"{unit(hours, 'hour')} {unit(minutes, 'minute')}"


def _line(b: Banner) -> str:
    text = " & ".join(f"**{n}**" for n in b.featured) or "**?**"
    if b.others:
        text += f"\nwith {', '.join(b.others)}"
    return text


def patch_embed(patch: Patch) -> discord.Embed:
    embed = discord.Embed(title=f"{TITLES[patch.game]} · Version {patch.version}", colour=COLOURS[patch.game])
    if patch.end:
        embed.description = f"Ends in **{time_left(patch.end - patch.now)}** · <t:{int(patch.end.timestamp())}:f>"
    running = _running(patch.banners, patch.now)
    for kind in KINDS[patch.game]:
        group = [b for b in running if b.kind == kind]
        if not group:
            continue
        ends = {int(b.end.timestamp()) for b in group}
        if len(ends) == 1:
            end = ends.pop()
            lines = [_line(b) for b in group] + [f"Until <t:{end}:f> (<t:{end}:R>)"]
        else:
            lines = [f"{_line(b)}\nuntil <t:{int(b.end.timestamp())}:R>" for b in group]
        embed.add_field(name=kind, value="\n".join(lines)[:1024], inline=False)
    if not running:
        embed.add_field(name="Banners", value="No banners are running right now.", inline=False)
    icon = next((b.icon for b in running if b.icon), None)
    if icon:
        embed.set_thumbnail(url=icon)
    embed.set_footer(text=f"From HoYoLAB's calendar · Times for {patch.server} servers" if patch.server
                     else "From HoYoLAB's calendar")
    return embed
