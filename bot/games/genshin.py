"""Genshin Impact: https://enka.network/api/uid/{uid}/

Genshin is the easy one: the API already sends final stats in fightPropMap,
so nothing has to be computed.
"""

from __future__ import annotations

from ..assets import Assets
from ..models import CharacterBuild, Gear, PlayerProfile, Stat, Weapon
from . import fmt_int, fmt_pct

# fightPropMap keys
HP, ATK, DEF = "2000", "2001", "2002"
EM, CRIT_RATE, CRIT_DMG, ER, HEALING = "28", "20", "22", "23", "26"
DMG_BONUS = {
    "Physical": "30",
    "Fire": "40",
    "Electric": "41",
    "Water": "42",
    "Grass": "43",
    "Wind": "44",
    "Rock": "45",
    "Ice": "46",
}
ELEMENT_NAMES = {
    "Fire": "Pyro",
    "Electric": "Electro",
    "Water": "Hydro",
    "Grass": "Dendro",
    "Wind": "Anemo",
    "Rock": "Geo",
    "Ice": "Cryo",
    "Physical": "Physical",
}

SLOTS = {
    "EQUIP_BRACER": "Flower",
    "EQUIP_NECKLACE": "Plume",
    "EQUIP_SHOES": "Sands",
    "EQUIP_RING": "Goblet",
    "EQUIP_DRESS": "Circlet",
}
SLOT_ORDER = list(SLOTS.values())

FLAT_PROPS = {
    "FIGHT_PROP_HP",
    "FIGHT_PROP_ATTACK",
    "FIGHT_PROP_DEFENSE",
    "FIGHT_PROP_BASE_ATTACK",
    "FIGHT_PROP_BASE_HP",
    "FIGHT_PROP_BASE_DEFENSE",
    "FIGHT_PROP_ELEMENT_MASTERY",
}

PROP_SHORT = {
    "FIGHT_PROP_HP": "HP",
    "FIGHT_PROP_HP_PERCENT": "HP%",
    "FIGHT_PROP_ATTACK": "ATK",
    "FIGHT_PROP_ATTACK_PERCENT": "ATK%",
    "FIGHT_PROP_DEFENSE": "DEF",
    "FIGHT_PROP_DEFENSE_PERCENT": "DEF%",
    "FIGHT_PROP_BASE_ATTACK": "Base ATK",
    "FIGHT_PROP_CRITICAL": "CRIT Rate",
    "FIGHT_PROP_CRITICAL_HURT": "CRIT DMG",
    "FIGHT_PROP_ELEMENT_MASTERY": "EM",
    "FIGHT_PROP_CHARGE_EFFICIENCY": "ER",
    "FIGHT_PROP_HEAL_ADD": "Healing",
    "FIGHT_PROP_PHYSICAL_ADD_HURT": "Physical DMG",
    "FIGHT_PROP_FIRE_ADD_HURT": "Pyro DMG",
    "FIGHT_PROP_ELEC_ADD_HURT": "Electro DMG",
    "FIGHT_PROP_WATER_ADD_HURT": "Hydro DMG",
    "FIGHT_PROP_GRASS_ADD_HURT": "Dendro DMG",
    "FIGHT_PROP_WIND_ADD_HURT": "Anemo DMG",
    "FIGHT_PROP_ROCK_ADD_HURT": "Geo DMG",
    "FIGHT_PROP_ICE_ADD_HURT": "Cryo DMG",
}

TALENT_LABELS = ["Normal", "Skill", "Burst"]



