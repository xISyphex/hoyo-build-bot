"""Definitions read from the ability texts, for characters, light cones and sets nobody has ported yet.

They reuse the text readers of the old score (bot/kit.py for abilities, bot/cone_effects.py for passives), so they
share their limits: buffs count as always active at full stacks, conditions and targets can be misread, hits are
the strongest one per ability. Everything built here has reviewed=False, which marks the result approximate.
"""

from __future__ import annotations

import re

from .. import cone_effects, kit
from .model import (ALL, Ability, Call, CharacterDef, Effect, Hit, LightConeDef, P, SetDef, Tag)

# cone_effects / kit bonus keys -> (stat, tags)
KEYS = {
    "CriticalChanceBase": ("cr", ALL), "CriticalDamageBase": ("cd", ALL), "AttackAddedRatio": ("atk%", ALL),
    "HPAddedRatio": ("hp%", ALL), "DefenceAddedRatio": ("def%", ALL), "SpeedAddedRatio": ("spd%", ALL),
    "BreakDamageAddedRatioBase": ("be", ALL), "ElationDamageAddedRatioBase": ("elation", ALL), "DMG": ("dmg", ALL),
    "DefIgnore": ("def_pen", ALL), "Vulnerability": ("vuln", ALL),
    "BreakDMG": ("dmg", Tag.BREAK | Tag.SUPER_BREAK), "BreakDefIgnore": ("def_pen", Tag.BREAK | Tag.SUPER_BREAK),
    "ElationDefIgnore": ("def_pen", Tag.ELATION), "StatusProbabilityBase": ("ehr", ALL),
    "StatusResistanceBase": ("res", ALL), "HealRatioBase": ("ohb", ALL), "SPRatioBase": ("err", ALL),
    "PhysicalAddedRatio": ("dmg_physical", ALL), "FireAddedRatio": ("dmg_fire", ALL), "IceAddedRatio": ("dmg_ice", ALL),
    "ThunderAddedRatio": ("dmg_lightning", ALL), "WindAddedRatio": ("dmg_wind", ALL),
    "QuantumAddedRatio": ("dmg_quantum", ALL), "ImaginaryAddedRatio": ("dmg_imaginary", ALL),
}
KIND_OF = {"Normal": "basic", "BPSkill": "skill", "Ultra": "ult", "Talent": "talent"}
TAG_OF = {"basic": Tag.BASIC, "skill": Tag.SKILL, "ult": Tag.ULT, "talent": Tag.FUA}
DPS_PATHS = ("Destruction", "Hunt", "Erudition", "Nihility", "Remembrance", "Elation")


def _effects_from(parse, source: str, keys) -> list[Effect]:
    out = []
    for key in keys:
        if key not in KEYS:
            continue
        stat, tags = KEYS[key]
        out.append(Effect(stat, Call(lambda ctx, k=key: parse(ctx).get(k, 0.0), f"read from text ({key})"),
                          "self", tags=tags, source=source))
    return out


