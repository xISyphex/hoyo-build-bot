# Ported in part from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/optimization/engine/config/tag.ts (DamageTag bits) and src/lib/conditionals/ashblazingCompute.ts, branch main as of 2026-11-16.
"""The declarative model the damage engine reads: values, conditions, effects, hits, abilities and definitions.

Every number in a definition is a Value. A Value is either a plain number (for numbers the game data does not carry,
such as eidolon effects) or a reference to the game data that is resolved for the request: P (an ability's params at
the level the user chose, eidolon level bumps included), T (a major trace's params), LC (the light cone's params at
its superimposition) and Tog (a toggle or slider of the definition). Values combine with + - * and /, so
``P("talent", 0) * Tog("stacks")`` is "the talent's first param per stack".

A few values depend on the build itself (Scale: "BE +0.8% for every 10 ATK above 1800"); conditions can too
(StatAtLeast: "when CRIT Rate is at least 70%"). The engine evaluates those per relic combination, everything else
once per request. See bot/calc/PORTING.md for how definitions are written.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Callable, Literal, Union


class Tag(enum.IntFlag):
    """What kind of damage a hit is, and which hits a buff applies to. Same bits as Fribbels' DamageTag."""
    NONE = 0
    BASIC = 1
    SKILL = 2
    ULT = 4
    FUA = 8
    DOT = 16
    BREAK = 32
    SUPER_BREAK = 64
    MEMO = 128
    ADDITIONAL = 256
    ELATION = 512
    ASSIST = 1024


ALL = Tag(2047)
DIRECT = ALL & ~(Tag.DOT | Tag.BREAK | Tag.SUPER_BREAK)  # hits that are attacks (Tribbie's E1 True DMG, ...)

ELEMENTS = ("Physical", "Fire", "Ice", "Lightning", "Wind", "Quantum", "Imaginary")
# Game data element names -> ours
GAME_ELEMENTS = {"Physical": "Physical", "Fire": "Fire", "Ice": "Ice", "Thunder": "Lightning", "Lightning": "Lightning",
                 "Wind": "Wind", "Quantum": "Quantum", "Imaginary": "Imaginary"}
# Game data path ids -> the names players know
PATHS = {"Warrior": "Destruction", "Rogue": "Hunt", "Mage": "Erudition", "Shaman": "Harmony", "Warlock": "Nihility",
         "Knight": "Preservation", "Priest": "Abundance", "Memory": "Remembrance", "Elation": "Elation"}

# Stats. "Basic" stats are the ones the character screen shows and relics carry; the rest only exist in combat.
FLAT = ("hp", "atk", "def", "spd")
PERCENT = ("hp%", "atk%", "def%", "spd%")
ELEMENT_DMG = tuple(f"dmg_{e.lower()}" for e in ELEMENTS)
BASIC_STATS = (*FLAT, *PERCENT, "cr", "cd", "be", "ehr", "res", "err", "ohb", "elation", "dmg", *ELEMENT_DMG)
COMBAT_STATS = ("vuln", "def_pen", "res_pen", "final", "true", "cr_boost", "cd_boost", "break_eff", "super_break",
                "merrymaking", "effect_res_pen", "dmg_red")
