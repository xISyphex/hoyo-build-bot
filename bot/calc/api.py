"""The public entry points and their JSON-shaped request / response types.

    evaluate(assets, request, relics) -> Evaluation       # damage of one set of (up to) six relics
    optimize(assets, request, inventory) -> OptimizeResult  # best six out of an inventory, with alternatives

Every type has to_dict() and a strict from_dict() (unknown fields, wrong types and missing required fields raise
CalcError with the path of the offending field), so the web layer can pass JSON straight through.

Toggle keys (request.toggles) are "<owner>.<kind>.<toggle id>": owner is "main" or "tm0".."tm2" (the teammate's
index), kind is "char", "lc" or "set.<set id>". Example: {"main.char.buffedState": false, "tm0.char.teammateATKValue":
4000, "main.set.117.value": 3}. evaluate() reports the toggles that exist (Evaluation.toggles) for the website to show.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from dataclasses import dataclass, field

import numpy as np

from .engine import CalcError
from .gamedata import GameData
from .model import BASIC_STATS
from .relics import SLOTS, Relic

# ---------------------------------------------------------------------------------------------------------------
# Strict (de)serialisation


def _convert(tp, value, path: str):
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin in (typing.Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        inner = [a for a in args if a is not type(None)]
        return _convert(inner[0], value, path)
    if dataclasses.is_dataclass(tp):
        return _from_dict(tp, value, path)
    if origin is list:
        if not isinstance(value, list):
            raise CalcError(f"{path} must be a list")
        return [_convert(args[0], v, f"{path}[{i}]") for i, v in enumerate(value)]
    if origin is dict:
        if not isinstance(value, dict):
            raise CalcError(f"{path} must be an object")
        return {str(k): _convert(args[1], v, f"{path}.{k}") for k, v in value.items()}
    if tp is bool:
        if not isinstance(value, bool):
            raise CalcError(f"{path} must be true or false")
        return value
    if tp is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise CalcError(f"{path} must be a whole number")
        return value
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalcError(f"{path} must be a number")
        return float(value)
    if tp is str:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise CalcError(f"{path} must be a string")
        return str(value)
    if tp is typing.Any:
        return value
    raise CalcError(f"{path}: unsupported type")  # pragma: no cover


def _from_dict(cls, data, path: str):
    if isinstance(data, cls):
        return data
    if not isinstance(data, dict):
        raise CalcError(f"{path} must be an object")
    hints = typing.get_type_hints(cls)
    fields = {f.name: f for f in dataclasses.fields(cls)}
    unknown = set(data) - set(fields)
    if unknown:
        raise CalcError(f"{path}: unknown field(s) {', '.join(sorted(unknown))}")
    kwargs = {}
    for name, f in fields.items():
        if name in data:
            kwargs[name] = _convert(hints[name], data[name], f"{path}.{name}")
        elif f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            raise CalcError(f"{path}.{name} is required")
    obj = cls(**kwargs)
    validate = getattr(obj, "validate", None)
    if validate:
        validate(path)
    return obj


class _Json:
    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return _from_dict(cls, data, cls.__name__)


# ---------------------------------------------------------------------------------------------------------------
# Requests


@dataclass
class ConeRequest(_Json):
    id: str
    rank: int = 1  # superimposition 1-5
    level: int = 80
    ascension: int | None = None  # None: the usual one for the level

    def validate(self, path="cone"):
        if not 1 <= self.rank <= 5:
            raise CalcError(f"{path}.rank must be 1 to 5")
        if not 1 <= self.level <= 80:
            raise CalcError(f"{path}.level must be 1 to 80")
        if self.ascension is not None and not 0 <= self.ascension <= 6:
            raise CalcError(f"{path}.ascension must be 0 to 6")


@dataclass
class CharacterRequest(_Json):
    id: str
    level: int = 80
    ascension: int | None = None
    eidolon: int = 0
    abilities: dict[str, int] = field(default_factory=dict)  # basic/skill/ult/talent/memo_skill/memo_talent, before eidolons
    traces: dict[str, bool] | None = None  # Kelz names: ability_1..3, stat_1..10; None = all unlocked
    light_cone: ConeRequest | None = None
    ability_version: int | None = None  # 1: reworked kit; None: the newest kit in the game data

    def validate(self, path="character"):
        if not 1 <= self.level <= 80:
            raise CalcError(f"{path}.level must be 1 to 80")
        if not 0 <= self.eidolon <= 6:
            raise CalcError(f"{path}.eidolon must be 0 to 6")
        if self.ascension is not None and not 0 <= self.ascension <= 6:
            raise CalcError(f"{path}.ascension must be 0 to 6")


@dataclass
class TeammateRequest(_Json):
    id: str
    eidolon: int = 0
    light_cone: ConeRequest | None = None
    relic_set: str | None = None  # 4-piece relic set they wear
    planar_set: str | None = None  # planar set they wear
    follows_carry: bool | None = None  # advance supporters: act right after the carry (None: yes if they advance)
    ability_version: int | None = None

    def validate(self, path="teammate"):
        if not 0 <= self.eidolon <= 6:
            raise CalcError(f"{path}.eidolon must be 0 to 6")


@dataclass
class EnemyOptions(_Json):
    """Fribbels' defaults: Lv. 95, one target, 20% RES (0 when weak), 30% Effect RES, 120 Toughness, not broken."""
    level: int = 95
    count: int = 1
    resistance: float = 0.2
    weak: bool = True  # weak to the main character's element (RES 0 for it)
    weaknesses: list[str] | None = None  # explicit weak elements (overrides weak)
    effect_res: float = 0.3
    toughness: float = 120.0  # max Toughness, displayed units
    broken: bool = False

    def validate(self, path="enemy"):
        if not 1 <= self.level <= 120:
            raise CalcError(f"{path}.level must be 1 to 120")
        if self.count not in (1, 3, 5):
            raise CalcError(f"{path}.count must be 1, 3 or 5")
        if not -1 <= self.resistance <= 1 or not 0 <= self.effect_res <= 1:
            raise CalcError(f"{path}: resistances must be between -1 and 1")
        if self.toughness <= 0:
            raise CalcError(f"{path}.toughness must be positive")


