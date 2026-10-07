"""Discord embeds for a character build."""

from __future__ import annotations

import re

import discord

from .models import CharacterBuild, Gear, PlayerProfile, Stat, Weapon

GAME_LABELS = {
    "genshin": {
        "title": "Genshin Impact", "cons": "C", "refine": "R", "weapon": "Weapon",
        "talents": "Talents", "gear": "Artifacts", "max_level": 20, "color": 0x4E7CFF,
    },
    "hsr": {
        "title": "Honkai: Star Rail", "cons": "E", "refine": "S", "weapon": "Light Cone",
        "talents": "Traces", "gear": "Relics", "max_level": 15, "color": 0xB6A0FF,
    },
    "zzz": {
        "title": "Zenless Zone Zero", "cons": "M", "refine": "P", "weapon": "W-Engine",
        "talents": "Skills", "gear": "Drive Discs", "max_level": 15, "color": 0xF2C94C,
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
ELEMENT_EMOJI = {
    "Pyro": "🔥", "Fire": "🔥",
    "Hydro": "💧", "Cryo": "❄️", "Ice": "❄️", "Frost": "❄️",
    "Electro": "⚡", "Electric": "⚡", "Lightning": "⚡",
    "Anemo": "🌪️", "Wind": "🌪️",
    "Geo": "🪨", "Dendro": "🌿",
    "Physical": "👊", "Quantum": "🌌", "Imaginary": "🌟",
    "Ether": "🌸", "Auric Ink": "🖋️",
}
# Checked in order, first match wins, so the more specific names come first.
STAT_EMOJI = [
    ("CRIT Rate", "🎯"), ("CRIT DMG", "💥"),
    ("Elemental Mastery", "🔮"), ("Anomaly Proficiency", "🔮"), ("Anomaly Mastery", "🌀"),
    ("Energy", "🔋"), ("Break Effect", "💢"), ("Effect Hit Rate", "🎲"), ("Effect RES", "🧿"),
    ("Healing", "💚"), ("PEN", "🗡️"), ("Impact", "🔨"),
    ("HP", "❤️"), ("ATK", "⚔️"), ("DEF", "🛡️"), ("SPD", "💨"),
]
DISPLAY_NAMES = {"Energy Regen Rate": "Energy Regen"}
ZZZ_RARITY = {4: "S", 3: "A", 2: "B"}
EFFECT_LIMIT = 900  # characters of weapon effect text per embed
FIELD_LIMIT = 1024
EMBED_LIMIT = 6000
BLANK = "​"


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
    if "DMG Bonus" in stat.name or "DMG Boost" in stat.name:
        emoji = ELEMENT_EMOJI.get(stat.name.split(" DMG")[0], "✨")
    else:
        emoji = next((e for key, e in STAT_EMOJI if key in stat.name), "▫️")
    return f"{emoji} {DISPLAY_NAMES.get(stat.name, stat.name)} **{stat.value}**"


def _stat_fields(build: CharacterBuild) -> list[tuple[str, str]]:
    """Two side-by-side columns; stats at 0 (like 0% Effect RES) are left out."""
    lines = [_stat_line(s) for s in build.stats if not _is_zero(s.value)]
    half = (len(lines) + 1) // 2
    columns = [lines[:half], lines[half:]]
    return [("Stats" if i == 0 else BLANK, "\n".join(col) or BLANK) for i, col in enumerate(columns) if col or i == 0]


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


def build_embed(profile: PlayerProfile, build: CharacterBuild) -> discord.Embed:
    labels = GAME_LABELS[build.game]
    element = f"{ELEMENT_EMOJI.get(build.element, '')} {build.element}".strip()
    embed = discord.Embed(
        title=build.name,
        description=(
            f"{_rarity(build.game, build.rarity)} · {element} · "
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
        embed.add_field(name=labels["weapon"], value=_weapon_value(lines, w, EFFECT_LIMIT), inline=False)

    if build.talents:
        embed.add_field(
            name=labels["talents"],
            value=" · ".join(f"{t.name} `{t.value}`" for t in build.talents),
            inline=False,
        )

    sets = "\n".join(f"🔸 {s}" for s in build.set_bonuses) or "No set bonus."
    embed.add_field(name=labels["gear"], value=sets if build.gear else "Nothing equipped.", inline=False)
    # One column per piece; Discord puts three side by side (stacked on phones).
    for piece in build.gear:
        name, value = _gear_field(piece, labels["max_level"])
        embed.add_field(name=name, value=value, inline=True)

    footer = "Data from Enka.Network"
    if build.notes:
        footer = " ".join(build.notes) + " · " + footer
    embed.set_footer(text=footer)

    # Discord rejects embeds over 6,000 characters; the effect text is the
    # only part long enough to matter, so it gives way first.
    if weapon_field is not None and build.weapon.effect:
        budget = min(EFFECT_LIMIT, len(build.weapon.effect))
        while len(embed) > EMBED_LIMIT and budget > 20:
            budget -= len(embed) - EMBED_LIMIT
            value = _weapon_value(lines, build.weapon, budget)
            embed.set_field_at(weapon_field, name=labels["weapon"], value=value, inline=False)
    return embed
