"""prepare(): turns a request into an engine.Prepared (everything that doesn't depend on the relics)."""

from __future__ import annotations

from collections import Counter

from . import fallback, formulas as F, registry
from .engine import (TURN_KEYS, CalcError, Ctx, Prepared, RHit, Team, owner_info, resolve, resolve_effect, resolve_hit,
                     toggle_values)
from .gamedata import GameData, ascension_for
from .model import (ABILITY_KINDS, DEFAULT_LEVELS, DIRECT, MAX_LEVELS, CharacterDef, Tag, ashblazing_stacks)

ASHBLAZING = "115"
TRACE_KEYS = {"ability_1": 1, "ability_2": 2, "ability_3": 3}

# Simplifications every result shares; shown with each evaluation.
MODEL_NOTES = [
    "Rotation: Fribbels' default combo for the character, repeated as often as the character acts in Memory of Chaos "
    "(average of clears in 1 to 5 cycles); damage per own turn is the combo's damage divided by its Basic ATK/Skill "
    "count. No energy model: Ultimates come as often as the combo has them.",
    "Buffs are counted with their default uptime (Fribbels' 'simple' mode): a buff that lasts some turns counts on "
    "every action of the combo.",
    "Teammates' own stats (Robin's ATK, Sunday's CRIT DMG, ...) are inputs with Fribbels' defaults, not simulated.",
]


def variant_for(gd: GameData, cid: str, ability_version: int | None) -> int:
    """The kit version: the request's (an export's ability_version), else the reworked kit when the game data has one."""
    if ability_version is not None:
        return 1 if ability_version and gd.has_variant(cid) else 0
    return 1 if gd.has_variant(cid) else 0


def character_def(gd: GameData, cid: str, variant: int) -> CharacterDef:
    key = f"{cid}b1" if variant else cid
    found = registry.characters().get(key)
    if found:
        return found
    return fallback.character(gd, cid, variant)


def parse_levels(abilities: dict | None) -> dict[str, int]:
    levels = dict(DEFAULT_LEVELS)
    for kind, level in (abilities or {}).items():
        if kind not in ABILITY_KINDS:
            raise CalcError(f"unknown ability {kind}; use one of {', '.join(ABILITY_KINDS)}")
        cap = DEFAULT_LEVELS[kind]
        if not isinstance(level, int) or not 1 <= level <= cap:
            raise CalcError(f"{kind} level must be a whole number from 1 to {cap} (before eidolon bonuses)")
        levels[kind] = level
    return levels


def parse_traces(gd: GameData, cid: str, variant: int, traces: dict | None) -> tuple[set[int], list[int]]:
    """(major traces 1-3, stat nodes 1-10) the request unlocks; None unlocks all."""
    nodes = sorted(gd.stat_nodes(cid, variant))
    if traces is None:
        return {1, 2, 3}, nodes
    major, stats = set(), []
    for key, on in traces.items():
        if key in TRACE_KEYS:
            if on:
                major.add(TRACE_KEYS[key])
        elif key.startswith("stat_") and key[5:].isdigit() and 1 <= int(key[5:]) <= 10:
            if on and int(key[5:]) in nodes:
                stats.append(int(key[5:]))
        elif key in ("special", "elation_debt"):
            continue
        else:
            raise CalcError(f"unknown trace {key}")
    return major, stats


