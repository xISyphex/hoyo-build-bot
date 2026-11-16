# Ported in part from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/optimization/calculateStats.ts and src/lib/conditionals/conditionalFinalizers.ts (pipeline order, conversions),
# branch main as of 2026-11-16.
"""The evaluation pipeline: resolve every definition for one request, collect the effects that reach the main
character, and compute the rotation's damage for any number of relic combinations at once.

prepare(assets, request) does everything that doesn't depend on relics, once per request:

1. Resolve the main character, its light cone and each teammate (with their light cone and sets) against the game
   data at the chosen levels, eidolons, superimpositions and toggles.
2. Collect their effects and keep those whose target reaches the main character or its memosprite (model.Effect).
3. Split them into constants (resolved numbers), set-gated ones (the main character's own sets, which differ between
   relic combinations), and dynamic ones (conversions and stat conditions, evaluated per combination).
4. Resolve the hits of every ability in the rotation.

Prepared.score(relic_stats, set_counts) then evaluates any number of combinations as numpy arrays (one entry per
combination), and Prepared.explain(...) does the same for one build and returns the breakdown the website shows.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from . import formulas as F
from .gamedata import GameData, ascension_for
from .model import (ABILITY_KINDS, ALL, BASIC_STATS, DEFAULT_LEVELS, ELEMENTS, MAX_LEVELS, PERCENT, SLOTS, STAT_NAMES,
                    Ability, All, CharacterDef, Cond, Effect, Hit, LightConeDef, Scale, SetDef, StatAtLeast, StatBelow,
                    Tag, Toggle, Value, ashblazing_stacks, static_parts)

TURN_KEYS = ("basic", "skill")  # abilities that end the character's own turn unless an Ability says otherwise
ITERATIONS = 8  # rounds of the conversion / stat-condition fixpoint


class CalcError(Exception):
    """A request the engine can't evaluate; the message is safe to show to users."""


# ---------------------------------------------------------------------------------------------------------------
# Resolution contexts: what a Value or Cond of one definition reads.


@dataclass
class Team:
    main_id: str
    main_element: str
    main_has_memo: bool
    paths: list[str]  # path names of every team member, the main character first
    enemy_broken: bool = False


class Ctx:
    """Resolves the Values and Conds of one definition instance (a character, light cone or set of one owner)."""

    def __init__(self, gd: GameData, team: Team, role: str, owner: dict, toggles: dict[str, float], defs: list[Toggle],
                 cone: tuple[str, int] | None = None):
        self.gd, self.team, self.role, self.owner = gd, team, role, owner
        self._toggles = toggles
        self._defs = {t.id: t for t in defs}
        self.cone_ref = cone

    # values
    def ability_param(self, kind: str, index: int, sid: str | None) -> float:
        o = self.owner
        cid, variant = o["id"], o["variant"]
        if kind not in ABILITY_KINDS:
            raise CalcError(f"unknown ability kind {kind}")
        if sid is None:
            if kind not in SLOTS:
                raise CalcError(f"ability kind {kind} needs an explicit skill id")
            sid = ("1" if variant else "") + cid + SLOTS[kind]
        else:
            sid = sid.replace("{id}", cid).replace("{v}", "1" if variant else "")
        level = o["levels"].get(kind, DEFAULT_LEVELS[kind])
        bumps = o["bumps"]
        base_sid = sid[1:] if variant and sid.startswith("1" + cid) and len(sid) == len(cid) + 3 else sid
        level += bumps.get(sid, 0) if sid in bumps else bumps.get(base_sid, 0)
        params = self.gd.skill_params(sid, level)
        if not params:
            raise CalcError(f"no game data for skill {sid} of character {cid}")
        if index >= len(params):
            raise CalcError(f"skill {sid} has no param #{index + 1}")
        return params[index]

    def trace_param(self, n: int, index: int) -> float:
        if not self.has_trace(n):
            return 0.0
        node = self.owner["major"].get(n)
        rows = (node or {}).get("params") or []
        if not rows or index >= len(rows[0]):
            raise CalcError(f"trace {n} of character {self.owner['id']} has no param #{index + 1}")
        return float(rows[0][index])

    def cone_param(self, index: int) -> float:
        if not self.cone_ref:
            raise CalcError("light cone param outside a light cone")
        params = self.gd.cone_params(*self.cone_ref)
        if index >= len(params):
            raise CalcError(f"light cone {self.cone_ref[0]} has no param #{index + 1}")
        return params[index]

    def toggle(self, tid: str) -> float:
        if tid not in self._toggles:
            raise CalcError(f"unknown toggle {tid}")
        return self._toggles[tid]

    # conditions
    @property
    def eidolon(self) -> int:
        return self.owner["eidolon"]

    def has_trace(self, n: int) -> bool:
        return n in self.owner["traces"]

    def team_path_count(self, path: str) -> int:
        return sum(p == path for p in self.team.paths)

    @property
    def owner_element(self) -> str:
        return self.owner["element"]

    @property
    def main_element(self) -> str:
        return self.team.main_element

    @property
    def main_has_memo(self) -> bool:
        return self.team.main_has_memo

    @property
    def enemy_broken(self) -> bool:
        return self.team.enemy_broken


