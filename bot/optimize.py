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
    x (1 + Break Effect) x turns

Elation characters deal Elation DMG, which uses a fixed base instead of ATK and Elation instead of DMG Boost:

    7535.107 (at Lv. 80) x (1 + Elation) x (1 + CRIT Rate x CRIT DMG) x DEF multiplier x turns

Only the parts the character builds for count: the stats the game itself recommends for them (the same list the
build card's effective substats use). So Firefly is scored on ATK, Break Effect and SPD, and Castorice on HP and crit.
Set effects that depend on the build (Space Sealing Station's SPD 120, Rutilant Arena's 70% CRIT Rate) and the ones a
set gives its wearer in combat are counted, at full stacks. The DEF multiplier is for an enemy of ENEMY_LEVEL with the
sets' DEF ignore. RES, DMG Taken, DMG Reduction, Weaken, Merrymaking and Punchline come from the enemy and the team,
not the gear, so they multiply every candidate alike and are left at 1.

"turns" is how often the character acts in Memory of Chaos, so Speed only pays at its breakpoints: the first cycle is
150 action value long and every later one 100, a turn costs 10000 / SPD, and the turns taken within the first 1, 2,
... CYCLES cycles are averaged (as turns per 100 action value, so 100 SPD is about 1).

A light cone counts with its base stats and its whole passive, read from the passive's text (bot/cone_effects.py):
like the sets, as active and at full stacks. The character's own abilities count the same way (bot/kit.py): the buffs
their kit gives them, and the multiplier of their strongest hit, so the index is the size of that hit before the
enemy's RES and the team's buffs.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass, replace

from . import cone_effects, kit as kits
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
CYCLES = 5  # Memory of Chaos clears of 1 to 5 cycles
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
    cone_effect: dict[str, float] | None = None  # what the picked light cone's passive was counted as
    kit: kits.Kit | None = None  # what the character's own abilities were counted as


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


def character_id(assets: Assets, name: str) -> str | None:
    for cid, info in assets.data.get("hsr_characters", {}).items():
        if (info.get("Name") or assets.hsr_text(info.get("AvatarName", {}).get("Hash"))) == name:
            return cid
    return None


def recommended(assets: Assets, set_ids_for, name: str, planar: bool) -> list[str]:
    """The names of the sets the game recommends for the character called name, best first. set_ids_for is
    EffectiveStats.recommended_sets."""
    cid = character_id(assets, name)
    by_id = {int(sid): set_name for set_name, sid in set_ids(assets).items()}
    return [by_id[i] for i in (set_ids_for(cid, planar) if cid else []) if i in by_id]


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


def with_speed(wanted: set[str] | None, speed: bool | None) -> set[str]:
    """The stats to score on, with Speed forced in or out when the player says so (None: as the character builds)."""
    stats = set(wanted or DEFAULT_WANTED)
    if speed is True:
        stats.add("SPD")
    elif speed is False:
        stats.discard("SPD")
    return stats


def turns(spd: float) -> float:
    """Turns per 100 action value in Memory of Chaos, averaged over clears of 1 to CYCLES cycles."""
    total = 0.0
    for cycles in range(1, CYCLES + 1):
        length = 50 + 100 * cycles  # the first cycle is 150 long
        total += int(length * spd / 10000 + 1e-9) / (length / 100)
    return total / CYCLES


class Scorer:
    """The damage index of one character for any set of relic stats."""

    def __init__(self, assets: Assets, calc: dict, wanted: set[str] | None, level: int = 80, elation: bool = False,
                 cone: dict[str, float] | None = None, kit: kits.Kit | None = None):
        self.calc = calc
        self.cone = cone or {}  # what the light cone's passive adds in combat
        self.kit = kit or kits.Kit()  # the character's own abilities: their strongest hit and self-buffs
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
        for extra in (self.cone, self.kit.buffs):
            for key, value in extra.items():
                bonus[key] += value
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
            score *= (1 + bonus["BreakDamageAddedRatioBase"]) * (1 + bonus["BreakDMG"])
        if self.speed:
            score *= turns(totals["spd"])
        return score * (1 + bonus["Vulnerability"]) * self.kit.multiplier


def _undominated(pieces: list[Piece], keys: set[str]) -> list[Piece]:
    """Drops pieces another piece of the slot beats or ties on every stat that can matter."""
    kept: list[Piece] = []
    for p in sorted(pieces, key=lambda p: -sum(p.props.get(k, 0) for k in keys)):
        if not any(all(q.props.get(k, 0) >= p.props.get(k, 0) for k in keys) for q in kept):
            kept.append(p)
    return kept


def optimize(assets: Assets, target: CharacterBuild, builds: list[CharacterBuild], relic_set: str, planar_set: str,
             wanted: set[str] | None, exclude: set[str] | None = None) -> Result:
    """The target in the best pieces of the two sets that the player's characters wear. The relics of the characters
    and the light cones of the characters named in exclude stay where they are."""
    exclude = (exclude or set()) - {target.name}  # the target's own gear is theirs to keep or swap
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
    enhanced = any(int(p.get("pointId", 0)) > 10_000_000 for p in info.get("skillTreeList", []))

    def with_cone(equipment: dict | None) -> tuple[CharacterBuild, Scorer]:
        bare = sr.parse_character(assets, {**{k: v for k, v in info.items() if k != "equipment"},
                                           **({"equipment": equipment} if equipment else {})})
        scorer = Scorer(assets, bare.calc, wanted, bare.level, elation, cone_effects.effect(assets, equipment))
        scorer.kit = kits.kit(assets, info.get("avatarId"), enhanced, scorer.scaling)
        return bare, scorer

    # The light cones to try: their own first, then every one of their Path that another character wears.
    cones: list[tuple[str, dict | None]] = [(target.name, info.get("equipment"))]
    seen = {_cone_key(info.get("equipment"))}
    for other in builds:
        eq = (other.bare or other.raw).get("equipment")
        if other.name in exclude:
            continue
        if eq and _cone_key(eq) not in seen and assets.data["hsr_weapons"].get(str(eq.get("tid")), {}).get("AvatarBaseType") == path:
            seen.add(_cone_key(eq))
            cones.append((other.name, eq))
    bare, scorer = with_cone(info.get("equipment"))

    everything = pool([b for b in builds if b.name not in exclude])
    by_slot: dict[str, list[Piece]] = {}
    missing = []
    for slot in sr.SLOT_ORDER:
        wanted_set = planar_set if slot in PLANAR_SLOTS else relic_set
        by_slot[slot] = [p for p in everything if p.gear.slot == slot and id_of(p.gear.set_name) == ids[wanted_set]]
        if not by_slot[slot]:
            missing.append(f"{slot} ({wanted_set})")
    if missing:
        raise OptimizeError("None of this player's characters wears these pieces with readable stats: "
                            + ", ".join(missing) + ". Only relics worn by a character can be used."
                            + (" Excluded: " + ", ".join(sorted(exclude)) + "." if exclude else ""))

    # Stats nothing in the index or the set effects reads can't change the result, so pieces are compared without them.
    keys = {k for p in everything for k in p.props} - {"HealRatioBase", "SPRatioBase"}
    keys = {k for k in keys if not k.endswith("AddedRatio") or k == scorer.dmg_key
            or k in ("HPAddedRatio", "AttackAddedRatio", "DefenceAddedRatio", "SpeedAddedRatio")}
    slots = [_undominated(by_slot[slot], keys) for slot in sr.SLOT_ORDER]
    # More pieces than can be tried (an account with many characters in the same set): the fullest slot loses the
    # piece that does the least for this character on its own, until the search fits.
    for slot_pieces in slots:
        slot_pieces.sort(key=lambda p: -scorer.index([p.props], {}))
    while _product(slots) * len(cones) > MAX_TRIES:
        max(slots, key=len).pop()

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

    # What the character wears now is always a candidate, so trimming can never make the answer worse than it.
    own = [next((p for p in by_slot[slot] if p.owner == target.name), None) for slot in sr.SLOT_ORDER]
    if all(own):
        for n, (_, cone_scorer) in enumerate(tries):
            value = cone_scorer.index([p.props for p in own], sets)
            if value > best_index:
                best, best_index, best_cone = tuple(own), value, n

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
                  cones[best_cone][0] if weapon else None, len(cones), dict(best_scorer.cone), best_scorer.kit)


def _cone_key(equipment: dict | None) -> tuple:
    e = equipment or {}
    return (str(e.get("tid")), int(e.get("rank", 1) or 1), int(e.get("level", 1) or 1)) if e else ()


def _product(slots: list[list[Piece]]) -> int:
    total = 1
    for s in slots:
        total *= len(s)
    return total