STATS = (*BASIC_STATS, *COMBAT_STATS)
# What each stat means, for the breakdown the website shows.
STAT_NAMES = {
    "hp": "HP", "atk": "ATK", "def": "DEF", "spd": "SPD", "hp%": "HP%", "atk%": "ATK%", "def%": "DEF%", "spd%": "SPD%",
    "cr": "CRIT Rate", "cd": "CRIT DMG", "be": "Break Effect", "ehr": "Effect Hit Rate", "res": "Effect RES",
    "err": "Energy Regeneration Rate", "ohb": "Outgoing Healing Boost", "elation": "Elation", "dmg": "DMG Boost",
    **{f"dmg_{e.lower()}": f"{e} DMG Boost" for e in ELEMENTS},
    "vuln": "DMG Taken (enemy)", "def_pen": "DEF ignore / reduction", "res_pen": "RES PEN / reduction",
    "final": "Final DMG multiplier", "true": "True DMG", "cr_boost": "CRIT Rate (conditional)",
    "cd_boost": "CRIT DMG (conditional)", "break_eff": "Weakness Break Efficiency", "super_break": "Super Break multiplier",
    "merrymaking": "Merrymaking", "effect_res_pen": "Effect RES PEN", "dmg_red": "DMG Reduction",
}
# Game property names (StarRailRes, Enka, HoYoLAB) -> ours
PROPS = {
    "HPDelta": "hp", "AttackDelta": "atk", "DefenceDelta": "def", "SpeedDelta": "spd", "BaseSpeed": "spd",
    "HPAddedRatio": "hp%", "AttackAddedRatio": "atk%", "DefenceAddedRatio": "def%", "SpeedAddedRatio": "spd%",
    "CriticalChanceBase": "cr", "CriticalDamageBase": "cd", "BreakDamageAddedRatioBase": "be",
    "StatusProbabilityBase": "ehr", "StatusResistanceBase": "res", "SPRatioBase": "err", "HealRatioBase": "ohb",
    "ElationDamageAddedRatioBase": "elation", "AllDamageTypeAddedRatio": "dmg",
    "PhysicalAddedRatio": "dmg_physical", "FireAddedRatio": "dmg_fire", "IceAddedRatio": "dmg_ice",
    "ThunderAddedRatio": "dmg_lightning", "WindAddedRatio": "dmg_wind", "QuantumAddedRatio": "dmg_quantum",
    "ImaginaryAddedRatio": "dmg_imaginary",
    "CriticalChance": "cr", "CriticalDamage": "cd", "StatusProbability": "ehr", "StatusResistance": "res",
    "BreakDamageAddedRatio": "be", "SPRatio": "err", "HealRatio": "ohb",
}

ABILITY_KINDS = ("basic", "skill", "ult", "talent", "memo_skill", "memo_talent", "elation_skill")
DEFAULT_LEVELS = {"basic": 6, "skill": 10, "ult": 10, "talent": 10, "memo_skill": 6, "memo_talent": 6, "elation_skill": 10}
MAX_LEVELS = {"basic": 7, "skill": 12, "ult": 12, "talent": 12, "memo_skill": 7, "memo_talent": 7, "elation_skill": 12}
# The ability slot each kind usually has in the game data's skill ids (<id>01 is the Basic ATK, and so on).
SLOTS = {"basic": "01", "skill": "02", "ult": "03", "talent": "04"}


# ---------------------------------------------------------------------------------------------------------------
# Values


class Value:
    """A number that is resolved for one request. Subclasses implement resolve(ctx) -> float."""

    def resolve(self, ctx) -> float:  # pragma: no cover - abstract
        raise NotImplementedError

    def refs(self):
        """Every leaf value, for checks and the breakdown."""
        yield self

    def __add__(self, other): return Op("+", self, val(other))
    def __radd__(self, other): return Op("+", val(other), self)
    def __sub__(self, other): return Op("-", self, val(other))
    def __rsub__(self, other): return Op("-", val(other), self)
    def __mul__(self, other): return Op("*", self, val(other))
    def __rmul__(self, other): return Op("*", val(other), self)
    def __truediv__(self, other): return Op("/", self, val(other))
    def __rtruediv__(self, other): return Op("/", val(other), self)


@dataclass(frozen=True, eq=False)
class Const(Value):
    value: float

    def resolve(self, ctx) -> float:
        return float(self.value)

    def __repr__(self):
        return repr(self.value)


@dataclass(frozen=True, eq=False)
class P(Value):
    """Param `index` (0-based: #1 in the text is 0) of one of the character's abilities, at the level the user chose
    for `kind` plus the eidolon bumps of that skill. `sid` names the skill when it isn't the kind's usual one, with
    {id} for the character id and {v} for the rework prefix ("1" for reworked kits, "" otherwise): "{v}{id}09" is an
    enhanced Skill, "1{id}02" a memosprite skill."""
    kind: str
    index: int
    sid: str | None = None

    def resolve(self, ctx) -> float:
        return ctx.ability_param(self.kind, self.index, self.sid)

    def __repr__(self):
        return f"P({self.kind!r}, {self.index}{', ' + repr(self.sid) if self.sid else ''})"


@dataclass(frozen=True, eq=False)
class T(Value):
    """Param `index` of major trace `n` (1 = A2, 2 = A4, 3 = A6). Resolves to 0 when the trace isn't unlocked."""
    n: int
    index: int

    def resolve(self, ctx) -> float:
        return ctx.trace_param(self.n, self.index)

    def __repr__(self):
        return f"T({self.n}, {self.index})"


