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


# The core stats; everything else goes in the second column. Both columns get a real
# heading because phones stack side-by-side fields, and an empty heading shows as a blank row.
BASE_STATS = ("HP", "ATK", "DEF", "SPD", "Elemental Mastery", "Impact")


def _stat_fields(build: CharacterBuild) -> list[tuple[str, str]]:
    """Base and advanced stats side by side (stacked on phones). Stats at 0 are left out."""
    shown = [s for s in build.stats if not _is_zero(s.value)]
    base = [_stat_line(s) for s in shown if s.name in BASE_STATS]
    advanced = [_stat_line(s) for s in shown if s.name not in BASE_STATS]
    columns = [("Base Stats", base), ("Advanced Stats", advanced)]
    return [(name, "\n".join(lines)[:FIELD_LIMIT]) for name, lines in columns if lines] or [("Stats", "No stats.")]


def set_icons(build: CharacterBuild) -> dict[str, str]:
    """Image URL for each equipped set: the first piece of it, in slot order."""
    icons: dict[str, str] = {}
    for piece in build.gear:
        if piece.icon:
            icons.setdefault(piece.set_name, piece.icon)
    return icons


def _set_line(bonus: str, emojis: dict[str, str]) -> str:
    # Bonuses read "4pc <set name>".
    return f"{emojis.get(bonus.split(' ', 1)[-1], DOT)} {bonus}"


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


def _gear_field(piece: Gear, max_level: int) -> tuple[str, str]:
    level = "" if piece.level >= max_level else f" +{piece.level}"
    lines = [f"**{piece.main.name} {piece.main.value}**"] + [_sub(s) for s in piece.subs]
    return f"{piece.slot}{level}", "\n".join(lines)[:FIELD_LIMIT]


def build_embed(
    profile: PlayerProfile,
    build: CharacterBuild,
    show_effect: bool = False,
    set_emojis: dict[str, str] | None = None,
) -> discord.Embed:
    """The build card. The weapon effect only shows when show_effect is set (the "Show ... effect" button).

    set_emojis maps a set name to a Discord emoji of its image, shown in front of the set bonus.
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

    weapon_field = None
    if build.weapon:
        w = build.weapon
        lines = [f"**{w.name}** · {labels['refine']}{w.refinement} · Lv. {w.level}"]
        if w.stats:
            lines.append(" · ".join(f"{s.name} **{s.value}**" for s in w.stats))
        weapon_field = len(embed.fields)
        limit = EFFECT_LIMIT if show_effect else 0
        embed.add_field(name=labels["weapon"], value=_weapon_value(lines, w, limit), inline=False)

    # One column per piece; Discord puts three side by side (stacked on phones).
    for piece in build.gear:
        name, value = _gear_field(piece, labels["max_level"])
        embed.add_field(name=name, value=value, inline=True)

    emojis = set_emojis or {}
    sets = "\n".join(_set_line(b, emojis) for b in build.set_bonuses) or "No set bonus."
    embed.add_field(name=labels["gear"], value=sets if build.gear else "Nothing equipped.", inline=False)

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
