"""Game-agnostic view of one character's build, filled in by each game adapter."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Stat:
    name: str
    value: str  # already formatted for display, e.g. "2,345" or "62.4%"
    rolls: int = 0  # gear substats only: times rolled, counting the first (0 = unknown)


@dataclass
class Gear:
    """One artifact / relic / drive disc."""

    slot: str
    set_name: str
    level: int
    rarity: int
    main: Stat
    subs: list[Stat] = field(default_factory=list)
    piece_icon: str | None = None  # image URL of this piece itself


@dataclass
class Weapon:
    name: str
    level: int
    refinement: int  # refinement / superimposition / phase
    rarity: int
    stats: list[Stat] = field(default_factory=list)
    icon_url: str | None = None  # picture of the weapon / light cone / W-Engine


@dataclass
class CharacterBuild:
    game: str  # "genshin" | "hsr" | "zzz"
    character_id: str
    name: str
    level: int
    rarity: int
    element: str
    constellation: int  # constellation / eidolon / mindscape
    icon_url: str | None
    stats: list[Stat]
    talents: list[Stat]
    weapon: Weapon | None
    gear: list[Gear]
    set_bonuses: list[str]
    notes: list[str] = field(default_factory=list)
    art_url: str | None = None  # large character art for the build card


@dataclass
class PlayerProfile:
    game: str
    uid: str
    nickname: str
    level: int
    characters: list[CharacterBuild]
    ttl: int
    profile_url: str
    # Names shown on the profile even when detailed builds are hidden.
    showcase_names: list[str] = field(default_factory=list)
