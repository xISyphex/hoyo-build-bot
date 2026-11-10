"""/hsr-optimize: the best relics for a character out of the ones the player's characters wear.

HoYoLAB (and the showcase) list every character's relics, so those are the pieces to choose from. The player names a
relic set and a planar set; every way to fill the six slots with their pieces of those sets is tried, and the one
with the highest damage index wins.

The light cone is part of the search too: every light cone of the character's Path that one of the player's
characters wears is tried with every relic combination.

The damage index follows the game's damage formula
(Base DMG x DMG% x DEF x RES x DMG Taken x DMG Reduction x Weaken, times the crit multiplier), keeping the parts gear
changes:

    scaling stat (ATK, HP or DEF) x (1 + DMG Boost) x (1 + CRIT Rate x CRIT DMG) x DEF multiplier
    x (1 + Break Effect) x SPD

Elation characters deal Elation DMG, which uses a fixed base instead of ATK and Elation instead of DMG Boost:

    7535.107 (at Lv. 80) x (1 + Elation) x (1 + CRIT Rate x CRIT DMG) x DEF multiplier x SPD

Only the parts the character builds for count: the stats the game itself recommends for them (the same list the
build card's effective substats use). So Firefly is scored on ATK, Break Effect and SPD, and Castorice on HP and crit.
Set effects that depend on the build (Space Sealing Station's SPD 120, Rutilant Arena's 70% CRIT Rate) and the ones a
set gives its wearer in combat are counted, at full stacks. The DEF multiplier is for an enemy of ENEMY_LEVEL with the
sets' DEF ignore. RES, DMG Taken, DMG Reduction, Weaken, Merrymaking and Punchline come from the enemy and the team,
not the gear, so they multiply every candidate alike and are left at 1. A light cone counts with its base stats and
the stats its passive always gives; passive effects that need a trigger aren't in the game data as numbers.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass, replace

from .assets import Assets
from .games import starrail as sr
from .models import CharacterBuild, Gear

RELIC_SLOTS = sr.SLOT_ORDER[:4]
PLANAR_SLOTS = sr.SLOT_ORDER[4:]
PROP_OF = {name: prop for prop, name in sr.PROP_SHORT.items()}  # "CRIT Rate" -> "CriticalChanceBase"
DEFAULT_WANTED = ("CRIT Rate", "CRIT DMG", "ATK%", "SPD")  # for characters the game has no recommendation for yet
MAX_TRIES = 400_000
ENEMY_LEVEL = 95  # Memory of Chaos, last floors
ELATION_BASE = 7535.107  # what Elation DMG uses in place of ATK at Lv. 80
SCALING = {"ATK%": "atk", "HP%": "hp", "DEF%": "def"}


@dataclass
class Piece:
    gear: Gear
    owner: str  # the character wearing it now
    props: dict[str, float]


@dataclass
class Result:
    build: CharacterBuild  # the character in the chosen pieces
    pieces: list[Piece]
    index: float
    current: float | None  # the index of what they wear now (None when they wear nothing)
    counted: list[str]  # the stats the index is made of, for the reply
    tried: int
    cone_owner: str | None = None  # whose light cone was picked (None: no light cone to pick)
    cones: int = 0  # how many light cones were tried


class OptimizeError(Exception):
    """Raised with a message that is safe to show to Discord users."""


def _number(text: str) -> float:
    try:
        return float(text.replace(",", "").rstrip("%"))
    except ValueError:
        return 0.0


def gear_props(piece: Gear) -> dict[str, float]:
    """A relic's main stat and substats as the game's property names, read back from the card's own lines."""
    props: dict[str, float] = defaultdict(float)
    for stat in [piece.main, *piece.subs]:
        prop = PROP_OF.get(stat.name)
        if prop:
            value = _number(stat.value)
            props[prop] += value / 100 if stat.value.endswith("%") else value
    return dict(props)