def prepare(assets, req, set_ids=()) -> Prepared:
    """req is an api.EvaluateRequest. set_ids: the sets the main character may wear (their effects are gated on the
    relic combination)."""
    gd = GameData(assets)
    main = req.character
    cid = str(main.id)
    if not gd.exists(cid):
        raise CalcError(f"unknown character {cid}")
    variant = variant_for(gd, cid, main.ability_version)
    char = character_def(gd, cid, variant)
    notes = list(MODEL_NOTES)
    approximate = not char.reviewed
    notes += [f"{char.name}: {n}" for n in char.notes]

    level = main.level
    ascension = main.ascension if main.ascension is not None else ascension_for(level)
    levels = parse_levels(main.abilities)
    major, stat_nodes = parse_traces(gd, cid, variant, main.traces)
    element = gd.element(cid)

    teammates = []
    for i, tm in enumerate(req.teammates):
        tid = str(tm.id)
        if not gd.exists(tid):
            raise CalcError(f"unknown teammate {tid}")
        if tid == cid:
            raise CalcError("a teammate can't be the main character")
        tvar = variant_for(gd, tid, tm.ability_version)
        teammates.append((i, tm, tid, tvar, character_def(gd, tid, tvar)))
    if len({t[2] for t in teammates}) != len(teammates):
        raise CalcError("the same teammate is listed twice")

    team = Team(cid, element, char.memo is not None, [gd.path(cid)] + [gd.path(t[2]) for t in teammates])
    overrides = dict(req.toggles or {})
    _check_toggle_keys(overrides, len(teammates))
    has_memo = char.memo is not None

    main_owner = owner_info(gd, cid, variant, main.eidolon, levels, major)
    main_ctx = Ctx(gd, team, "main", main_owner, toggle_values(char.toggles, "main", overrides, "main.char"), char.toggles)
    team.enemy_broken = bool(req.enemy.broken) or (char.broken_when is not None and char.broken_when.check(main_ctx))
    if char.broken_when is not None and team.enemy_broken and not req.enemy.broken:
        notes.append(f"{char.name}'s default mode counts the enemy as Weakness Broken (no 0.9 Toughness multiplier).")

    effects = []
    label = char.name

    def add(defn_effects, ctx, role, owner_label, set_req=None):
        for e in defn_effects:
            r = resolve_effect(e, ctx, role, owner_label, has_memo, set_req)
            if r is not None:
                effects.append(r)

    add(char.effects, main_ctx, "main", label)

    # base stats
    base = gd.base_stats(cid, level, ascension)
    basic_const = {"cr": base.pop("cr"), "cd": base.pop("cd")}
    for n in stat_nodes:
        for k, v in gd.stat_nodes(cid, variant)[n].items():
            basic_const[k] = basic_const.get(k, 0.0) + v

    # main light cone
    lc = main.light_cone
    if lc is not None:
        lid = str(lc.id)
        if not gd.cone_exists(lid):
            raise CalcError(f"unknown light cone {lid}")
        lc_asc = lc.ascension if lc.ascension is not None else ascension_for(lc.level)
        for k, v in gd.cone_base(lid, lc.level, lc_asc).items():
            base[k] += v
        if gd.cone_path(lid) == gd.path(cid):
            for k, v in gd.cone_props(lid, lc.rank).items():
                basic_const[k] = basic_const.get(k, 0.0) + v
            cone = registry.light_cones().get(lid) or fallback.light_cone(gd, lid, lc.rank)
            if not cone.reviewed:
                approximate = True
            notes += [f"{cone.name}: {n}" for n in cone.notes]
            ctx = Ctx(gd, team, "main", main_owner, toggle_values(cone.toggles, "main", overrides, "main.lc"),
                      cone.toggles, (lid, lc.rank))
            add(cone.effects, ctx, "main", cone.name)
        else:
            notes.append(f"{gd.cone_name(lid)} is not of {gd.name(cid)}'s Path: only its base stats count.")

    # teammates
    advance = 0.0
    team_sets: dict[str, int] = {}
    for i, tm, tid, tvar, tdef in teammates:
        tname = tdef.name
        towner = owner_info(gd, tid, tvar, tm.eidolon, dict(DEFAULT_LEVELS), {1, 2, 3})
        prefix = f"tm{i}"
        if not tdef.reviewed:
            notes.append(f"{tname} has no reviewed definition: their buffs to the team are not counted.")
            approximate = True
        else:
            ctx = Ctx(gd, team, "teammate", towner, toggle_values(tdef.toggles, "teammate", overrides, f"{prefix}.char"),
                      tdef.toggles)
            add(tdef.effects, ctx, "teammate", tname)
            share = resolve(tdef.advance, ctx)
            follows = tm.follows_carry if tm.follows_carry is not None else share > 0
            if follows and share > 0:
                advance += share
                notes.append(f"{tname} advances {gd.name(cid)}: counted as {share:.0%} more turns (follows-carry "
                             "model, assumes {tname} is fast enough to act after every turn of the carry).".replace("{tname}", tname))
        if tm.light_cone is not None:
            tlid = str(tm.light_cone.id)
            if not gd.cone_exists(tlid):
                raise CalcError(f"unknown light cone {tlid}")
            if gd.cone_path(tlid) == gd.path(tid):
                tcone = registry.light_cones().get(tlid)
                if tcone is None:
                    notes.append(f"{gd.cone_name(tlid)} (on {tname}) has no reviewed definition: its team effects are not counted.")
                    approximate = True
                else:
                    ctx = Ctx(gd, team, "teammate", towner,
                              toggle_values(tcone.toggles, "teammate", overrides, f"{prefix}.lc"), tcone.toggles,
                              (tlid, tm.light_cone.rank))
                    add(tcone.effects, ctx, "teammate", f"{tcone.name} ({tname})")
        for sid, need in ((tm.relic_set, 4), (tm.planar_set, 2)):
            if not sid:
                continue
            sid = str(sid)
            if not gd.set_exists(sid):
                raise CalcError(f"unknown set {sid}")
            if (int(sid) >= 300) != (need == 2):
                raise CalcError(f"set {sid} is not a {'planar' if need == 2 else 'relic'} set")
            sdef = registry.sets().get(sid)
            if sdef is None:
                notes.append(f"{gd.set_name(sid)} (on {tname}) has no reviewed definition: its team effect is not counted.")
                approximate = True
                continue
            if not sdef.team:
                continue
            if sdef.nonstackable and sid in team_sets:
                continue
            team_sets[sid] = team_sets.get(sid, 0) + 1
            ctx = Ctx(gd, team, "teammate", towner,
                      toggle_values(sdef.toggles, "teammate", overrides, f"{prefix}.set.{sid}"), sdef.toggles)
            add(sdef.team, ctx, "teammate", f"{sdef.name} ({tname})")

    # the main character's own sets: effects gated on the relic combination
    set_plain = []
    for sid in sorted({str(s) for s in set_ids}, key=int):
        if not gd.set_exists(sid):
            raise CalcError(f"unknown set {sid}")
        planar = int(sid) >= 300
        for n in ((2,) if planar else (2, 4)):
            for k, v in gd.set_props(sid, n).items():
                set_plain.append((sid, n, k, v))
        sdef = registry.sets().get(sid) or fallback.relic_set(gd, sid)
        ctx = Ctx(gd, team, "main", main_owner, toggle_values(sdef.toggles, "main", overrides, f"main.set.{sid}"), sdef.toggles)
        for n, effs in sdef.pieces.items():
            kept = effs
            if sdef.nonstackable and sid in team_sets:
                kept = [e for e in effs if e.target not in ("team",)]
            before = len(effects)
            add(kept, ctx, "main", sdef.name, (sid, n))
            if not sdef.reviewed and len(effects) > before:
                notes.append(f"{sdef.name}: effect read from the set's text (approximate).")
                approximate = True

    # abilities in the rotation
    abilities = {}
    for key in dict.fromkeys(char.rotation):
        ab = char.abilities[key]
        hits = [h for h in (resolve_hit(h, main_ctx, element, key) for h in ab.hits) if h is not None]
        if ab.ashblazing:
            stacks = ashblazing_stacks(ab.ashblazing, req.enemy.count)
            for h in hits:
                if h.tags & Tag.FUA:
                    h.ashblazing = stacks
        abilities[key] = hits
    has_super = any(h.func == "super_break" for hs in abilities.values() for h in hs)
    if not has_super and any(e.stat == "super_break" for e in effects):
        for key, hits in abilities.items():
            for h in list(hits):
                if h.func in ("crit", "additional") and h.toughness > 0 and h.tags & DIRECT:
                    hits.append(RHit(func="super_break", tags=Tag.SUPER_BREAK, element=h.element, entity=h.entity,
                                     scale_entity=h.entity, toughness=h.toughness, fixed_toughness=h.fixed_toughness,
                                     label=f"{h.label} (Super Break)"))
    funcs = {h.func for hs in abilities.values() for h in hs}
    level_mult, exact = F.level_multiplier(level)
    if not exact and funcs & {"break", "super_break", "elation"}:
        approximate = True
        notes.append(f"Break, Super Break and Elation DMG use an unverified level multiplier at Lv. {level} "
                     "(only Lv. 80 is verified).")
    buff_only = bool(funcs) and funcs == {"buff"}
    if not char.rotation:
        notes.append(f"{char.name} has no damage rotation to score.")
    elif buff_only:
        notes.append(f"{char.name} is scored by the size of their main buff to the team (Fribbels' support score), "
                     "not by damage; Speed is not counted.")

    turns = 0.0
    for key in char.rotation:
        ab = char.abilities[key]
        if ab.turn if ab.turn is not None else key in TURN_KEYS:
            turns += 1
    if not turns and char.rotation and not buff_only:
        turns = 1.0
        notes.append(f"{char.name}'s combo has no Basic ATK or Skill; it counts as one turn.")

    enemy = req.enemy
    weak = set(enemy.weaknesses or ([element] if enemy.weak else []))
    prepared = Prepared(gd=gd, level=level, element=element, char=char, base=base, basic_const=basic_const,
                        set_plain=set_plain, effects=effects, abilities=abilities, pattern=Counter(char.rotation),
                        turns_in_pattern=turns or 1.0, advance=advance, speed=bool(req.speed), cycles=req.cycles,
                        enemy={"level": enemy.level, "count": enemy.count, "res": enemy.resistance, "weak": weak,
                               "effect_res": enemy.effect_res, "toughness": enemy.toughness},
                        broken=team.enemy_broken, memo=char.memo, level_mult=level_mult, notes=notes,
                        approximate=approximate, buff_only=buff_only, ashblazing_set=ASHBLAZING)
    prepared.relevant = relevant_stats(prepared)
    return prepared


