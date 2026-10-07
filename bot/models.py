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


@dataclass
class Weapon:
    name: str
    level: int
    refinement: int  # refinement / superimposition / phase
    rarity: int
    stats: list[Stat] = field(default_factory=list)
    effect_name: str | None = None  # passive / light cone ability / W-Engine effect
    effect: str | None = None  # plain text, already filled in for the refinement


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