def _canon(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def set_ids(assets: Assets) -> dict[str, str]:
    """Set name -> id, for every relic and planar set."""
    return {s["name"]: sid for sid, s in assets.data.get("srr_relic_sets", {}).items() if s.get("name")}


def _id_of(ids: dict[str, str]):
    """Looks a set up by the name on a relic, whatever its apostrophes and capitals."""
    canon = {_canon(name): sid for name, sid in ids.items()}
    return lambda name: canon.get(_canon(name or ""))


def set_names(assets: Assets, planar: bool) -> list[str]:
    return sorted(name for name, sid in set_ids(assets).items() if (int(sid) >= 300) == planar)


def pool(builds: list[CharacterBuild]) -> list[Piece]:
    """Every relic the player's characters wear that has its stats (HoYoLAB hides them for other players)."""
    pieces = []
    for build in builds:
        for gear in build.gear:
            if gear.slot in sr.SLOT_ORDER and (props := gear_props(gear)):
                pieces.append(Piece(gear, build.name, props))
    return pieces


# What a set gives its wearer in combat beyond the plain stats in the game data, at full stacks and with its condition
# met. Each entry gets the build's totals so far (hp, atk, def, spd and the bonus table) and returns what to add.
# Effects that only multiply the result (DEF ignore, a bonus to one kind of attack on top of others) change every
# candidate alike once the sets are fixed, so only the ones that share a pool with relic stats are listed.
def _at(value: float, steps: list[tuple[float, float]]) -> float:
    return max((gain for need, gain in steps if value >= need), default=0.0)


SET_EFFECTS = {
    # relic sets, 4 pieces
    "104": lambda t, b: {"CriticalDamageBase": 0.25},
    "105": lambda t, b: {"AttackAddedRatio": 0.25},
    "107": lambda t, b: {"FireAddedRatio": 0.12, "DMG": 0.12},
    "108": lambda t, b: {"DefIgnore": 0.20},
    "109": lambda t, b: {"AttackAddedRatio": 0.20},
    "112": lambda t, b: {"CriticalChanceBase": 0.10},
    "113": lambda t, b: {"CriticalChanceBase": 0.16},
    "115": lambda t, b: {"AttackAddedRatio": 0.48, "DMG": 0.20},
    "116": lambda t, b: {"DefIgnore": 0.18},
    "119": lambda t, b: {"BreakDefIgnore": _at(b["BreakDamageAddedRatioBase"], [(1.5, 0.10), (2.5, 0.25)])},
    "129": lambda t, b: {"ElationDefIgnore": 0.20},
    "117": lambda t, b: {"DMG": 0.12, "CriticalChanceBase": 0.04, "CriticalDamageBase": 0.24},
    "120": lambda t, b: {"DMG": 0.36},
    "122": lambda t, b: {"DMG": 0.20},
    "123": lambda t, b: {"SpeedAddedRatio": 0.06, "CriticalDamageBase": 0.30},
    "124": lambda t, b: {"CriticalChanceBase": 0.32 if t["spd"] < 95 else 0.20 if t["spd"] < 110 else 0.0},
    "127": lambda t, b: {"HPAddedRatio": 0.24, "DMG": 0.15},
    "130": lambda t, b: {"CriticalChanceBase": _at(t["spd"], [(120, 0.10), (160, 0.18)])},
    "131": lambda t, b: {"DMG": 0.54},
    "132": lambda t, b: {"CriticalDamageBase": 0.28},
    "134": lambda t, b: {"AttackAddedRatio": 0.20, "DMG": 0.36},
    # planar sets
    "301": lambda t, b: {"AttackAddedRatio": _at(t["spd"], [(120, 0.12)])},
    "302": lambda t, b: {"AttackAddedRatio": _at(t["spd"], [(120, 0.08)])},
    "303": lambda t, b: {"AttackAddedRatio": min(0.25, 0.25 * b["StatusProbabilityBase"])},
    "304": lambda t, b: {"DefenceAddedRatio": _at(b["StatusProbabilityBase"], [(0.5, 0.15)])},
    "306": lambda t, b: {"DMG": _at(b["CriticalChanceBase"], [(0.5, 0.15)])},
    "307": lambda t, b: {"BreakDamageAddedRatioBase": _at(t["spd"], [(145, 0.20)])},
    "309": lambda t, b: {"DMG": _at(b["CriticalChanceBase"], [(0.7, 0.20)])},
    "310": lambda t, b: {"CriticalDamageBase": _at(b["StatusResistanceBase"], [(0.3, 0.10)])},
    "311": lambda t, b: {"DMG": _at(t["spd"], [(135, 0.12), (160, 0.18)])},
    "313": lambda t, b: {"CriticalDamageBase": 0.40},
    "314": lambda t, b: {"CriticalChanceBase": 0.12},
    "315": lambda t, b: {"DMG": 0.25, "CriticalDamageBase": 0.25},
    "316": lambda t, b: {"BreakDamageAddedRatioBase": 0.40},
    "318": lambda t, b: {"CriticalDamageBase": 0.32},
    "319": lambda t, b: {"CriticalDamageBase": _at(t["hp"], [(5000, 0.28)])},
    "322": lambda t, b: {"DMG": _at(t["atk"], [(2400, 0.12), (3600, 0.24)])},
    "324": lambda t, b: {"CriticalDamageBase": 0.32},
    "325": lambda t, b: {"CriticalDamageBase": _at(b["ElationDamageAddedRatioBase"], [(0.4, 0.20), (0.8, 0.32)])},
    "326": lambda t, b: {"AttackAddedRatio": 0.24, "CriticalDamageBase": 0.12},
    "327": lambda t, b: {"CriticalDamageBase": 0.32},
}


class Scorer:
    """The damage index of one character for any set of relic stats."""

    def __init__(self, assets: Assets, calc: dict, wanted: set[str] | None, level: int = 80, elation: bool = False):
        self.calc = calc
        self.level = level
        self.elation = elation  # an Elation character: Elation DMG's formula
        self.wanted = set(wanted or DEFAULT_WANTED)
        self.skills = assets.data["hsr_meta"]["relic"]["setSkill"]
        self.scaling = next((key for name, key in SCALING.items() if name in self.wanted), None if elation else "atk")
        self.crit = "CRIT Rate" in self.wanted or elation
        self.crit_dmg = "CRIT DMG" in self.wanted
        self.break_effect = "Break Effect" in self.wanted
        self.speed = "SPD" in self.wanted
        self.dmg_key = f"{calc['element']}AddedRatio"

    def counted(self) -> list[str]:
        names = [self.scaling.upper()] if self.scaling else []
        names += ["Elation"] if self.elation else [f"{sr.ELEMENTS.get(self.calc['element'], 'Elemental')} DMG"]
        names += ["CRIT Rate", "CRIT DMG"] if self.crit else ["CRIT DMG"] if self.crit_dmg else []
        names += ["Break Effect"] if self.break_effect else []
        names += ["SPD"] if self.speed else []
        return names

    def bonus(self, props: list[dict[str, float]], sets: dict[str, int]) -> dict[str, float]:
        """The character's own bonuses plus these relic stats and the sets' plain stats (what the character screen shows)."""
        bonus = defaultdict(float, self.calc["bonus"])
        for p in props:
            for key, value in p.items():
                bonus[key] += value
        for set_id, count in sets.items():
            for need in (2, 4):
                if count >= need:
                    for key, value in (self.skills.get(set_id, {}).get(str(need), {}).get("props") or {}).items():
                        bonus[key] += value
        return bonus

    def index(self, props: list[dict[str, float]], sets: dict[str, int]) -> float:
        bonus = self.bonus(props, sets)
        totals = sr.totals(self.calc, bonus)
        for set_id, count in sets.items():
            effect = SET_EFFECTS.get(set_id)
            if effect and count >= (2 if int(set_id) >= 300 else 4):
                for key, value in effect(totals, bonus).items():
                    bonus[key] += value
        totals = sr.totals(self.calc, bonus)
        ignore = bonus["DefIgnore"]
        if self.elation:
            # Elation DMG: a fixed base in place of ATK, Elation in place of DMG Boost. A stat the game still
            # recommends for the character (their kit turns it into Elation or other damage) stays in.
            score = ELATION_BASE * (1 + bonus["ElationDamageAddedRatioBase"])
            score *= totals[self.scaling] / self.calc[self.scaling] if self.scaling else 1
            ignore += bonus["ElationDefIgnore"]
        else:
            score = totals[self.scaling]
            score *= 1 + bonus[self.dmg_key] + bonus["AllDamageTypeAddedRatio"] + bonus["DMG"]
        if self.break_effect:
            ignore += bonus["BreakDefIgnore"]
        score *= (self.level + 20) / ((ENEMY_LEVEL + 20) * (1 - min(ignore, 1.0)) + self.level + 20)
        rate = min(max(bonus["CriticalChanceBase"], 0.0), 1.0)
        if self.crit:
            score *= 1 + rate * bonus["CriticalDamageBase"]
        elif self.crit_dmg:  # supports whose buff grows with their own CRIT DMG
            score *= 1 + bonus["CriticalDamageBase"]
        if self.break_effect:
            score *= 1 + bonus["BreakDamageAddedRatioBase"]
        if self.speed:
            score *= totals["spd"] / 100
        return score


def _undominated(pieces: list[Piece], keys: set[str]) -> list[Piece]:
    """Drops pieces another piece of the slot beats or ties on every stat that can matter."""
    kept: list[Piece] = []
    for p in sorted(pieces, key=lambda p: -sum(p.props.get(k, 0) for k in keys)):
        if not any(all(q.props.get(k, 0) >= p.props.get(k, 0) for k in keys) for q in kept):
            kept.append(p)
    return kept


def optimize(assets: Assets, target: CharacterBuild, builds: list[CharacterBuild], relic_set: str, planar_set: str,
             wanted: set[str] | None) -> Result:
    """The target in the best pieces of the two sets that the player's characters wear."""
    ids = set_ids(assets)
    for name, planar in ((relic_set, False), (planar_set, True)):
        if name not in ids or (int(ids[name]) >= 300) != planar:
            raise OptimizeError(f"**{name}** isn't a {'planar' if planar else 'relic'} set.")
    id_of = _id_of(ids)
    info = target.bare or {k: v for k, v in target.raw.items() if k != "relicList"}
    if not info:
        raise OptimizeError(f"I can't read **{target.name}**'s level and traces, so their stats can't be worked out.")
    info = sr.maxed(assets, info)  # fully built: Lv. 80 with every trace
    path = assets.data["hsr_characters"].get(str(info.get("avatarId")), {}).get("AvatarBaseType")
    elation = path == "Elation"

    def with_cone(equipment: dict | None) -> tuple[CharacterBuild, Scorer]:
        bare = sr.parse_character(assets, {**{k: v for k, v in info.items() if k != "equipment"},
                                           **({"equipment": equipment} if equipment else {})})
        return bare, Scorer(assets, bare.calc, wanted, bare.level, elation)

    # The light cones to try: their own first, then every one of their Path that another character wears.
    cones: list[tuple[str, dict | None]] = [(target.name, info.get("equipment"))]
    seen = {_cone_key(info.get("equipment"))}
    for other in builds:
        eq = (other.bare or other.raw).get("equipment")
        if eq and _cone_key(eq) not in seen and assets.data["hsr_weapons"].get(str(eq.get("tid")), {}).get("AvatarBaseType") == path:
            seen.add(_cone_key(eq))
            cones.append((other.name, eq))
    bare, scorer = with_cone(info.get("equipment"))

    everything = pool(builds)
    by_slot: dict[str, list[Piece]] = {}
    missing = []
    for slot in sr.SLOT_ORDER:
        wanted_set = planar_set if slot in PLANAR_SLOTS else relic_set
        by_slot[slot] = [p for p in everything if p.gear.slot == slot and id_of(p.gear.set_name) == ids[wanted_set]]
        if not by_slot[slot]:
            missing.append(f"{slot} ({wanted_set})")
    if missing:
        raise OptimizeError("None of this player's characters wears these pieces with readable stats: "
                            + ", ".join(missing) + ". Only relics worn by a character can be used.")

    # Stats nothing in the index or the set effects reads can't change the result, so pieces are compared without them.
    keys = {k for p in everything for k in p.props} - {"HealRatioBase", "SPRatioBase"}
    keys = {k for k in keys if not k.endswith("AddedRatio") or k == scorer.dmg_key
            or k in ("HPAddedRatio", "AttackAddedRatio", "DefenceAddedRatio", "SpeedAddedRatio")}
    slots = [_undominated(by_slot[slot], keys) for slot in sr.SLOT_ORDER]
    while _product(slots) * len(cones) > MAX_TRIES:  # far more than anyone owns of one set; trims the weakest of the fullest slot
        fullest = max(slots, key=len)
        fullest.pop()

    sets = {ids[relic_set]: 4, ids[planar_set]: 2}
    best, best_index, tried, best_cone = None, -1.0, 0, 0
    tries = [with_cone(eq) for _, eq in cones]
    combos = [(combo, [p.props for p in combo]) for combo in itertools.product(*slots)]
    for n, (_, cone_scorer) in enumerate(tries):
        for combo, props in combos:
            tried += 1
            value = cone_scorer.index(props, sets)
            if value > best_index:
                best, best_index, best_cone = combo, value, n

    current = None
    if target.gear:
        counts: dict[str, int] = defaultdict(int)
        for g in target.gear:
            if id_of(g.set_name):
                counts[id_of(g.set_name)] += 1
        current = scorer.index([gear_props(g) for g in target.gear], dict(counts))

    gear = [p.gear for p in best]
    bare, best_scorer = tries[best_cone]
    bonus = best_scorer.bonus([p.props for p in best], sets)
    weapon = bare.weapon
    if best_cone == 0 and target.weapon:
        weapon = target.weapon
    build = replace(bare, gear=gear, stats=sr.stat_lines(bare.calc, bonus), set_bonuses=[f"4pc {relic_set}", f"2pc {planar_set}"],
                    source=target.source, art_url=target.art_url, icon_url=target.icon_url, outfit_icon=target.outfit_icon,
                    talents=target.talents or bare.talents, weapon=weapon, borrowed_from=None, optimized=True, score=best_index,
                    score_gain=(best_index / current - 1) * 100 if current else None)
    return Result(build, list(best), best_index, current, scorer.counted(), tried,
                  cones[best_cone][0] if weapon else None, len(cones))


def _cone_key(equipment: dict | None) -> tuple:
    e = equipment or {}
    return (str(e.get("tid")), int(e.get("rank", 1) or 1), int(e.get("level", 1) or 1)) if e else ()


def _product(slots: list[list[Piece]]) -> int:
    total = 1
    for s in slots:
        total *= len(s)
    return total
