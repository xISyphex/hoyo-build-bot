"""Discord embeds for a character build."""

from __future__ import annotations

import re

import discord

from .models import CharacterBuild, Gear, PlayerProfile, Stat

GAME_LABELS = {
    "genshin": {
        "title": "Genshin Impact", "cons": "C", "refine": "R", "weapon": "Weapon",
        "gear": "Artifacts", "max_level": 20, "color": 0x4E7CFF,
    },
    "hsr": {
        "title": "Honkai: Star Rail", "cons": "E", "refine": "S", "weapon": "Light Cone",
        "gear": "Relics", "max_level": 15, "color": 0xB6A0FF,
    },
    "zzz": {
        "title": "Zenless Zone Zero", "cons": "M", "refine": "P", "weapon": "W-Engine",
        "gear": "Drive Discs", "max_level": 15, "color": 0xF2C94C,
    },
}
ELEMENT_COLORS = {
    "Pyro": 0xEF7938, "Fire": 0xEF7938,
    "Hydro": 0x4CC2F1, "Cryo": 0x9FD6E3, "Ice": 0x9FD6E3, "Frost": 0x9FD6E3,
    "Electro": 0xAF8EC1, "Electric": 0x2E6CF6, "Lightning": 0xC264E6,
    "Anemo": 0x74C2A8, "Wind": 0x61CF93,
    "Geo": 0xFAB632, "Dendro": 0xA5C83B,
    "Physical": 0xB8B8B8, "Quantum": 0x6F6BD8, "Imaginary": 0xF3D84C,
    "Ether": 0xE84B9C, "Auric Ink": 0xD4AF37, "Lumen": 0xF58BC4,
}
# Long stat names wrap in the narrow columns, so they get their common short forms.
SHORT_NAMES = {
    "Energy Regen Rate": "Energy Reg.", "Energy Regen": "Energy Reg.", "Energy Recharge": "Energy Reg.",
    "ER": "Energy Reg.", "ER%": "Energy Reg.%",  # the parsers' own short gear names
    "Break Effect": "Break Eff.", "Effect Hit Rate": "EHR", "Elemental Mastery": "EM",
    "Anomaly Proficiency": "AP", "Anomaly Mastery": "AM",
    "Outgoing Healing": "Healing", "Healing Bonus": "Healing",
}
ZZZ_RARITY = {4: "S", 3: "A", 2: "B"}
FIELD_LIMIT = 1024
DOT = "•"


def _rarity(game: str, rarity: int) -> str:
    if game == "zzz":
        return f"{ZZZ_RARITY.get(rarity, '?')}-Rank"
    return "★" * rarity


def _is_zero(value: str) -> bool:
    number = re.sub(r"[^0-9.]", "", value)
    return bool(number) and float(number) == 0


def _name(stat: Stat) -> str:
    """Short stat name: "Quantum DMG Boost" -> "Quantum DMG", "Energy Regen Rate" -> "Energy Reg."."""
    name = SHORT_NAMES.get(stat.name, stat.name)
    return re.sub(r" DMG (Boost|Bonus)$", " DMG", name)


def _stat_line(stat: Stat) -> str:
    return f"{DOT} {_name(stat)} **{stat.value}**"


def _stat_fields(build: CharacterBuild) -> list[tuple[str, str]]:
    """Three side-by-side columns of near-equal length (the left ones get the extra lines).

    Three, because Discord puts three inline fields per row: with fewer, the first gear
    piece would slide up next to the stats and every gear row after it would be off.
    All are titled "Stats": phones stack the columns, and an empty title shows as a blank row.
    Stats at 0 (like 0% Effect RES) are left out.
    """
    lines = [_stat_line(s) for s in build.stats if not _is_zero(s.value)]
    size, extra = divmod(len(lines), 3)
    columns, start = [], 0
    for i in range(3):
        end = start + size + (i < extra)
        columns.append(lines[start:end])
        start = end
    return [("Stats", "\n".join(col)[:FIELD_LIMIT]) for col in columns if col] or [("Stats", "No stats.")]


