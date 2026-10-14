"""/hsr-patch: the current Star Rail version, how long it has left, and the warps running now.

Everything comes from HoYoLAB's event calendar, read with the bot's own HoYoLAB login (HOYOLAB_COOKIES). HoYoLAB
doesn't say when a version ends, so the end is taken as the last end time of the current version's warps.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging

import discord

log = logging.getLogger(__name__)

HSR_COLOUR = 0x8F7CF0


@dataclasses.dataclass
class Banner:
    kind: str  # "character" or "light cone"
    featured: list[str]  # the 5-star(s)
    others: list[str]  # the 4-stars
    start: dt.datetime
    end: dt.datetime
    icon: str | None = None


@dataclasses.dataclass
class Patch:
    version: str
    now: dt.datetime
    end: dt.datetime | None
    banners: list[Banner]


def _real(when: dt.datetime) -> dt.datetime:
    """genshin.py reads HoYoLAB's Unix times as UTC and then swaps in China's time zone without converting, which
    puts them 8 hours early; this puts the UTC back."""
    return when.replace(tzinfo=dt.timezone.utc)


def _ends(items, version: str) -> list[dt.datetime]:
    return [_real(i.time_info.end) for i in items
            if getattr(i, "time_info", None) and str(getattr(i, "version", "")) == version]


def hsr_patch(calendar) -> Patch:
    """Turns HoYoLAB's HSR event calendar into the version, its end and the warps running now."""
    version = str(calendar.cur_game_version)
    now = _real(calendar.now)
    warps = list(calendar.character_warps) + list(calendar.light_cone_warps)
    ends = _ends(warps, version)  # a version ends when its last warp does (its second half's, if HoYoLAB lists it)
    log.info("HSR %s: warp ends %s", version, sorted({e.isoformat() for e in ends}))
    banners = []
    for kind, pools in (("character", calendar.character_warps), ("light cone", calendar.light_cone_warps)):
        for warp in pools:
            t = warp.time_info
            if t is None or not (_real(t.start) <= now < _real(t.end)):
                continue
            items = list(warp.characters) if kind == "character" else list(warp.light_cones)
            top = [i for i in items if i.rarity >= 5]
            banners.append(Banner(kind, [i.name for i in top], [i.name for i in items if i.rarity < 5], _real(t.start), _real(t.end),
                                  top[0].icon if top else None))
    return Patch(version, now, max(ends) if ends else None, banners)


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
    now = patch.now
    embed = discord.Embed(title=f"Honkai: Star Rail · Version {patch.version}", colour=HSR_COLOUR)
    if patch.end:
        embed.description = f"Ends in **{time_left(patch.end - now)}** · <t:{int(patch.end.timestamp())}:f>"
    for kind, title in (("character", "Character warps"), ("light cone", "Light cone warps")):
        group = [b for b in patch.banners if b.kind == kind]
        if not group:
            continue
        lines = [_line(b) for b in group]
        ends = {int(b.end.timestamp()) for b in group}
        if len(ends) == 1:
            lines.append(f"Until <t:{ends.pop()}:f> (<t:{int(group[0].end.timestamp())}:R>)")
        else:
            lines = [f"{_line(b)} · until <t:{int(b.end.timestamp())}:R>" for b in group]
        embed.add_field(name=title, value="\n".join(lines)[:1024], inline=False)
    if not patch.banners:
        embed.add_field(name="Warps", value="No warps are running right now.", inline=False)
    icon = next((b.icon for b in patch.banners if b.kind == "character" and b.icon), None)
    if icon:
        embed.set_thumbnail(url=icon)
    embed.set_footer(text="From HoYoLAB's event calendar")
    return embed