def resolve(v, ctx: Ctx):
    if v is None:
        return None
    if isinstance(v, Value):
        return v.resolve(ctx)
    return float(v)


def check(cond: Cond | None, ctx: Ctx) -> bool:
    return True if cond is None else cond.check(ctx)


# ---------------------------------------------------------------------------------------------------------------
# Resolved pieces


@dataclass
class RScale:
    src: str
    ratio: float
    above: float
    step: float | None
    cap: float | None
    convertible: bool

    def value(self, stats, conv):
        x = (conv if self.convertible else stats)[self.src] - self.above
        if self.step:
            v = self.ratio * np.floor(np.maximum(0.0, x) / self.step + 1e-9)
        else:
            v = self.ratio * np.maximum(0.0, x)
        return np.minimum(self.cap, v) if self.cap is not None else v


@dataclass
class REffect:
    stat: str
    value: float | None  # None: scale
    scale: RScale | None
    targets: frozenset  # {"self", "memo"}
    tags: Tag
    element: str | None
    actions: tuple | None
    conds: list  # dynamic conditions (StatAtLeast / StatBelow)
    set_req: tuple | None  # (set id, pieces) for the main character's own sets
    unconvertible: bool
    source: str
    owner: str
    target: str

    @property
    def action_level(self) -> bool:
        return self.tags == ALL and self.element is None and self.actions is None

    @property
    def dynamic(self) -> bool:
        return self.scale is not None or bool(self.conds)


@dataclass
class RHit:
    func: str
    tags: Tag
    element: str
    entity: str
    scale_entity: str
    atk: float = 0.0
    hp: float = 0.0
    def_: float = 0.0
    be_atk: float = 0.0
    be_cap: float | None = None
    elation_atk: float = 0.0
    toughness: float = 0.0
    fixed_toughness: float = 0.0
    tick: float = 1.0
    dot_chance: float = 1.0
    dot_split: float = 0.0
    dot_stacks: float = 1.0
    cr_override: float | None = None
    cd_override: float | None = None
    true_dmg: float = 0.0
    elation_scaling: float = 0.0
    punchline: float = 0.0
    min_elation: float = 0.0
    special: float = 1.0
    extra_super_break: float = 0.0
    src: str | None = None
    ratio: float = 0.0
    flat: float = 0.0
    above: float = 0.0
    step: float | None = None
    per: float = 0.0
    cap: float | None = None
    ashblazing: float = 0.0  # ATK% from Ashblazing Grand Duke 4pc stacks (when worn)
    label: str = ""