def relevant_stats(p: Prepared) -> set[str]:
    """The relic stats that can change the result (for the search's dominance filter and gradient)."""
    out: set[str] = set()
    scaling = set()
    for hits in p.abilities.values():
        for h in hits:
            if h.func == "buff":
                scaling.add(h.src)
                continue
            if h.atk or h.be_atk or h.elation_atk:
                scaling.add("atk")
            if h.hp:
                scaling.add("hp")
            if h.def_:
                scaling.add("def")
            if h.be_atk or h.func in ("break", "super_break"):
                out.add("be")
            if h.elation_atk or h.func == "elation":
                out.add("elation")
            if h.func in ("crit", "additional", "elation"):
                if h.cr_override is None:
                    out.add("cr")
                if h.cd_override is None:
                    out.add("cd")
            if h.func == "dot":
                out.add("ehr")
            if h.func in ("crit", "additional", "dot"):
                out.add(f"dmg_{h.element.lower()}")
                out.add("dmg")
    for e in p.effects:
        for c in e.conds:
            scaling.add(c.stat)
        if e.scale is not None:
            scaling.add(e.scale.src)
    if p.speed and not p.buff_only:
        scaling.add("spd")
    if p.memo is not None:
        scaling |= {"atk", "hp", "def"}
    for s in scaling:
        if s in ("atk", "hp", "def", "spd"):
            out |= {s, f"{s}%"}
        else:
            out.add(s)
    return out


def _check_toggle_keys(overrides: dict, n_teammates: int) -> None:
    for key, value in overrides.items():
        parts = key.split(".")
        ok = len(parts) >= 3 and (parts[0] == "main" or (parts[0][:2] == "tm" and parts[0][2:].isdigit()
                                                          and int(parts[0][2:]) < n_teammates))
        ok = ok and parts[1] in ("char", "lc", "set")
        if not ok:
            raise CalcError(f"bad toggle key {key}: use main.char.<id>, main.lc.<id>, main.set.<set id>.<id>, "
                            "or tm<n>.char|lc|set...")
        if isinstance(value, bool):
            overrides[key] = 1.0 if value else 0.0
        elif not isinstance(value, (int, float)):
            raise CalcError(f"toggle {key} must be a number or true/false")
