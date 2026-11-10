"""What-if builds: one character wearing another character's weapon and gear (/hsr Moze Feixiao).

Star Rail and ZZZ stats are computed from the raw showcase entry, so the wearer's entry is simply given the donor's
light cone and relics (W-Engine and discs) and read again. Genshin's showcase sends finished stats instead, so the
wearer's own weapon, artifacts and 2-piece set stats are taken off them and the donor's put on.
"""

from __future__ import annotations

import dataclasses

from .assets import Assets
from .games import genshin, starrail, zenless
from .models import CharacterBuild

# What each game moves from the donor to the wearer, in the showcase entry.
GEAR_KEYS = {"hsr": ("equipment", "relicList"), "zzz": ("Weapon", "EquippedList")}
GEAR_WORDS = {"genshin": "weapon and artifacts", "hsr": "light cone and relics", "zzz": "W-Engine and Drive Discs"}

# Genshin fightPropMap keys of the stats gear can give.
GI_KEYS = {
    "FIGHT_PROP_BASE_HP": "1", "FIGHT_PROP_HP": "2", "FIGHT_PROP_HP_PERCENT": "3",
    "FIGHT_PROP_BASE_ATTACK": "4", "FIGHT_PROP_ATTACK": "5", "FIGHT_PROP_ATTACK_PERCENT": "6",
    "FIGHT_PROP_BASE_DEFENSE": "7", "FIGHT_PROP_DEFENSE": "8", "FIGHT_PROP_DEFENSE_PERCENT": "9",
    "FIGHT_PROP_CRITICAL": "20", "FIGHT_PROP_CRITICAL_HURT": "22", "FIGHT_PROP_CHARGE_EFFICIENCY": "23",
    "FIGHT_PROP_HEAL_ADD": "26", "FIGHT_PROP_ELEMENT_MASTERY": "28", "FIGHT_PROP_PHYSICAL_ADD_HURT": "30",
    "FIGHT_PROP_FIRE_ADD_HURT": "40", "FIGHT_PROP_ELEC_ADD_HURT": "41", "FIGHT_PROP_WATER_ADD_HURT": "42",
    "FIGHT_PROP_GRASS_ADD_HURT": "43", "FIGHT_PROP_WIND_ADD_HURT": "44", "FIGHT_PROP_ROCK_ADD_HURT": "45",
    "FIGHT_PROP_ICE_ADD_HURT": "46",
}
# Flat stats come as they are; every other stat comes as a percentage (31.1) and is kept as a share (0.311).
GI_FLAT = {"1", "2", "4", "5", "7", "8", "28"}


def can_borrow(build: CharacterBuild) -> bool:
    """Characters read from the in-game showcase carry the raw entry needed. Star Rail characters from HoYoLAB work
    too, as long as HoYoLAB shares their relic stats (it does for the player's own linked account)."""
    if build.raw:
        return True
    return build.game == "hsr" and bool(build.bare) and (not build.gear or any(g.subs for g in build.gear))


def _hsr_from_cards(assets: Assets, wearer: CharacterBuild, donor: CharacterBuild) -> CharacterBuild:
    """Star Rail when one of the two comes from HoYoLAB, which has no showcase entry to re-read: the wearer's own
    numbers (level, traces, eidolons) with the donor's light cone, and the donor's relics added from their card lines."""
    from . import optimize

    own = wearer.raw or wearer.bare
    info = {k: v for k, v in own.items() if k not in GEAR_KEYS["hsr"]}
    cone = (donor.raw or donor.bare).get("equipment")
    if cone:
        info["equipment"] = cone
    bare = starrail.parse_character(assets, info)
    id_of = optimize._id_of(optimize.set_ids(assets))
    sets: dict[str, int] = {}
    for piece in donor.gear:
        if set_id := id_of(piece.set_name):
            sets[set_id] = sets.get(set_id, 0) + 1
    bonus = optimize.Scorer(assets, bare.calc, None).bonus([optimize.gear_props(g) for g in donor.gear], sets)
    build = dataclasses.replace(
        bare, gear=list(donor.gear), stats=starrail.stat_lines(bare.calc, bonus), set_bonuses=list(donor.set_bonuses),
        weapon=donor.weapon if cone else None, art_url=wearer.art_url, icon_url=wearer.icon_url,
        outfit_icon=wearer.outfit_icon, talents=wearer.talents or bare.talents)
    build.bare = info
    return build