@dataclass(frozen=True, eq=False)
class LC(Value):
    """Param `index` of the light cone's passive at its superimposition."""
    index: int

    def resolve(self, ctx) -> float:
        return ctx.cone_param(self.index)

    def __repr__(self):
        return f"LC({self.index})"


@dataclass(frozen=True, eq=False)
class Tog(Value):
    """The value of one of the definition's toggles (1/0 for switches, the number for sliders)."""
    id: str

    def resolve(self, ctx) -> float:
        return ctx.toggle(self.id)

    def __repr__(self):
        return f"Tog({self.id!r})"


@dataclass(frozen=True, eq=False)
class Pick(Value):
    """values[toggle value] (a select toggle), e.g. a table of CRIT DMG per number of debuffs."""
    id: str
    table: dict

    def resolve(self, ctx) -> float:
        key = ctx.toggle(self.id)
        k = int(key) if float(key).is_integer() else key
        return float(self.table.get(k, 0.0))


@dataclass(frozen=True, eq=False)
class Call(Value):
    """Anything the other values can't express, as a function of the context (team composition, ...). The label is
    what the breakdown shows."""
    fn: Callable
    label: str = "computed"

    def resolve(self, ctx) -> float:
        return float(self.fn(ctx))


@dataclass(frozen=True, eq=False)
class IfV(Value):
    """`then` when the condition holds (a condition known per request: eidolon, trace, toggle, team), else `other`."""
    cond: "Cond"
    then: Value | float
    other: Value | float = 0.0

    def resolve(self, ctx) -> float:
        return val(self.then).resolve(ctx) if self.cond.check(ctx) else val(self.other).resolve(ctx)


@dataclass(frozen=True, eq=False)
class Min(Value):
    a: Value | float
    b: Value | float

    def resolve(self, ctx) -> float:
        return min(val(self.a).resolve(ctx), val(self.b).resolve(ctx))


@dataclass(frozen=True, eq=False)
class Op(Value):
    op: str
    a: Value
    b: Value

    def resolve(self, ctx) -> float:
        a, b = self.a.resolve(ctx), self.b.resolve(ctx)
        if self.op == "+":
            return a + b
        if self.op == "-":
            return a - b
        if self.op == "*":
            return a * b
        return a / b if b else 0.0

    def refs(self):
        yield from self.a.refs()
        yield from self.b.refs()

    def __repr__(self):
        return f"({self.a!r} {self.op} {self.b!r})"


def val(x) -> Value:
    if isinstance(x, Value):
        return x
    if isinstance(x, (int, float)):
        return Const(float(x))
    raise TypeError(f"not a value: {x!r}")


@dataclass(frozen=True, eq=False)
class Scale:
    """A value that depends on the build: `ratio` per `step` of stat `src` above `above`, at most `cap`. Without a
    step it is linear: ratio x (src - above). `src` is read on the main character after every buff, without what
    other conversions and unconvertible buffs (Robin's and Bronya's) added, as in Fribbels' conversions."""
    src: str
    ratio: Value | float
    above: Value | float = 0.0
    step: Value | float | None = None
    cap: Value | float | None = None
    convertible: bool = True  # False: read the full stat (thresholds like "for every 10 SPD over 100")

    def __repr__(self):
        return f"Scale({self.src!r}, {self.ratio!r}, above={self.above}, step={self.step}, cap={self.cap})"


# ---------------------------------------------------------------------------------------------------------------
# Conditions


class Cond:
    dynamic = False  # True: depends on the build's stats

    def __and__(self, other): return All((self, other))
    def __or__(self, other): return Any_((self, other))
    def __invert__(self): return Not(self)


@dataclass(frozen=True)
class Eidolon(Cond):
    n: int

    def check(self, ctx) -> bool:
        return ctx.eidolon >= self.n


@dataclass(frozen=True)
class Trace(Cond):
    """Major trace n (1 = A2, 2 = A4, 3 = A6) is unlocked."""
    n: int

    def check(self, ctx) -> bool:
        return ctx.has_trace(self.n)


@dataclass(frozen=True)
class On(Cond):
    """A toggle is on (switch) or above zero (slider)."""
    id: str

    def check(self, ctx) -> bool:
        return bool(ctx.toggle(self.id))


@dataclass(frozen=True)
class TogAtLeast(Cond):
    id: str
    value: float

    def check(self, ctx) -> bool:
        return ctx.toggle(self.id) >= self.value