@dataclass
class EvaluateRequest(_Json):
    character: CharacterRequest
    teammates: list[TeammateRequest] = field(default_factory=list)
    relic_sets: list[str] = field(default_factory=list)  # [] any; [A] 4pc A; [A, B] 2pc A + 2pc B; [A, "*"] 2pc A + any
    planar_sets: list[str] = field(default_factory=list)  # [] any; else the allowed planar sets
    speed: bool = True  # False: one combo, Speed not counted
    cycles: int = 5  # Memory of Chaos horizon: clears of 1..cycles cycles are averaged
    excluded_owners: list[str] = field(default_factory=list)  # character ids whose relics stay where they are
    enemy: EnemyOptions = field(default_factory=EnemyOptions)
    toggles: dict[str, typing.Any] = field(default_factory=dict)
    main_stats: dict[str, list[str]] = field(default_factory=dict)  # slot -> allowed main stat keys
    min_stats: dict[str, float] = field(default_factory=dict)  # final stat floors, e.g. {"spd": 134}
    top_n: int = 10

    def validate(self, path="request"):
        if len(self.teammates) > 3:
            raise CalcError(f"{path}.teammates: at most 3")
        if len(self.relic_sets) > 2:
            raise CalcError(f"{path}.relic_sets: at most 2")
        if not 1 <= self.cycles <= 10:
            raise CalcError(f"{path}.cycles must be 1 to 10")
        for slot, keys in self.main_stats.items():
            if slot not in SLOTS:
                raise CalcError(f"{path}.main_stats: unknown slot {slot}")
        for k in self.min_stats:
            if k not in ("hp", "atk", "def", "spd", "cr", "cd", "be", "ehr", "res", "err"):
                raise CalcError(f"{path}.min_stats: unsupported stat {k}")
        if not 1 <= self.top_n <= 50:
            raise CalcError(f"{path}.top_n must be 1 to 50")


# ---------------------------------------------------------------------------------------------------------------
# Responses


@dataclass
class Evaluation(_Json):
    total: float  # damage over the horizon (or the buff's size, unit "buff")
    unit: str
    repetitions: float  # how many times the combo was counted
    abilities: list[dict]  # per ability: key, name, per_use, uses, total, hits (with their multipliers)
    effects: list[dict]  # every effect that reached the main character: source, owner, stat, value, target, ...
    stats: dict[str, float]  # the main character's combat stats
    memo_stats: dict[str, float] | None
    relics: list[str]  # uids of the relics evaluated
    sets: dict[str, int]  # set id -> pieces
    character: dict  # id, definition id, name, reviewed
    toggles: dict[str, float]  # every toggle key that exists for this request, with the value used
    approximate: bool
    notes: list[str]


@dataclass
class Alternative(_Json):
    total: float
    relics: list[str]
    sets: dict[str, int]