@dataclass
class Prepared:
    gd: GameData
    level: int
    element: str
    char: CharacterDef
    base: dict  # hp/atk/def/spd: character + light cone base
    basic_const: dict  # basic stats that don't depend on relics
    set_plain: list  # (set id, pieces, stat, value)
    effects: list  # REffect
    abilities: dict  # key -> list[RHit]
    pattern: Counter
    turns_in_pattern: float
    advance: float
    speed: bool
    cycles: int
    enemy: dict
    broken: bool
    memo: object
    level_mult: float
    notes: list
    approximate: bool
    buff_only: bool
    relevant: set = field(default_factory=set)
    ashblazing_set: str = "115"

    # -----------------------------------------------------------------------------------------------------------

    def _gate(self, e: REffect, counts) -> object:
        """1 where a set-gated effect is active, as an array (or 1.0 when it isn't gated)."""
        if e.set_req is None:
            return 1.0
        sid, n = e.set_req
        c = counts.get(sid)
        return 0.0 if c is None else (c >= n).astype(float)

    @staticmethod
    def _cond_mask(conds, stats):
        mask = 1.0
        for c in conds:
            if isinstance(c, StatAtLeast):
                mask = mask * (stats[c.stat] >= c.x - 1e-9)
            elif isinstance(c, StatBelow):
                mask = mask * (stats[c.stat] < c.x)
        return mask

    def _totals(self, acc: dict, base: dict) -> dict:
        s = dict(acc)
        s["hp"] = base["hp"] * (1 + acc["hp%"]) + acc["hp"]
        s["atk"] = base["atk"] * (1 + acc["atk%"]) + acc["atk"]
        s["def"] = base["def"] * (1 + acc["def%"]) + acc["def"]
        s["spd"] = base["spd"] * (1 + acc["spd%"]) + acc["spd"]
        return s

    def _evaluate(self, relic: dict, counts: dict, m: int, keep: bool = False):
        """The stats of every entity and the damage of every ability, for m combinations."""
        # Stats stay plain numbers until something relic-dependent is added, so most of them cost nothing per row.
        zero = 0.0
        acc = {k: self.basic_const.get(k, 0.0) for k in (*BASIC_STATS, *_COMBAT)}
        for k, v in relic.items():
            acc[k] = acc[k] + v
        for sid, n, stat, value in self.set_plain:
            c = counts.get(sid)
            if c is not None:
                acc[stat] = acc[stat] + value * (c >= n)
        basic = dict(acc)  # the character screen: base, traces, light cone, relics, set bonuses' plain stats
        basic_totals = self._totals(basic, self.base)
        final_mult = {"self": 1.0, "memo": 1.0}

        # constant combat effects for the main character, and the inputs of the dynamic ones
        unconv = {k: 0.0 for k in acc}
        dyn_self = [e for e in self.effects if e.dynamic and e.action_level and "self" in e.targets]
        for e in self.effects:
            if e.dynamic or not e.action_level or "self" not in e.targets:
                continue
            v = e.value * self._gate(e, counts)
            if e.stat == "final":
                final_mult["self"] = final_mult["self"] * (1 + v)
                continue
            acc[e.stat] = acc[e.stat] + v
            if e.unconvertible:
                unconv[e.stat] = unconv[e.stat] + v
        # conversions and stat conditions, to a fixpoint
        dyn_vals = [zero] * len(dyn_self)
        for _ in range(ITERATIONS):
            full = dict(acc)
            conv = dict(acc)
            for e, v in zip(dyn_self, dyn_vals):
                if e.stat == "final":
                    continue
                full[e.stat] = full[e.stat] + v
                if e.scale is None and not e.unconvertible:
                    conv[e.stat] = conv[e.stat] + v
            for k in conv:
                conv[k] = conv[k] - unconv[k]
            stats, conv_stats = self._totals(full, self.base), self._totals(conv, self.base)
            new = [self._dyn_value(e, stats, conv_stats, counts) for e in dyn_self]
            if all(np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(new, dyn_vals)):
                break
            dyn_vals = new
        acc_self = dict(acc)
        for e, v in zip(dyn_self, dyn_vals):
            if e.stat == "final":
                final_mult["self"] = final_mult["self"] * (1 + v)
            else:
                acc_self[e.stat] = acc_self[e.stat] + v
        stats_self = self._totals(acc_self, self.base)
        conv_self = dict(acc_self)
        for k in conv_self:
            conv_self[k] = conv_self[k] - unconv[k]
        conv_self = self._totals(conv_self, self.base)

        # every effect's value at this build (dynamic ones on the main character's final stats)
        values = []
        for e in self.effects:
            if e.dynamic:
                values.append(self._dyn_value(e, stats_self, conv_self, counts))
            else:
                values.append(e.value * self._gate(e, counts))
        entities = {"self": (acc_self, stats_self, self.base)}
        if self.memo is not None:
            mb = {
                "hp": self.memo.hp_scale * basic_totals["hp"] + self.memo.hp_flat,
                "atk": self.memo.atk_scale * basic_totals["atk"] + self.memo.atk_flat,
                "def": self.memo.def_scale * basic_totals["def"] + self.memo.def_flat,
                "spd": self.memo.spd_scale * basic_totals["spd"] + self.memo.spd_flat,
            }
            macc = {k: 0.0 for k in acc}
            for k in ("cr", "cd", "be", "ehr", "res", "err", "ohb", "elation", *(f"dmg_{x.lower()}" for x in ELEMENTS)):
                macc[k] = basic[k]
            for e, v in zip(self.effects, values):
                if "memo" in e.targets and e.action_level:
                    if e.stat == "final":
                        final_mult["memo"] = final_mult["memo"] * (1 + v)
                    else:
                        macc[e.stat] = macc[e.stat] + v
            entities["memo"] = (macc, self._totals(macc, mb), mb)

        c = counts.get(self.ashblazing_set)
        ash = 0.0 if c is None else (c >= 4).astype(float)
        damage = {}
        details = {} if keep else None
        for key, hits in self.abilities.items():
            total = zero
            for i, h in enumerate(hits):
                d, info = self._hit(h, key, entities, values, final_mult, ash, keep)
                total = total + d
                if keep:
                    details[(key, i)] = info
            damage[key] = total
        return stats_self, damage, values, details, entities

    def _dyn_value(self, e: REffect, stats, conv, counts):
        v = e.scale.value(stats, conv) if e.scale is not None else e.value
        if e.conds:
            v = v * self._cond_mask(e.conds, stats)
        return v * self._gate(e, counts)

    def _hit_stats(self, entity: str, h: RHit, key: str, entities, values, final_mult, ash):
        acc, stats, base = entities[entity]
        extra: dict = {}
        final = final_mult[entity]
        for e, v in zip(self.effects, values):
            if e.action_level or entity not in e.targets:
                continue
            if e.tags != ALL and not (e.tags & h.tags):
                continue
            if e.element is not None and e.element != h.element:
                continue
            if e.actions is not None and key not in e.actions:
                continue
            if e.stat == "final":
                final = final * (1 + v)
            else:
                extra[e.stat] = extra.get(e.stat, 0.0) + v
        if h.ashblazing and entity == "self":
            extra["atk%"] = extra.get("atk%", 0.0) + h.ashblazing * ash
        if not extra:
            return stats, final, {}
        a = dict(acc)
        for k, v in extra.items():
            a[k] = a[k] + v
        return self._totals(a, base), final, extra

    def _hit(self, h: RHit, key: str, entities, values, final_mult, ash, keep):
        if h.entity not in entities:
            return 0.0, None
        s, final, extra = self._hit_stats(h.entity, h, key, entities, values, final_mult, ash)
        sc = s if h.scale_entity == h.entity else self._hit_stats(h.scale_entity, h, key, entities, values, final_mult, ash)[0]
        if h.func == "buff":
            src = sc[h.src]
            if h.step:
                v = np.minimum(h.cap if h.cap is not None else np.inf,
                               np.floor(np.maximum(0.0, src - h.above) / h.step + 1e-9) * h.per)
            else:
                v = h.ratio * src + h.flat
            return v, ({"func": "buff", "label": h.label, "source_stat": h.src, "damage": v} if keep else None)
        enemy = self.enemy
        res = 0.0 if h.element in enemy["weak"] else enemy["res"]
        mult = F.common(self.level, enemy["level"], res, self.broken, s["def_pen"], s["res_pen"], s["vuln"],
                        final - 1, s["true"] + h.true_dmg)
        elem_dmg = s.get(f"dmg_{h.element.lower()}", 0.0)
        if h.func in ("crit", "additional"):
            base = self._base_dmg(h, sc)
            boost = s["dmg"] + elem_dmg
            cr = s["cr"] + s["cr_boost"] if h.cr_override is None else h.cr_override
            cd = s["cd"] + s["cd_boost"] if h.cd_override is None else h.cd_override
            d = F.crit_damage(base, boost, cr, cd, mult) * h.tick
        elif h.func == "dot":
            base = self._base_dmg(h, sc)
            boost = s["dmg"] + elem_dmg
            chance = F.dot_chance(h.dot_chance, s["ehr"], enemy["effect_res"], s["effect_res_pen"], h.dot_split, h.dot_stacks)
            d = F.dot_damage(base, boost, chance, mult, h.tick)
        elif h.func == "break":
            boost = extra.get("dmg", 0.0)  # only effects tagged for Break DMG (Fribbels: hit-level BOOST)
            d = F.break_damage(self.level_mult, h.element, enemy["toughness"], s["be"], boost, mult, h.special)
        elif h.func == "super_break":
            boost = extra.get("dmg", 0.0)
            modifier = s["super_break"] + h.extra_super_break
            d = F.super_break_damage(self.level_mult, h.toughness, s["break_eff"], h.fixed_toughness, s["be"],
                                     modifier, boost, mult)
        elif h.func == "elation":
            d = F.elation_damage(2 * self.level_mult if self.level != 80 else F.ELATION_BASE_80, h.elation_scaling,
                                 s["elation"], s["merrymaking"], h.punchline, s["cr"] + s["cr_boost"],
                                 s["cd"] + s["cd_boost"], mult, h.min_elation)
        else:  # pragma: no cover - validated in model
            raise CalcError(f"unknown hit function {h.func}")
        info = None
        if keep:
            info = {"func": h.func, "label": h.label, "tags": _tag_names(h.tags), "element": h.element,
                    "entity": h.entity, "damage": d,
                    "multipliers": {"def": F.def_multiplier(self.level, enemy["level"], s["def_pen"]),
                                    "res": F.res_multiplier(res, s["res_pen"]),
                                    "vuln": F.vuln_multiplier(s["vuln"]),
                                    "final": final, "broken": 1.0 if self.broken else 0.9,
                                    "true": 1 + s["true"] + h.true_dmg},
                    "stats": {k: s[k] for k in ("atk", "hp", "def", "cr", "cd", "be", "ehr", "dmg") if k in s}}
            if h.func in ("crit", "additional", "dot"):
                info["base"] = self._base_dmg(h, sc)
                info["multipliers"]["dmg_boost"] = 1 + s["dmg"] + elem_dmg
            if h.func in ("crit", "additional"):
                info["multipliers"]["crit"] = F.crit_multiplier(cr, cd)
        return d, info

    @staticmethod
    def _base_dmg(h: RHit, s):
        atk_mult = h.atk
        if h.be_atk:
            be = s["be"] if h.be_cap is None else np.minimum(h.be_cap, s["be"])
            atk_mult = atk_mult + h.be_atk * be
        if h.elation_atk:
            atk_mult = atk_mult + h.elation_atk * s["elation"]
        return atk_mult * s["atk"] + h.hp * s["hp"] + h.def_ * s["def"]

    # -----------------------------------------------------------------------------------------------------------

    def score(self, relic: dict, counts: dict, m: int):
        """Rotation damage (or buff size for supports) of m relic combinations."""
        stats, damage, _, _, _ = self._evaluate(relic, counts, m)
        total = self._total(stats, damage, counts)[0]
        return np.broadcast_to(np.asarray(total, dtype=float), (m,)), stats

    def _total(self, stats, damage, counts):
        if self.buff_only:
            return sum(damage[k] * c for k, c in self.pattern.items()), 1.0
        pattern = sum(damage[k] * c for k, c in self.pattern.items())
        if self.speed:
            turns = F.expected_turns(stats["spd"], self.cycles) * (1 + self.advance)
            reps = turns / self.turns_in_pattern
        else:
            reps = 1.0
        return pattern * reps, reps

    def explain(self, relic: dict, counts: dict) -> dict:
        """One build's total, per-ability damage, every counted effect and the final stats."""
        stats, damage, values, details, entities = self._evaluate(relic, counts, 1, keep=True)
        total, reps = self._total(stats, damage, counts)
        f = lambda x: float(np.asarray(x).reshape(-1)[0])
        abilities = []
        for key, count in self.pattern.items():
            hits = [{**{k: v for k, v in details[(key, i)].items() if k not in ("damage", "multipliers", "stats", "base")},
                     "damage": f(details[(key, i)]["damage"]),
                     **({"base": f(details[(key, i)]["base"])} if "base" in details[(key, i)] else {}),
                     "multipliers": {k: f(v) for k, v in details[(key, i)].get("multipliers", {}).items()}}
                    for i in range(len(self.abilities[key])) if details.get((key, i))]
            abilities.append({"key": key, "name": self.char.abilities[key].name or key, "per_use": f(damage[key]),
                              "uses": count * f(reps), "total": f(damage[key]) * count * f(reps), "hits": hits})
        effects = []
        for e, v in zip(self.effects, values):
            value = f(v)
            effects.append({"source": e.source, "owner": e.owner, "stat": e.stat, "stat_name": STAT_NAMES.get(e.stat, e.stat),
                            "value": value, "target": e.target, "reaches": sorted(e.targets),
                            "tags": _tag_names(e.tags), "element": e.element, "abilities": list(e.actions) if e.actions else None,
                            "conditional": e.dynamic or e.set_req is not None, "active": abs(value) > 1e-12})
        shown = ("hp", "atk", "def", "spd", "cr", "cd", "be", "ehr", "res", "err", "ohb", "elation", "dmg",
                 f"dmg_{self.element.lower()}", "vuln", "def_pen", "res_pen", "break_eff", "super_break")
        final_stats = {k: f(stats[k]) for k in shown}
        memo_stats = None
        if "memo" in entities:
            memo_stats = {k: f(entities["memo"][1][k]) for k in shown}
        return {"total": f(total), "repetitions": f(reps), "abilities": abilities, "effects": effects,
                "stats": final_stats, "memo_stats": memo_stats}


