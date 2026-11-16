"""The session's characters and relics as JSON for the optimizer page."""

from __future__ import annotations

import hashlib

from .. import optimize
from ..assets import Assets
from ..games import starrail as sr
from ..models import CharacterBuild, Gear, Stat
from .meta import short
from .sessions import Session


def _stat(stat: Stat, sub: bool = False) -> dict:
    out = {"name": stat.name, "value": stat.value}
    if sub:
        out["rolls"] = stat.rolls
    return out


def info_of(build: CharacterBuild) -> dict:
    """The showcase-shaped entry of a build, without relics (HoYoLAB's characters carry one in bare)."""
    return build.bare or {k: v for k, v in build.raw.items() if k != "relicList"}


def relic_entry(gear: Gear, rid: str, owner: CharacterBuild, set_id: str | None) -> dict:
    return {"id": rid, "set_id": set_id, "set_name": gear.set_name, "slot": gear.slot, "rarity": gear.rarity,
            "level": gear.level, "main": _stat(gear.main), "subs": [_stat(s, True) for s in gear.subs],
            "icon": gear.piece_icon, "owner": owner.character_id, "owner_name": owner.name,
            "readable": bool(optimize.gear_props(gear))}


def inventory(assets: Assets, session: Session) -> tuple[list[dict], dict[int, str]]:
    """Every relic the session's characters wear, with an id that stays the same for the session, and a map from each
    Gear object to its id (for naming the pieces an optimize picked)."""
    if "relics" in session.cache:
        return session.cache["relics"], session.cache["ids"]
    id_of = optimize._id_of(optimize.set_ids(assets))
    relics, ids, seen = [], {}, set()
    for build in session.builds:
        for gear in build.gear:
            if gear.slot not in sr.SLOT_ORDER:
                continue
            text = "|".join([build.character_id, gear.slot, gear.set_name, str(gear.level), gear.main.name,
                             gear.main.value, *(f"{s.name}={s.value}" for s in gear.subs)])
            rid = "r" + hashlib.sha256(text.encode()).hexdigest()[:12]
            n = 1
            while rid in seen:  # two identical pieces on one character can't happen in game, but stay unique anyway
                n += 1
                rid = f"{rid[:13]}-{n}"
            seen.add(rid)
            ids[id(gear)] = rid
            relics.append(relic_entry(gear, rid, build, id_of(gear.set_name)))
    session.cache["relics"], session.cache["ids"] = relics, ids
    return relics, ids


def character_entry(build: CharacterBuild, ability_ids: set[str], trace_ids: set[str], relic_ids: list[str]) -> dict:
    info = info_of(build)
    abilities, traces = {}, []
    for point in info.get("skillTreeList") or []:
        pid = short(point.get("pointId", 0))
        if pid in ability_ids:
            abilities[pid] = int(point.get("level", 1))
        elif pid in trace_ids and int(point.get("level", 0)) > 0:
            traces.append(pid)
    eq = info.get("equipment")
    light_cone = None
    if eq:
        light_cone = {"id": str(eq.get("tid")), "name": build.weapon.name if build.weapon else None,
                      "level": int(eq.get("level", 1)), "rank": int(eq.get("rank", 1))}
    return {"id": build.character_id, "name": build.name, "level": build.level,
            "ascension": int(info.get("promotion", 0) or 0), "eidolon": build.constellation, "source": build.source,
            "abilities": abilities, "traces": traces, "light_cone": light_cone, "relics": relic_ids}


def session_payload(assets: Assets, session: Session, meta_cache) -> dict:
    relics, ids = inventory(assets, session)
    characters = []
    for build in session.builds:
        known = meta_cache.character(build.character_id) or {}
        ability_ids = {a["id"] for a in known.get("abilities", [])}
        trace_ids = {t["id"] for t in known.get("traces", [])}
        worn = [ids[id(g)] for g in build.gear if id(g) in ids]
        characters.append(character_entry(build, ability_ids, trace_ids, worn))
    return {"player": {"uid": session.uid}, "expires_at": int(session.expires), "preselect": session.preselect,
            "characters": characters, "relics": relics}
