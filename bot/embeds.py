"""Discord embeds for a character build."""

from __future__ import annotations

import re

import discord

from .models import CharacterBuild, Gear, PlayerProfile, Stat, Weapon

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
    "Ether": 0xE84B9C, "Auric Ink": 0xD4AF37,
}
DISPLAY_NAMES = {"Energy Regen Rate": "Energy Regen"}
ZZZ_RARITY = {4: "S", 3: "A", 2: "B"}
EFFECT_LIMIT = 900  # characters of weapon effect text per embed
FIELD_LIMIT = 1024
EMBED_LIMIT = 6000
DOT = "•"


def _rarity(game: str, rarity: int) -> str:
    if game == "zzz":
        return f"{ZZZ_RARITY.get(rarity, '?')}-Rank"
    return "★" * rarity


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines())


def _is_zero(value: str) -> bool:
    number = re.sub(r"[^0-9.]", "", value)
    return bool(number) and float(number) == 0


def _stat_line(stat: Stat) -> str:
    return f"{DOT} {DISPLAY_NAMES.get(stat.name, stat.name)} **{stat.value}**"


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


def _weapon_value(lines: list[str], weapon: Weapon, effect_limit: int) -> str:
    value = "\n".join(lines)
    if weapon.effect and effect_limit > 20:
        title = f"> **{weapon.effect_name}**\n" if weapon.effect_name else ""
        budget = effect_limit
        while True:
            # The "> " quote prefixes count too, so trim until the field fits.
            effect = _quote(_shorten(weapon.effect, budget))
            extra = len(value) + 1 + len(title) + len(effect) - FIELD_LIMIT
            if extra <= 0 or budget <= 20:
                break
            budget -= extra
        value += f"\n{title}{effect}"
    return value[:FIELD_LIMIT]


def _sub(stat: Stat) -> str:
    """A substat, led by how many times it rolled (counting its first roll)."""
    rolls = f"`{stat.rolls}×` " if stat.rolls else ""
    return f"{rolls}{stat.name} **{stat.value}**"


def _gear_field(piece: Gear, max_level: int, emoji: str | None = None, keep_slot: bool = False) -> tuple[str, str]:
    """The piece's picture stands in for its slot name; keep_slot keeps both (drive discs all look alike)."""
    level = "" if piece.level >= max_level else f" +{piece.level}"
    if emoji:
        title = f"{emoji} {piece.slot}" if keep_slot else emoji
    else:
        title = piece.slot
    lines = [f"**{piece.main.name} {piece.main.value}**"] + [_sub(s) for s in piece.subs]
    return f"{title}{level}", "\n".join(lines)[:FIELD_LIMIT]


def build_embed(
    profile: PlayerProfile,
    build: CharacterBuild,
    show_effect: bool = False,
    piece_emojis: dict[str, str] | None = None,
) -> discord.Embed:
    """The build card. The weapon effect only shows when show_effect is set (the "Show ... effect" button).

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
    for piece in build.gear:
        name, value = _gear_field(
            piece, labels["max_level"], (piece_emojis or {}).get(piece.piece_icon or ""), keep_slot=build.game == "zzz"
        )
        embed.add_field(name=name, value=value, inline=True)

    if not build.gear:
        embed.add_field(name=labels["gear"], value="Nothing equipped.", inline=False)

    # The weapon comes last, so its effect (when shown) doesn't push the gear down.
    weapon_field = None
    if build.weapon:
        w = build.weapon
        lines = [f"**{w.name}** · {labels['refine']}{w.refinement} · Lv. {w.level}"]
        if w.stats:
            lines.append(" · ".join(f"{s.name} **{s.value}**" for s in w.stats))
        weapon_field = len(embed.fields)
        limit = EFFECT_LIMIT if show_effect else 0
        embed.add_field(name=labels["weapon"], value=_weapon_value(lines, w, limit), inline=False)

    footer = "Data from Enka.Network"
    if build.notes:
        footer = " ".join(build.notes) + " · " + footer
    embed.set_footer(text=footer)

    # Discord rejects embeds over 6,000 characters; the effect text is the
    # only part long enough to matter, so it gives way first.
    if show_effect and weapon_field is not None and build.weapon.effect:
        budget = min(EFFECT_LIMIT, len(build.weapon.effect))
        while len(embed) > EMBED_LIMIT and budget > 20:
            budget -= len(embed) - EMBED_LIMIT
            value = _weapon_value(lines, build.weapon, budget)
            embed.set_field_at(weapon_field, name=labels["weapon"], value=value, inline=False)
    return embed
