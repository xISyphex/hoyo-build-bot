"""Runs an optimize request from the page on the existing search (bot/optimize.py).

That search knows the character, the two sets, Speed and the excluded characters. It scores the character fully built
(Lv. 80, every trace, abilities at their cap) with the eidolons they own, and picks the light cone itself among the
ones of their Path worn on the account. Everything else the page sends is checked (bot/web/schema.py) and listed back
under "ignored" until the new damage engine reads it.
"""

from __future__ import annotations

import asyncio

from .. import optimize
from ..games import starrail as sr
from ..models import CharacterBuild
from .inventory import inventory, relic_entry
from .sessions import Session

ASSUMED = ("Scored fully built: Lv. 80, every trace, abilities at their cap, with the eidolons the account has (none for "
           "a character it doesn't have). The light cone is the best of the character's Path worn on the account. Set "
           "and light cone effects count at full stacks; team buffs don't count yet.")


class EngineError(Exception):
    """A request that is valid but can't be run (no recommended set, no pieces of a set...). Safe to show."""


def _plain(text: str) -> str:
    return text.replace("**", "")


def target_build(ctx, session: Session, cid: str, name: str) -> CharacterBuild | None:
    """The character as the search wants them: the account's own, the beta's, or one they don't have (fully built,
    no eidolons)."""
    owned = next((b for b in session.builds if b.character_id == cid), None)
    if owned is not None:
        return owned
    if ctx.unreleased is not None and (beta := ctx.unreleased.build(ctx.assets, "hsr", name)) is not None:
        return beta
    if cid not in ctx.assets.data.get("hsr_meta", {}).get("avatar", {}):
        return None
    raw = sr.maxed(ctx.assets, {"avatarId": int(cid), "rank": 0, "skillTreeList": []})
    build = sr.parse_character(ctx.assets, raw)
    build.raw, build.source = raw, "unowned"
    return build


def _set_choice(ctx, cid: str, given: str | None, planar: bool) -> tuple[str, str]:
    names = {sid: s.get("name") for sid, s in ctx.assets.data.get("srr_relic_sets", {}).items()}
    if given is None:
        given = next((str(i) for i in ctx.effective.recommended_sets(cid, planar) if names.get(str(i))), None)
        if given is None:
            kind = "planar" if planar else "relic"
            raise EngineError(f"The game recommends no {kind} set for this character that I know of. Pick a {kind} set.")
    return given, names[given]


def ignored_fields(config: dict) -> list[str]:
    fields = [f"character.{key}" for key in config["character"]["given"]]
    if config["teammates"]:
        fields.append("teammates")
    return fields


async def run(ctx, session: Session, config: dict, character_name: str) -> dict:
    main = config["character"]
    options = config["options"]
    cid = main["id"]
    target = target_build(ctx, session, cid, character_name)
    if target is None:
        raise EngineError(f"I can't work out {character_name}'s stats: the game data has no base stats for them yet.")
    relic_id, relic_name = _set_choice(ctx, cid, options["relic_set"], False)
    planar_id, planar_name = _set_choice(ctx, cid, options["planar_set"], True)
    owned = {b.character_id: b.name for b in session.builds}
    unknown = [c for c in options["exclude"] if c not in owned]
    if unknown:
        raise EngineError("Only the account's own characters can be excluded.")
    excluded = {owned[c] for c in options["exclude"]}
    wanted = optimize.with_speed(ctx.effective.wanted(target), options["speed"])
    try:
        result = await asyncio.to_thread(optimize.optimize, ctx.assets, target, session.builds, relic_name, planar_name,
                                         wanted, excluded)
    except optimize.OptimizeError as exc:
        raise EngineError(_plain(str(exc))) from None
    _, ids = inventory(ctx.assets, session)
    by_name = {b.name: b for b in session.builds}
    relics = []
    for piece in result.pieces:
        rid = ids.get(id(piece.gear))
        owner = by_name.get(piece.owner) or target
        relics.append(relic_entry(piece.gear, rid, owner, relic_id if piece.gear.slot in optimize.RELIC_SLOTS else planar_id))
    weapon = result.build.weapon
    return {
        "character": {"id": cid, "name": result.build.name, "source": target.source},
        "relic_set": {"id": relic_id, "name": relic_name},
        "planar_set": {"id": planar_id, "name": planar_name},
        "relics": relics,
        "light_cone": {"name": weapon.name, "level": weapon.level, "rank": weapon.refinement,
                       "owner_name": result.cone_owner} if weapon else None,
        "stats": [{"name": s.name, "value": s.value} for s in result.build.stats],
        "score": result.index,
        "current_score": result.current,
        "score_gain": result.build.score_gain,
        "counted": result.counted,
        "tried": result.tried,
        "light_cones_tried": result.cones,
        "excluded": sorted(options["exclude"]),
        "ignored": ignored_fields(config),
        "assumed": ASSUMED,
    }