@dataclass(frozen=True)
class TeamPath(Cond):
    """At least n characters of the path in the team, the main character included ("Nihility")."""
    path: str
    n: int

    def check(self, ctx) -> bool:
        return ctx.team_path_count(self.path) >= self.n


@dataclass(frozen=True)
class SamePath(Cond):
    """At least n characters of the team (the owner included) share the owner's path (Izumo Gensei)."""
    n: int

    def check(self, ctx) -> bool:
        return ctx.team_path_count(ctx.gd.path(str(ctx.owner["id"]))) >= self.n


@dataclass(frozen=True)
class SameElement(Cond):
    """The owner of the effect and the main character have the same element (Penacony, Planetary Rendezvous)."""

    def check(self, ctx) -> bool:
        return ctx.owner_element == ctx.main_element


@dataclass(frozen=True)
class MainHasMemo(Cond):
    """The main character has a memosprite or summon."""

    def check(self, ctx) -> bool:
        return ctx.main_has_memo


@dataclass(frozen=True)
class OwnerIs(Cond):
    """The owner of the effect is this character (game id): A Grounded Ascent and Sacerdos' Relived Ordeal reach the
    memosprite too when Sunday gives them."""
    id: str

    def check(self, ctx) -> bool:
        return str(ctx.owner["id"]) == self.id


@dataclass(frozen=True)
class Broken(Cond):
    """The enemy is Weakness Broken in this evaluation."""

    def check(self, ctx) -> bool:
        return ctx.enemy_broken


@dataclass(frozen=True)
class Not(Cond):
    c: Cond

    @property
    def dynamic(self):
        return self.c.dynamic

    def check(self, ctx) -> bool:
        return not self.c.check(ctx)


@dataclass(frozen=True)
class All(Cond):
    cs: tuple

    @property
    def dynamic(self):
        return any(c.dynamic for c in self.cs)

    def check(self, ctx) -> bool:
        return all(c.check(ctx) for c in self.cs)


@dataclass(frozen=True)
class Any_(Cond):
    cs: tuple

    @property
    def dynamic(self):
        return any(c.dynamic for c in self.cs)

    def check(self, ctx) -> bool:
        return any(c.check(ctx) for c in self.cs)


@dataclass(frozen=True)
class StatAtLeast(Cond):
    """The main character's stat (after combat buffs) is at least x. Evaluated per relic combination."""
    stat: str
    x: float
    dynamic = True


@dataclass(frozen=True)
class StatBelow(Cond):
    stat: str
    x: float
    dynamic = True


def static_parts(cond: Cond | None) -> tuple[list[Cond], list[Cond]]:
    """Splits a condition that is a conjunction into the parts known per request and the parts that depend on stats."""
    if cond is None:
        return [], []
    if isinstance(cond, All):
        st, dyn = [], []
        for c in cond.cs:
            a, b = static_parts(c)
            st += a
            dyn += b
        return st, dyn
    return ([cond], []) if not cond.dynamic else ([], [cond])


# ---------------------------------------------------------------------------------------------------------------
# Effects, hits, abilities

Target = Literal["self", "memo", "self+memo", "team", "ally", "ally+memo", "ally_memo", "enemy"]
TARGETS = ("self", "memo", "self+memo", "team", "ally", "ally+memo", "ally_memo", "enemy")


@dataclass
class Effect:
    """One buff or debuff.

    target: who gets it, seen from the effect's owner. self / memo / self+memo: the owner and its memosprite or
    summon; team: all allies with their memosprites; ally (+memo): the one ally a single-target ability picks, which
    is the main character when the owner is a teammate (and nobody when the owner is the main character); ally_memo:
    only the summon or memosprite of that ally; enemy: a debuff, which helps every hit of every ally.
    as_teammate: "mutual" counts whether the owner is the main character or a teammate, "teammate_only" only when a
    teammate (single-target buffs computed from the teammate's own stats), "main_only" only for the main character.
    tags: the kinds of hits it applies to (ALL: every hit). element: only hits of that element. actions: only hits of
    these abilities of the main character's rotation ("ult" for "the Ultimate's RES PEN").
    unconvertible: other conversions don't read it (Robin's ATK buff, Bronya's CRIT DMG buff)."""
    stat: str
    value: Value | Scale | float
    target: str = "self"
    tags: Tag = ALL
    element: str | None = None
    when: Cond | None = None
    as_teammate: str = "mutual"
    source: str = ""
    actions: tuple[str, ...] | None = None
    unconvertible: bool = False
    note: str = ""

    def __post_init__(self):
        if self.stat not in STATS:
            raise ValueError(f"unknown stat {self.stat!r}")
        if self.target not in TARGETS:
            raise ValueError(f"unknown target {self.target!r}")
        if self.as_teammate not in ("mutual", "teammate_only", "main_only"):
            raise ValueError(f"unknown as_teammate {self.as_teammate!r}")
        if self.element is not None and self.element not in ELEMENTS:
            raise ValueError(f"unknown element {self.element!r}")
        if not isinstance(self.value, (Value, Scale)):
            self.value = val(self.value)