def _sub(stat: Stat) -> str:
    """A substat, led by how many times it was upgraded (its first roll is the base, not an upgrade)."""
    rolls = f"`+{stat.rolls - 1}` " if stat.rolls > 1 else ""
    return f"{rolls}{_name(stat)} **{stat.value}**"


def _gear_field(piece: Gear, max_level: int, emoji: str | None = None, keep_slot: bool = False) -> tuple[str, str]:
    """The piece's picture stands in for its slot name; keep_slot keeps both (drive discs all look alike)."""
    level = "" if piece.level >= max_level else f" +{piece.level}"
    if emoji:
        title = f"{emoji} {piece.slot}" if keep_slot else emoji
    else:
        title = piece.slot
    lines = [f"**{_name(piece.main)} {piece.main.value}**"] + [_sub(s) for s in piece.subs]
    return f"{title}{level}", "\n".join(lines)[:FIELD_LIMIT]


PLANAR_SLOTS = {"Planar Sphere", "Link Rope"}


def _gear_order(build: CharacterBuild) -> list[Gear]:
    """Star Rail and ZZZ: the 4-piece set fills the left two columns, the 2-piece set the right one.

    Discord shows three pieces per row, so the order is 4pc, 4pc, 2pc, 4pc, 4pc, 2pc.
    Builds without a clean 4 + 2 split keep their slot order.
    """
    gear = build.gear
    if build.game not in ("hsr", "zzz") or len(gear) != 6:
        return gear
    if build.game == "hsr":
        four = [p for p in gear if p.slot not in PLANAR_SLOTS]
    else:
        names = [p.set_name for p in gear]
        main = next((n for n in names if names.count(n) == 4), None)
        four = [p for p in gear if p.set_name == main]
    two = [p for p in gear if p not in four]
    if len(four) != 4:
        return gear
    return [four[0], four[1], two[0], four[2], four[3], two[1]]


def build_embed(
    profile: PlayerProfile,
    build: CharacterBuild,
    piece_emojis: dict[str, str] | None = None,
) -> discord.Embed:
    """The all-text build reply, used when the card image can't be drawn.

    piece_emojis maps a piece's image URL to its emoji, shown next to the piece's slot name.
    """
    labels = GAME_LABELS[build.game]
    embed = discord.Embed(
        title=build.name,
        description=(
            f"{_rarity(build.game, build.rarity)} · {build.element} · "
            f"Lv. {build.level} · {labels['cons']}{build.constellation}"
        ),
        color=ELEMENT_COLORS.get(build.element, labels["color"]),
        url=profile.profile_url,
    )
    embed.set_author(name=f"{profile.nickname} · UID {profile.uid} · {labels['title']}")
    if build.icon_url:
        embed.set_thumbnail(url=build.icon_url)

    for name, value in _stat_fields(build):
        embed.add_field(name=name, value=value, inline=True)

    # One column per piece; Discord puts three side by side (stacked on phones).
    for piece in _gear_order(build):
        name, value = _gear_field(
            piece, labels["max_level"], (piece_emojis or {}).get(piece.piece_icon or ""), keep_slot=build.game == "zzz"
        )
        embed.add_field(name=name, value=value, inline=True)

    if not build.gear:
        embed.add_field(name=labels["gear"], value="Nothing equipped.", inline=False)

    # The weapon comes last.
    if build.weapon:
        w = build.weapon
        lines = [f"**{w.name}** · {labels['refine']}{w.refinement} · Lv. {w.level}"]
        if w.stats:
            lines.append(" · ".join(f"{_name(s)} **{s.value}**" for s in w.stats))
        embed.add_field(name=labels["weapon"], value="\n".join(lines)[:FIELD_LIMIT], inline=False)

    footer = "Data from Enka.Network"
    if build.notes:
        footer = " ".join(build.notes) + " · " + footer
    embed.set_footer(text=footer)
    return embed