_COMBAT = ("vuln", "def_pen", "res_pen", "final", "true", "cr_boost", "cd_boost", "break_eff", "super_break",
           "merrymaking", "effect_res_pen", "dmg_red")


def _tag_names(tags: Tag) -> list[str]:
    if tags == ALL:
        return ["ALL"]
    return [t.name for t in Tag if t.value and t in tags and t.name]


# ---------------------------------------------------------------------------------------------------------------
# Targets


def reaches(target: str, role: str, as_teammate: str, has_memo: bool) -> frozenset:
    if role == "main" and as_teammate == "teammate_only":
        return frozenset()
    if role == "teammate" and as_teammate == "main_only":
        return frozenset()
    if role == "main":
        out = {"self": {"self"}, "memo": {"memo"}, "self+memo": {"self", "memo"}, "team": {"self", "memo"},
               "enemy": {"self", "memo"}}.get(target, set())
    else:
        out = {"team": {"self", "memo"}, "enemy": {"self", "memo"}, "ally": {"self"}, "ally+memo": {"self", "memo"},
               "ally_memo": {"memo"}}.get(target, set())
    if not has_memo:
        out = out - {"memo"}
    return frozenset(out)


def resolve_effect(e: Effect, ctx: Ctx, role: str, owner_label: str, has_memo: bool,
                   set_req: tuple | None = None) -> REffect | None:
    targets = reaches(e.target, role, e.as_teammate, has_memo)
    if not targets:
        return None
    static, dynamic = static_parts(e.when)
    if not all(c.check(ctx) for c in static):
        return None
    scale = None
    value = None
    if isinstance(e.value, Scale):
        s = e.value
        scale = RScale(s.src, resolve(s.ratio, ctx), resolve(s.above, ctx), resolve(s.step, ctx), resolve(s.cap, ctx),
                       s.convertible)
    else:
        value = resolve(e.value, ctx)
        if value == 0 and not dynamic:
            return None
    for c in dynamic:
        if not isinstance(c, (StatAtLeast, StatBelow)):
            raise CalcError("only StatAtLeast / StatBelow conditions can depend on stats")
    return REffect(e.stat, value, scale, targets, e.tags, e.element, e.actions, dynamic, set_req, e.unconvertible,
                   e.source, owner_label, e.target)