HIT_FUNCS = ("crit", "dot", "break", "super_break", "additional", "elation", "buff")


@dataclass
class Hit:
    """One damage instance (or, for supports, the size of one buff: func "buff").

    Scalings are Values: atk/hp/def multipliers, be_atk (extra ATK multiplier per point of Break Effect, capped at
    be_cap), elation_atk (extra ATK multiplier per point of Elation). entity: who deals it ("self" or "memo");
    scale: whose ATK/HP/DEF it scales with (Castorice's memosprite hits scale with her HP). toughness: Toughness
    reduction in displayed units (Basic ATK 10), for Super Break. tick: how many times it counts (DoT ticks,
    repeated Additional DMG). For func "buff": src (stat read), ratio, flat; or step/above/per/cap for stepwise
    buffs (Ruan Mei's DMG from Break Effect)."""
    func: str
    tags: Tag
    element: str | None = None
    atk: Value | float = 0.0
    hp: Value | float = 0.0
    def_: Value | float = 0.0
    be_atk: Value | float = 0.0
    be_cap: float | None = None
    elation_atk: Value | float = 0.0
    entity: str = "self"
    scale: str | None = None
    toughness: Value | float = 0.0
    fixed_toughness: Value | float = 0.0
    tick: Value | float = 1.0
    dot_chance: Value | float = 1.0
    dot_split: float = 0.0
    dot_stacks: float = 1.0
    cr_override: Value | float | None = None
    cd_override: Value | float | None = None
    true_dmg: Value | float = 0.0
    elation_scaling: Value | float = 0.0
    punchline: Value | float = 0.0
    min_elation: float = 0.0
    special: Value | float = 1.0  # break: specialScaling
    extra_super_break: Value | float = 0.0
    src: str | None = None  # buff
    ratio: Value | float = 0.0
    flat: Value | float = 0.0
    above: float = 0.0
    step: float | None = None
    per: Value | float = 0.0
    cap: float | None = None
    when: Cond | None = None
    label: str = ""

    def __post_init__(self):
        if self.func not in HIT_FUNCS:
            raise ValueError(f"unknown hit function {self.func!r}")
        for name in ("atk", "hp", "def_", "be_atk", "elation_atk", "toughness", "fixed_toughness", "tick", "dot_chance",
                     "true_dmg", "elation_scaling", "punchline", "special", "extra_super_break", "ratio", "flat", "per"):
            v = getattr(self, name)
            if not isinstance(v, Value):
                setattr(self, name, val(v))
        for name in ("cr_override", "cd_override"):
            v = getattr(self, name)
            if v is not None and not isinstance(v, Value):
                setattr(self, name, val(v))


@dataclass
class AshHit:
    """One hit of a multi-hit ability, for the Ashblazing Grand Duke 4pc stack order (Fribbels' ashblazingCompute).
    kind: single / aoe / blast / bounce / outer."""
    kind: str
    weight: float = 1.0
    count: int = 1


@dataclass
class Ability:
    key: str  # rotation key: "basic", "skill", "ult", "fua", "dot", "break", "memo_skill", "memo_talent", ...
    hits: list[Hit]
    name: str = ""
    turn: bool | None = None  # ends the character's own turn (default: basic and skill do)
    ashblazing: list[AshHit] | None = None  # FUA hit order, when the kit has FUA hits


