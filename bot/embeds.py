"""Discord embeds for a character build."""

from __future__ import annotations

import discord

from .models import CharacterBuild, PlayerProfile, Stat

GAME_LABELS = {
    "genshin": {"title": "Genshin Impact", "cons": "C", "refine": "R", "weapon": "Weapon", "talents": "Talents", "color": 0x4E7CFF},
    "hsr": {"title": "Honkai: Star Rail", "cons": "E", "refine": "S", "weapon": "Light Cone", "talents": "Traces", "color": 0xB6A0FF},
    "zzz": {"title": "Zenless Zone Zero", "cons": "M", "refine": "P", "weapon": "W-Engine", "talents": "Skills", "color": 0xF2C94C},
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
ZZZ_RARITY = {4: "S", 3: "A", 2: "B"}


def _rarity(game: str, rarity: int) -> str:
    if game == "zzz":
        return f"{ZZZ_RARITY.get(rarity, '?')}-Rank"
    return "★" * rarity


def _stat_block(stats: list[Stat]) -> str:
    width = max((len(s.name) for s in stats), default=0)
    lines = [f"{s.name:<{width}}  {s.value:>8}" for s in stats]
    return "```\n" + "\n".join(lines) + "\n```"


def build_embed(profile: PlayerProfile, build: CharacterBuild) -> discord.Embed:
    labels = GAME_LABELS[build.game]
    embed = discord.Embed(
        title=f"{build.name} · Lv. {build.level}",
        description=(
            f"{_rarity(build.game, build.rarity)} · {build.element} · "
            f"{labels['cons']}{build.constellation}"
        ),
        color=ELEMENT_COLORS.get(build.element, labels["color"]),
        url=profile.profile_url,
    )
    embed.set_author(name=f"{profile.nickname} · UID {profile.uid} · {labels['title']}")
    if build.icon_url:
        embed.set_thumbnail(url=build.icon_url)

    embed.add_field(name="Stats", value=_stat_block(build.stats), inline=False)

    if build.weapon:
        w = build.weapon
        lines = [f"**{w.name}** · {labels['refine']}{w.refinement} · Lv. {w.level}"]
        if w.stats:
            lines.append(" · ".join(f"{s.name} {s.value}" for s in w.stats))
        embed.add_field(name=labels["weapon"], value="\n".join(lines), inline=False)

    if build.talents:
        embed.add_field(
            name=labels["talents"],
            value=" · ".join(f"{t.name} **{t.value}**" for t in build.talents),
            inline=False,
        )

    if build.set_bonuses:
        embed.add_field(name="Sets", value="\n".join(build.set_bonuses), inline=False)

    for piece in build.gear:
        value = f"**{piece.main.name} {piece.main.value}**\n" + "\n".join(f"{s.name} {s.value}" for s in piece.subs)
        embed.add_field(name=f"{piece.slot} +{piece.level}", value=value[:1024], inline=True)

    if not build.gear:
        embed.add_field(name="Gear", value="Nothing equipped.", inline=False)

    footer = "Data from Enka.Network"
    if build.notes:
        footer = " ".join(build.notes) + " · " + footer
    embed.set_footer(text=footer)
    return embed
