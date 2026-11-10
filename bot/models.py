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
    path_icon: str | None = None  # path / specialty / weapon type symbol, shown in the info row under the name
    element_icon: str | None = None  # element symbol, shown in the info row and behind the badge number
    outfit_icon: str | None = None  # the character's icon in the outfit (skin) they wear, when they wear one
    cons_icons: list[str] = field(default_factory=list)  # constellation / eidolon icons in unlock order (ZZZ has none)
    source: str = "enka"  # "hoyolab" for characters that aren't on the in-game showcase
    optimized: bool = False  # wearing the best pieces found among the player's relics (bot/optimize.py)
    borrowed_from: str | None = None  # wearing this character's weapon and gear (a what-if, see bot/borrow.py)
    raw: dict = field(default_factory=dict, repr=False, compare=False)  # the showcase entry it was read from
    # Star Rail, for bot/optimize.py: the numbers behind the stats ({"hp", "atk", "def", "spd", "element", "bonus"})
    # and, for HoYoLAB's characters, a showcase-shaped entry without relics to compute them from.
    calc: dict = field(default_factory=dict, repr=False, compare=False)
    bare: dict = field(default_factory=dict, repr=False, compare=False)


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
    # Enka's player block as sent (signature, profile picture, name card, ...), for /<game>-stats.
    player: dict = field(default_factory=dict, repr=False)