def borrow(assets: Assets, wearer: CharacterBuild, donor: CharacterBuild) -> CharacterBuild:
    """The wearer as they'd be with the donor's weapon and gear."""
    if wearer.game == "hsr" and not (wearer.raw and donor.raw):
        build = _hsr_from_cards(assets, wearer, donor)
        build.source = wearer.source
        build.borrowed_from = donor.name
        return build
    if wearer.game == "genshin":
        info = _genshin_info(assets, wearer.raw, donor.raw)
        build = genshin.parse_character(assets, info)
    else:
        info = {k: v for k, v in wearer.raw.items() if k not in GEAR_KEYS[wearer.game]}
        info.update({k: donor.raw[k] for k in GEAR_KEYS[wearer.game] if k in donor.raw})
        build = (starrail if wearer.game == "hsr" else zenless).parse_character(assets, info)
    build.raw = info
    build.source = wearer.source
    build.borrowed_from = donor.name
    return build


def _gi_gear(assets: Assets, equip: list[dict]) -> dict[str, float]:
    """The stats a Genshin weapon and artifacts add up to, as fightPropMap keys."""
    total: dict[str, float] = {}

    def add(prop: str | None, value: float, percent: bool = True) -> None:
        key = GI_KEYS.get(prop or "")
        if key:
            total[key] = total.get(key, 0.0) + (value / 100 if percent and key not in GI_FLAT else value)

    sets: dict[str, int] = {}
    for item in equip:
        flat = item.get("flat", {})
        if flat.get("itemType") == "ITEM_WEAPON":
            for s in flat.get("weaponStats", []):
                add(s.get("appendPropId"), float(s.get("statValue", 0)))
            # The passive's lasting stats (Jade Cutter's HP, Mistsplitter's DMG Bonus), when the game data has them.
            store = assets.data.get("gi_weapons", {}).get(str(item.get("itemId")), {})
            refine = next(iter((item.get("weapon") or {}).get("affixMap", {}).values()), 0)
            props = store.get("RefineProps")
            if isinstance(props, list) and refine < len(props):
                for prop in props[refine] or []:
                    add(prop.get("PropType"), float(prop.get("Value", 0)), percent=False)
        elif flat.get("itemType") == "ITEM_RELIQUARY":
            main = flat.get("reliquaryMainstat", {})
            add(main.get("mainPropId"), float(main.get("statValue", 0)))
            for s in flat.get("reliquarySubstats", []):
                add(s.get("appendPropId"), float(s.get("statValue", 0)))
            if flat.get("setId"):
                sets[str(flat["setId"])] = sets.get(str(flat["setId"]), 0) + 1
    set_data = assets.data.get("gi_relics", {}).get("Sets", {})
    for set_id, count in sets.items():
        if count >= 2:  # the 2-piece stat (18% ATK, 20% Energy Recharge, ...)
            for key, value in (set_data.get(set_id, {}).get("AddProps") or {}).items():
                total[key] = total.get(key, 0.0) + float(value)
    return total


def _genshin_info(assets: Assets, wearer: dict, donor: dict) -> dict:
    props = {k: float(v) for k, v in wearer.get("fightPropMap", {}).items()}
    for key, value in _gi_gear(assets, wearer.get("equipList", [])).items():
        props[key] = props.get(key, 0.0) - value
    for key, value in _gi_gear(assets, donor.get("equipList", [])).items():
        props[key] = props.get(key, 0.0) + value
    for key in GI_KEYS.values():
        if key in props and abs(props[key]) < 1e-6:
            props[key] = 0.0
    g = props.get
    props[genshin.HP] = g("1", 0) * (1 + g("3", 0)) + g("2", 0)
    props[genshin.ATK] = g("4", 0) * (1 + g("6", 0)) + g("5", 0)
    props[genshin.DEF] = g("7", 0) * (1 + g("9", 0)) + g("8", 0)
    equip = [e for e in wearer.get("equipList", []) if e.get("flat", {}).get("itemType") not in ("ITEM_WEAPON", "ITEM_RELIQUARY")]
    equip += [e for e in donor.get("equipList", []) if e.get("flat", {}).get("itemType") in ("ITEM_WEAPON", "ITEM_RELIQUARY")]
    return {**wearer, "fightPropMap": props, "equipList": equip}