@dataclass
class OptimizeResult(_Json):
    best: Evaluation | None
    alternatives: list[Alternative]
    current: Evaluation | None  # what the character wears now (None: not six pieces in the inventory)
    candidates: int  # relics left after filtering and pruning
    combinations: int  # combinations evaluated
    elapsed_ms: float
    notes: list[str]


# ---------------------------------------------------------------------------------------------------------------
# Entry points


def _request(request) -> EvaluateRequest:
    return request if isinstance(request, EvaluateRequest) else EvaluateRequest.from_dict(request)


def _relics(items) -> list[Relic]:
    return [r if isinstance(r, Relic) else Relic.from_dict(r) for r in items]


def stat_arrays(relics: list[Relic]) -> tuple[dict, dict]:
    """One build's relic stats and set counts, as length-1 arrays for the engine."""
    stats: dict[str, float] = {}
    counts: dict[str, int] = {}
    for r in relics:
        for k, v in r.stats().items():
            stats[k] = stats.get(k, 0.0) + v
        counts[r.set_id] = counts.get(r.set_id, 0) + 1
    return ({k: np.array([v]) for k, v in stats.items() if k in BASIC_STATS},
            {k: np.array([v]) for k, v in counts.items()})


def evaluate(assets, request, relics) -> Evaluation:
    """The damage of the main character wearing these relics (up to one per slot)."""
    from .prepare import prepare

    req = _request(request)
    relics = _relics(relics)
    slots = [r.slot for r in relics]
    if len(slots) != len(set(slots)):
        raise CalcError("two relics for the same slot")
    prep = prepare(assets, req, {r.set_id for r in relics})
    return _evaluation(prep, req, relics)


def _evaluation(prep, req: EvaluateRequest, relics: list[Relic]) -> Evaluation:
    stats, counts = stat_arrays(relics)
    out = prep.explain(stats, counts)
    notes = list(prep.notes)
    if len(relics) < 6:
        notes.append(f"Only {len(relics)} relic(s) given.")
    return Evaluation(total=out["total"], unit="buff" if prep.buff_only else "damage", repetitions=out["repetitions"],
                      abilities=out["abilities"], effects=out["effects"], stats=out["stats"],
                      memo_stats=out["memo_stats"], relics=[r.uid for r in relics],
                      sets={k: int(v[0]) for k, v in counts.items()},
                      character={"id": req.character.id, "definition": prep.char.id, "name": prep.char.name,
                                 "reviewed": prep.char.reviewed},
                      toggles=toggle_listing(prep.gd.assets, req), approximate=prep.approximate, notes=notes)


def toggle_listing(assets, req: EvaluateRequest) -> dict[str, float]:
    """Every toggle key of this request (main character, its light cone, teammates and their gear), with its value."""
    from . import registry
    from .engine import toggle_values
    from .prepare import character_def, variant_for

    gd = GameData(assets)
    out: dict[str, float] = {}
    overrides = {k: (1.0 if v is True else 0.0 if v is False else v) for k, v in (req.toggles or {}).items()}

    def put(prefix, defs, role):
        for k, v in toggle_values(defs, role, {}, prefix).items():
            out[f"{prefix}.{k}"] = float(overrides.get(f"{prefix}.{k}", v))

    c = req.character
    put("main.char", character_def(gd, c.id, variant_for(gd, c.id, c.ability_version)).toggles, "main")
    if c.light_cone and c.light_cone.id in registry.light_cones():
        put("main.lc", registry.light_cones()[c.light_cone.id].toggles, "main")
    for sid in {*req.relic_sets, *req.planar_sets} - {"*"}:
        if sid in registry.sets():
            put(f"main.set.{sid}", registry.sets()[sid].toggles, "main")
    for i, t in enumerate(req.teammates):
        put(f"tm{i}.char", character_def(gd, t.id, variant_for(gd, t.id, t.ability_version)).toggles, "teammate")
        if t.light_cone and t.light_cone.id in registry.light_cones():
            put(f"tm{i}.lc", registry.light_cones()[t.light_cone.id].toggles, "teammate")
        for sid in (t.relic_set, t.planar_set):
            if sid and sid in registry.sets():
                put(f"tm{i}.set.{sid}", registry.sets()[sid].toggles, "teammate")
    return out


def optimize(assets, request, inventory) -> OptimizeResult:
    """The best six relics for the main character out of the inventory, with request.top_n alternatives."""
    from .search import search

    return search(assets, _request(request), _relics(inventory))