@dataclass
class Toggle:
    """A switch or slider of a definition (Fribbels' content/defaults). teammate_default is used when the owner is a
    teammate (None: the same as default). Sliders that stand for a teammate's own stats (Robin's ATK) have
    main_default None: they only exist for teammates."""
    id: str
    kind: str = "switch"  # switch / slider / select
    default: float = 1.0
    teammate_default: float | None = None
    min: float = 0.0
    max: float = 1.0
    text: str = ""
    options: dict | None = None  # select: value -> label

    def __post_init__(self):
        if self.kind not in ("switch", "slider", "select"):
            raise ValueError(f"unknown toggle kind {self.kind!r}")
        self.default = float(self.default)
        if self.teammate_default is not None:
            self.teammate_default = float(self.teammate_default)


@dataclass
class Memo:
    """A memosprite's (or summon's) base stats: scale x the owner's character-screen stat + flat."""
    name: str
    atk_scale: float = 0.0
    atk_flat: float = 0.0
    hp_scale: float = 0.0
    hp_flat: float = 0.0
    def_scale: float = 0.0
    def_flat: float = 0.0
    spd_scale: float = 0.0
    spd_flat: float = 0.0
    summon: bool = False


@dataclass
class CharacterDef:
    id: str  # game id; reworked kits are "<id>b1" like Fribbels
    name: str
    abilities: dict[str, Ability]
    effects: list[Effect]
    toggles: list[Toggle] = field(default_factory=list)
    rotation: list[str] = field(default_factory=list)  # Fribbels' comboTurnAbilities, without the first NULL
    memo: Memo | None = None
    advance: Value | float = 0.0  # share of the main character's turns a teammate adds by advancing them
    broken_when: Cond | None = None  # the enemy counts as Weakness Broken (Firefly's Super Break mode)
    reviewed: bool = True  # False: built by the text fallback, results are approximate
    source: str = ""  # the Fribbels file it was ported from
    notes: list[str] = field(default_factory=list)  # simplifications, shown with the result

    @property
    def game_id(self) -> str:
        return self.id.split("b")[0]

    @property
    def variant(self) -> int:
        return 1 if self.id.endswith("b1") else 0

    def __post_init__(self):
        if not isinstance(self.advance, Value):
            self.advance = val(self.advance)
        for key in self.rotation:
            if key not in self.abilities:
                raise ValueError(f"{self.name}: rotation names {key!r}, which isn't an ability")
        ids = [t.id for t in self.toggles]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.name}: duplicate toggle ids")


@dataclass
class LightConeDef:
    id: str
    name: str
    effects: list[Effect]
    toggles: list[Toggle] = field(default_factory=list)
    source: str = ""
    notes: list[str] = field(default_factory=list)
    reviewed: bool = True


@dataclass
class SetDef:
    """A relic or planar set. pieces[2] / pieces[4]: what the main character gets from wearing it (the plain stats
    of the game data are added by the engine, so only the combat effects are listed). team: what the main character
    gets when a teammate wears it (4 pieces of a relic set, 2 of a planar set). nonstackable: the team effect counts
    once however many allies wear the set."""
    id: str
    name: str
    pieces: dict[int, list[Effect]] = field(default_factory=dict)
    team: list[Effect] = field(default_factory=list)
    toggles: list[Toggle] = field(default_factory=list)
    nonstackable: bool = False
    source: str = ""
    notes: list[str] = field(default_factory=list)
    reviewed: bool = True

    @property
    def planar(self) -> bool:
        return int(self.id) >= 300


def ashblazing_stacks(hits: list[AshHit], enemies: int) -> float:
    """Fribbels' weighted average Ashblazing Grand Duke stack count for a hit order (ashblazingCompute.ts), as the
    ATK% it is worth: 6% per stack, at most 8 stacks."""
    def targets(kind: str) -> int:
        return {"single": 1, "aoe": enemies, "blast": min(3, enemies), "outer": max(0, enemies - 1), "bounce": 1}[kind]

    if not hits:
        return 0.0
    stacks = math.ceil(targets(hits[0].kind) / 2)
    total = weight = 0.0
    for h in hits:
        if h.kind == "outer":
            stacks = min(8, stacks + max(0, enemies - 1))
            continue
        if h.kind == "bounce":
            per = h.weight / enemies
            for _ in range(h.count):
                total += stacks * per
                weight += per
                stacks = min(8, stacks + 1)
            continue
        total += stacks * h.weight
        weight += h.weight
        stacks = min(8, stacks + targets(h.kind))
    return 0.06 * total / weight if weight else 0.0


Number = Union[int, float]