def _roll_counts(append_ids: list[int]) -> list[int]:
    """Rolls per substat, in the order the substats are listed.

    appendPropIdList has one affix id per roll (initial ones included). The id
    without its last digit (the roll's tier) names the stat, and stats appear
    in the same order as reliquarySubstats.
    """
    counts: dict[int, int] = {}
    for affix in append_ids:
        counts[affix // 10] = counts.get(affix // 10, 0) + 1
    return list(counts.values())

def _prop(prop_id: str, value: float) -> Stat:
    name = PROP_SHORT.get(prop_id, prop_id.replace("FIGHT_PROP_", "").title())
    if prop_id in FLAT_PROPS:
        return Stat(name, fmt_int(round(value)))
    # Artifact/weapon stat values for percentages come as e.g. 31.1
    return Stat(name, f"{value:.1f}%")


def _avatar_key(assets: Assets, info: dict) -> str:
    avatar_id = str(info["avatarId"])
    depot = info.get("skillDepotId")
    variant = f"{avatar_id}-{depot}"
    if depot and variant in assets.data["gi_avatars"]:
        return variant  # Traveler: one entry per element
    return avatar_id


def _weapon_name(assets: Assets, item: dict) -> str:
    # The hashes inside the API response are sometimes missing from the store's
    # text map, so prefer the store's own entry for the item.
    store = assets.data.get("gi_weapons", {}).get(str(item.get("itemId")), {})
    return (
        assets.gi_text(store.get("NameTextMapHash"))
        or assets.gi_text(item.get("flat", {}).get("nameTextMapHash"))
        or "Unknown weapon"
    )


def _set_icon(assets: Assets, flat: dict) -> str | None:
    """The set's flower, which the game uses as the set's picture; else this piece's own icon."""
    items = assets.data.get("gi_relics", {}).get("Items", {})
    flower = f"/ui/UI_RelicIcon_{flat.get('setId')}_4.png"
    if any(item.get("Icon") == flower for item in items.values()):
        return "https://enka.network" + flower
    return f"https://enka.network/ui/{flat['icon']}.png" if flat.get("icon") else None


def _set_name(assets: Assets, flat: dict) -> str | None:
    store = assets.data.get("gi_relics", {}).get("Sets", {}).get(str(flat.get("setId")), {})
    return assets.gi_text(store.get("Name")) or assets.gi_text(flat.get("setNameTextMapHash"))


def parse_character(assets: Assets, info: dict) -> CharacterBuild:
    key = _avatar_key(assets, info)
    meta = assets.data["gi_avatars"].get(key, {})
    name = assets.gi_text(meta.get("NameTextMapHash")) or f"Character {key}"
    element = meta.get("Element", "None")
    props = {k: float(v) for k, v in info.get("fightPropMap", {}).items()}
    level_prop = info.get("propMap", {}).get("4001", {})
    level = int(level_prop.get("val", level_prop.get("ival", 0)))

    stats = [
        Stat("HP", fmt_int(props.get(HP, 0))),
        Stat("ATK", fmt_int(props.get(ATK, 0))),
        Stat("DEF", fmt_int(props.get(DEF, 0))),
        Stat("Elemental Mastery", fmt_int(props.get(EM, 0))),
        Stat("CRIT Rate", fmt_pct(props.get(CRIT_RATE, 0))),
        Stat("CRIT DMG", fmt_pct(props.get(CRIT_DMG, 0))),
        Stat("Energy Recharge", fmt_pct(props.get(ER, 0))),
    ]
    dmg_key = DMG_BONUS.get(element)
    if dmg_key and props.get(dmg_key):
        stats.append(Stat(f"{ELEMENT_NAMES[element]} DMG Bonus", fmt_pct(props[dmg_key])))
    if props.get(DMG_BONUS["Physical"]) and element != "Physical":
        stats.append(Stat("Physical DMG Bonus", fmt_pct(props[DMG_BONUS["Physical"]])))
    if props.get(HEALING):
        stats.append(Stat("Healing Bonus", fmt_pct(props[HEALING])))

    # Talent levels, including the +3 from constellations.
    talents = []
    skill_levels = info.get("skillLevelMap", {})
    extra = info.get("proudSkillExtraLevelMap", {})
    for label, skill_id in zip(TALENT_LABELS, meta.get("SkillOrder", [])):
        base = int(skill_levels.get(str(skill_id), 1))
        proud = meta.get("ProudMap", {}).get(str(skill_id))
        bonus = int(extra.get(str(proud), 0)) if proud is not None else 0
        talents.append(Stat(label, f"{base + bonus}" + (" ★" if bonus else "")))

    weapon = None
    gear: list[Gear] = []
    set_counts: dict[str, int] = {}
    for item in info.get("equipList", []):
        flat = item.get("flat", {})
        if flat.get("itemType") == "ITEM_WEAPON":
            w = item.get("weapon", {})
            refinement = next(iter(w.get("affixMap", {}).values()), 0) + 1
            weapon = Weapon(
                name=_weapon_name(assets, item),
                level=int(w.get("level", 1)),
                refinement=refinement,
                rarity=int(flat.get("rankLevel", 0)),
                stats=[_prop(s["appendPropId"], s["statValue"]) for s in flat.get("weaponStats", [])],
            )
        elif flat.get("itemType") == "ITEM_RELIQUARY":
            set_name = _set_name(assets, flat)
            if set_name:
                set_counts[set_name] = set_counts.get(set_name, 0) + 1
            main = flat.get("reliquaryMainstat", {})
            subs = [_prop(s["appendPropId"], s["statValue"]) for s in flat.get("reliquarySubstats", [])]
            for stat, rolls in zip(subs, _roll_counts(item.get("reliquary", {}).get("appendPropIdList", []))):
                stat.rolls = rolls
            gear.append(
                Gear(
                    slot=SLOTS.get(flat.get("equipType"), "?"),
                    set_name=set_name or "Unknown set",
                    level=max(int(item.get("reliquary", {}).get("level", 1)) - 1, 0),
                    rarity=int(flat.get("rankLevel", 0)),
                    main=_prop(main.get("mainPropId", ""), main.get("statValue", 0)),
                    subs=subs,
                    icon=_set_icon(assets, flat),
                )
            )
    gear.sort(key=lambda g: SLOT_ORDER.index(g.slot) if g.slot in SLOT_ORDER else 99)

    set_bonuses = []
    for set_name, count in sorted(set_counts.items(), key=lambda kv: -kv[1]):
        if count >= 4:
            set_bonuses.append(f"4pc {set_name}")
        elif count >= 2:
            set_bonuses.append(f"2pc {set_name}")

    side_icon = meta.get("SideIconName")
    icon = None
    if side_icon:
        icon = "https://enka.network" + side_icon.replace("_Side", "")

    return CharacterBuild(
        game="genshin",
        character_id=key,
        name=name,
        level=level,
        rarity=5 if meta.get("QualityType") in ("QUALITY_ORANGE", "QUALITY_ORANGE_SP") else 4,
        element=ELEMENT_NAMES.get(element, element),
        constellation=len(info.get("talentIdList", [])),
        icon_url=icon,
        stats=stats,
        talents=talents,
        weapon=weapon,
        gear=gear,
        set_bonuses=set_bonuses,
    )


def parse_profile(assets: Assets, uid: str, data: dict) -> PlayerProfile:
    player = data.get("playerInfo", {})
    showcase = []
    for entry in player.get("showAvatarInfoList", []):
        meta = assets.data["gi_avatars"].get(str(entry.get("avatarId")), {})
        name = assets.gi_text(meta.get("NameTextMapHash"))
        if name:
            showcase.append(name)
    return PlayerProfile(
        game="genshin",
        uid=uid,
        nickname=player.get("nickname", "Unknown"),
        level=int(player.get("level", 0)),
        characters=[parse_character(assets, c) for c in data.get("avatarInfoList", [])],
        ttl=int(data.get("ttl", 60)),
        profile_url=f"https://enka.network/u/{uid}/",
        showcase_names=showcase,
    )