def resolve_hit(h: Hit, ctx: Ctx, element: str, key: str) -> RHit | None:
    if not check(h.when, ctx):
        return None
    r = lambda v: resolve(v, ctx)
    entity = h.entity
    return RHit(func=h.func, tags=h.tags, element=h.element or element, entity=entity, scale_entity=h.scale or entity,
                atk=r(h.atk), hp=r(h.hp), def_=r(h.def_), be_atk=r(h.be_atk), be_cap=h.be_cap,
                elation_atk=r(h.elation_atk), toughness=r(h.toughness), fixed_toughness=r(h.fixed_toughness),
                tick=r(h.tick), dot_chance=r(h.dot_chance), dot_split=h.dot_split, dot_stacks=h.dot_stacks,
                cr_override=r(h.cr_override), cd_override=r(h.cd_override), true_dmg=r(h.true_dmg),
                elation_scaling=r(h.elation_scaling), punchline=r(h.punchline), min_elation=h.min_elation,
                special=r(h.special), extra_super_break=r(h.extra_super_break), src=h.src, ratio=r(h.ratio),
                flat=r(h.flat), above=h.above, step=h.step, per=r(h.per), cap=h.cap, label=h.label or key)


def owner_info(gd: GameData, cid: str, variant: int, eidolon: int, levels: dict, traces: set[int]) -> dict:
    return {"id": cid, "variant": variant, "eidolon": eidolon, "levels": levels, "traces": traces,
            "bumps": gd.eidolon_bumps(cid, eidolon), "major": gd.major_traces(cid, variant),
            "element": gd.element(cid), "path": gd.path(cid)}


def toggle_values(defs: list[Toggle], role: str, overrides: dict[str, float], prefix: str) -> dict[str, float]:
    """Defaults (main or teammate), then the request's overrides "<prefix>.<toggle id>"."""
    out = {}
    for t in defs:
        out[t.id] = t.teammate_default if role == "teammate" and t.teammate_default is not None else t.default
    for key, value in overrides.items():
        if key.startswith(prefix + "."):
            tid = key[len(prefix) + 1:]
            if tid not in out:
                raise CalcError(f"unknown toggle {key}")
            t = next(t for t in defs if t.id == tid)
            if not (t.min - 1e-9 <= value <= t.max + 1e-9):
                raise CalcError(f"toggle {key} must be between {t.min:g} and {t.max:g}")
            out[tid] = float(value)
    return out