def character(gd, cid: str, variant: int) -> CharacterDef:
    """Strongest hit of Basic ATK, Skill and Ultimate (and a Talent hit, as a follow-up), the self-buffs the text reader
    finds, and a plain rotation: Ultimate then three Skills for damage Paths, Basic ATK otherwise."""
    skills = gd.skills_of(cid, variant)
    abilities: dict[str, Ability] = {}
    effects: list[Effect] = []
    for sid, entry in skills.items():
        kind = KIND_OF.get(entry.get("type"))
        if not kind or kind in abilities and kind != "talent":
            continue
        desc = entry.get("desc", "")
        hits = []
        for match in kit.HIT.finditer(desc):
            index = int(match.group(1)) - 1
            stat = kit.STAT[match.group(2)]
            hits.append((index, stat))
        if hits:
            # the largest multiplier at max level stands for the ability (the main target's hit)
            top = gd.skill_params(sid, 10)
            index, stat = max(hits, key=lambda h: top[h[0]] if h[0] < len(top) else 0.0)
            key = "fua" if kind == "talent" else kind
            hit = Hit("crit", TAG_OF[kind], **{("def_" if stat == "def" else stat): P(kind, index, sid)},
                      label=entry.get("name", key))
            abilities.setdefault(key, Ability(key, [hit], name=entry.get("name", "")))
        params_fn = (lambda s, k: (lambda ctx: kit._buffs(gd.skill(s).get("desc", ""),
                                                          gd.skill_params(s, ctx.owner["levels"].get(k, 10) +
                                                                          ctx.owner["bumps"].get(s, 0)))))(sid, kind)
        sample = kit._buffs(desc, gd.skill_params(sid, 10))
        effects += _effects_from(params_fn, f"{entry.get('name', kind)} (read from text)", sample)
    for n, node in gd.major_traces(cid, variant).items():
        if not node.get("desc"):
            continue
        parse = (lambda nd, nn: (lambda ctx: kit._buffs(nd["desc"], [float(x) for x in (nd.get("params") or [[]])[0]])
                                 if ctx.has_trace(nn) else {}))(node, n)
        sample = kit._buffs(node["desc"], [float(x) for x in (node.get("params") or [[]])[0]])
        effects += _effects_from(parse, f"{node.get('name', 'Trace')} (read from text)", sample)
    path = gd.path(cid)
    for key in ("basic", "skill", "ult"):
        abilities.setdefault(key, Ability(key, []))
    if path in DPS_PATHS:
        rotation = ["ult", "skill", "skill", "skill"]
    else:
        rotation = ["basic"]
    if "fua" in abilities and path in DPS_PATHS:
        rotation.append("fua")
    notes = ["no reviewed definition: hits, buffs and rotation are read from the ability texts (approximate)."]
    if path == "Remembrance":
        notes.append("the memosprite is not modelled.")
    if path == "Elation":
        notes.append("Elation DMG is not modelled; hits count as ordinary DMG.")
    return CharacterDef(id=f"{cid}b1" if variant else cid, name=gd.name(cid), abilities=abilities, effects=effects,
                        rotation=rotation, reviewed=False, notes=notes)


def light_cone(gd, lid: str, rank: int) -> LightConeDef:
    entry = gd.cone(lid)
    desc = entry.get("desc", "")

    def parse(ctx):
        params = gd.cone_params(lid, ctx.cone_ref[1])
        always: dict[str, float] = {}
        rows = entry.get("properties") or []
        for prop in rows[min(ctx.cone_ref[1], len(rows)) - 1] if rows else []:
            always[prop["type"]] = always.get(prop["type"], 0.0) + float(prop["value"])
        if lid in cone_effects.CAPPED:
            return cone_effects.CAPPED[lid](params)
        return cone_effects.parse(desc, params, always)

    sample = cone_effects.effect(gd.assets, {"tid": lid, "rank": rank})
    effects = _effects_from(parse, "passive (read from text)", sample)
    return LightConeDef(id=lid, name=gd.cone_name(lid), effects=effects, reviewed=False,
                        notes=["no reviewed definition: the passive is read from its text, at full stacks (approximate)."])


NUMBER = re.compile(r"(\d+(?:\.\d+)?)%")


def _blanks(text: str) -> tuple[str, list[float]]:
    """Set texts carry literal numbers; turn "by 12%" into "by #1[i]%" so cone_effects.parse can read them."""
    params: list[float] = []

    def sub(m):
        params.append(float(m.group(1)) / 100)
        return f"#{len(params)}[i]%"

    return NUMBER.sub(sub, text), params


def relic_set(gd, sid: str) -> SetDef:
    planar = int(sid) >= 300
    pieces: dict[int, list[Effect]] = {}
    for n in ((2,) if planar else (2, 4)):
        text, params = _blanks(gd.set_text(sid, n))
        always = {}
        for k, v in gd.set_props(sid, n).items():
            for prop, (stat, _) in KEYS.items():
                if stat == k:
                    always[prop] = v
        found = cone_effects.parse(text, params, always) if text else {}
        if found:
            pieces[n] = _effects_from(lambda ctx, f=found: f, f"{n}pc (read from text)", found)
    return SetDef(id=sid, name=gd.set_name(sid), pieces=pieces, reviewed=False,
                  notes=["no reviewed definition: the bonus is read from its text, as always active (approximate)."])
