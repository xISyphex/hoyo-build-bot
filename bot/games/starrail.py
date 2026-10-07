"""Honkai: Star Rail: https://enka.network/api/hsr/uid/{uid}

The API sends levels, IDs and relic roll counts but no final stats, so they are
computed here from Enka's honker_meta.json the same way the in-game character
panel does: (character base + light cone base) * (1 + %bonuses) + flat bonuses.
Conditional effects (light cone passives that need a trigger, 4pc sets with
conditions) are not in the meta file and are left out, as in-game.
"""

from __future__ import annotations

from collections import defaultdict

from ..assets import Assets
from ..models import CharacterBuild, Gear, PlayerProfile, Stat, Weapon
from . import fmt_int, fmt_pct

ELEMENTS = {
    "Thunder": "Lightning",
    "Fire": "Fire",
    "Ice": "Ice",
    "Physical": "Physical",
    "Quantum": "Quantum",
    "Imaginary": "Imaginary",
    "Wind": "Wind",
}

SLOTS = {
    "HEAD": "Head",
    "HAND": "Hands",
    "BODY": "Body",
    "FOOT": "Feet",
    "NECK": "Planar Sphere",
    "OBJECT": "Link Rope",
}
SLOT_ORDER = list(SLOTS.values())

FLAT = {"HPDelta", "AttackDelta", "DefenceDelta", "SpeedDelta", "BaseSpeed"}
PROP_SHORT = {
    "HPDelta": "HP",
    "HPAddedRatio": "HP%",
    "AttackDelta": "ATK",
    "AttackAddedRatio": "ATK%",
    "DefenceDelta": "DEF",
    "DefenceAddedRatio": "DEF%",
    "SpeedDelta": "SPD",
    "CriticalChanceBase": "CRIT Rate",
    "CriticalDamageBase": "CRIT DMG",
    "StatusProbabilityBase": "Effect Hit Rate",
    "StatusResistanceBase": "Effect RES",
    "BreakDamageAddedRatioBase": "Break Effect",
    "HealRatioBase": "Outgoing Healing",
    "SPRatioBase": "Energy Regen Rate",
    "PhysicalAddedRatio": "Physical DMG",
    "FireAddedRatio": "Fire DMG",
    "IceAddedRatio": "Ice DMG",
    "ThunderAddedRatio": "Lightning DMG",
    "WindAddedRatio": "Wind DMG",
    "QuantumAddedRatio": "Quantum DMG",
    "ImaginaryAddedRatio": "Imaginary DMG",
}
TALENT_LABELS = ["Basic ATK", "Skill", "Ultimate", "Talent"]


def _fmt_prop(prop: str, value: float) -> Stat:
    name = PROP_SHORT.get(prop, prop)
    if prop in FLAT:
        return Stat(name, f"{value:.1f}" if prop == "SpeedDelta" and value % 1 else fmt_int(value))
    return Stat(name, fmt_pct(value))


def _add(bonus: dict, props: dict | None) -> None:
    for key, value in (props or {}).items():
        bonus[key] += value


def parse_character(assets: Assets, info: dict) -> CharacterBuild:
    avatar_id = str(info["avatarId"])
    char = assets.data["hsr_characters"].get(avatar_id, {})
    meta = assets.data["hsr_meta"]
    level = int(info.get("level", 1))
    promotion = str(info.get("promotion", 0))
    rank = int(info.get("rank", 0))
    name = assets.hsr_text(char.get("AvatarName", {}).get("Hash")) or f"Character {avatar_id}"
    if "{" in name:  # main character name is a {NICKNAME} placeholder
        name = "Trailblazer"
    element = char.get("Element", "")

    base = meta["avatar"].get(avatar_id, {}).get(promotion, {})
    base_hp = base.get("HPBase", 0) + base.get("HPAdd", 0) * (level - 1)
    base_atk = base.get("AttackBase", 0) + base.get("AttackAdd", 0) * (level - 1)
    base_def = base.get("DefenceBase", 0) + base.get("DefenceAdd", 0) * (level - 1)
    base_spd = base.get("SpeedBase", 0)
    bonus: dict[str, float] = defaultdict(float)
    bonus["CriticalChanceBase"] += base.get("CriticalChance", 0)
    bonus["CriticalDamageBase"] += base.get("CriticalDamage", 0)

    # Light cone
    weapon = None
    eq = info.get("equipment")
    if eq:
        tid = str(eq["tid"])
        lc_level = int(eq.get("level", 1))
        lc_rank = int(eq.get("rank", 1))
        lc = meta["equipment"].get(tid, {}).get(str(eq.get("promotion", 0)), {})
        lc_hp = lc.get("BaseHP", 0) + lc.get("HPAdd", 0) * (lc_level - 1)
        lc_atk = lc.get("BaseAttack", 0) + lc.get("AttackAdd", 0) * (lc_level - 1)
        lc_def = lc.get("BaseDefence", 0) + lc.get("DefenceAdd", 0) * (lc_level - 1)
        base_hp += lc_hp
        base_atk += lc_atk
        base_def += lc_def
        wep = assets.data["hsr_weapons"].get(tid, {})
        if wep.get("AvatarBaseType") == char.get("AvatarBaseType"):
            _add(bonus, meta["equipmentSkill"].get(tid, {}).get(str(lc_rank), {}).get("props"))
        weapon = Weapon(
            name=assets.hsr_text(wep.get("EquipmentName", {}).get("Hash"))
            or assets.hsr_text((eq.get("_flat") or {}).get("name"))
            or f"Light Cone {tid}",
            level=lc_level,
            refinement=lc_rank,
            rarity=int(wep.get("Rarity", 0)),
            stats=[Stat("HP", fmt_int(lc_hp)), Stat("ATK", fmt_int(lc_atk)), Stat("DEF", fmt_int(lc_def))],
        )

    # Traces (minor stat nodes)
    eidolon_skill_bonus: dict[int, int] = defaultdict(int)
    for rank_id in char.get("RankIDList", [])[:rank]:
        for skill_id, add in assets.data.get("hsr_ranks", {}).get(str(rank_id), {}).get("SkillAddLevelList", {}).items():
            eidolon_skill_bonus[int(skill_id) % 100] += add
    point_levels = {}
    for point in info.get("skillTreeList", []):
        pid = str(point["pointId"])
        lvl = int(point.get("level", 1))
        point_levels[pid] = lvl
        _add(bonus, meta["tree"].get(pid, {}).get(str(lvl), {}).get("props"))

    talents = []
    anchors = assets.data["hsr_skilltree"].get(avatar_id, {}).get("0", [])[:4]
    for label, pid in zip(TALENT_LABELS, anchors):
        lvl = point_levels.get(pid, 1)
        extra = eidolon_skill_bonus.get(int(pid) % 100, 0)
        talents.append(Stat(label, f"{lvl + extra}" + (" ★" if extra else "")))

    # Relics
    gear: list[Gear] = []
    set_counts: dict[int, int] = defaultdict(int)
    set_names: dict[int, str] = {}
    for relic in info.get("relicList", []):
        tid = str(relic["tid"])
        rmeta = assets.data["hsr_relics"].get(tid, {})
        rlevel = int(relic.get("level", 0))
        main_def = meta["relic"]["mainAffix"].get(str(rmeta.get("MainAffixGroup")), {}).get(str(relic.get("mainAffixId")), {})
        main_prop = main_def.get("Property", "")
        main_val = main_def.get("BaseValue", 0) + main_def.get("LevelAdd", 0) * rlevel
        bonus[main_prop] += main_val
        subs = []
        for sub in relic.get("subAffixList", []):
            sdef = meta["relic"]["subAffix"].get(str(rmeta.get("SubAffixGroup")), {}).get(str(sub.get("affixId")), {})
            val = sdef.get("BaseValue", 0) * sub.get("cnt", 1) + sdef.get("StepValue", 0) * sub.get("step", 0)
            bonus[sdef.get("Property", "")] += val
            subs.append(_fmt_prop(sdef.get("Property", ""), val))
        set_id = int(rmeta.get("SetID", 0))
        set_counts[set_id] += 1
        flat = relic.get("_flat") or {}
        set_names.setdefault(set_id, assets.hsr_text(flat.get("setName")) or f"Set {set_id}")
        gear.append(
            Gear(
                slot=SLOTS.get(rmeta.get("Type"), "?"),
                set_name=set_names[set_id],
                level=rlevel,
                rarity=int(rmeta.get("Rarity", 0)),
                main=_fmt_prop(main_prop, main_val),
                subs=subs,
            )
        )
    gear.sort(key=lambda g: SLOT_ORDER.index(g.slot) if g.slot in SLOT_ORDER else 99)

    set_bonuses = []
    for set_id, count in sorted(set_counts.items(), key=lambda kv: -kv[1]):
        skills = meta["relic"]["setSkill"].get(str(set_id), {})
        for need in (2, 4):
            if count >= need and str(need) in skills:
                _add(bonus, skills[str(need)].get("props"))
        if count >= 4:
            set_bonuses.append(f"4pc {set_names[set_id]}")
        elif count >= 2:
            set_bonuses.append(f"2pc {set_names[set_id]}")

    hp = base_hp * (1 + bonus["HPAddedRatio"]) + bonus["HPDelta"]
    atk = base_atk * (1 + bonus["AttackAddedRatio"]) + bonus["AttackDelta"]
    df = base_def * (1 + bonus["DefenceAddedRatio"]) + bonus["DefenceDelta"]
    spd = (base_spd + bonus["BaseSpeed"]) * (1 + bonus["SpeedAddedRatio"]) + bonus["SpeedDelta"]
    elem_dmg = bonus[f"{element}AddedRatio"] + bonus["AllDamageTypeAddedRatio"]

    stats = [
        Stat("HP", fmt_int(hp)),
        Stat("ATK", fmt_int(atk)),
        Stat("DEF", fmt_int(df)),
        Stat("SPD", f"{spd:.1f}"),
        Stat("CRIT Rate", fmt_pct(bonus["CriticalChanceBase"])),
        Stat("CRIT DMG", fmt_pct(bonus["CriticalDamageBase"])),
        Stat("Break Effect", fmt_pct(bonus["BreakDamageAddedRatioBase"])),
        Stat("Energy Regen Rate", fmt_pct(1 + bonus["SPRatioBase"])),
        Stat("Effect Hit Rate", fmt_pct(bonus["StatusProbabilityBase"])),
        Stat("Effect RES", fmt_pct(bonus["StatusResistanceBase"])),
    ]
    if bonus["HealRatioBase"]:
        stats.append(Stat("Outgoing Healing", fmt_pct(bonus["HealRatioBase"])))
    if elem_dmg:
        stats.append(Stat(f"{ELEMENTS.get(element, element)} DMG Boost", fmt_pct(elem_dmg)))

    icon_path = char.get("AvatarSideIconPath")
    return CharacterBuild(
        game="hsr",
        character_id=avatar_id,
        name=name,
        level=level,
        rarity=int(char.get("Rarity", 0)),
        element=ELEMENTS.get(element, element),
        constellation=rank,
        icon_url=f"https://enka.network/ui/hsr/{icon_path}" if icon_path else None,
        stats=stats,
        talents=talents,
        weapon=weapon,
        gear=gear,
        set_bonuses=set_bonuses,
        notes=["Stats exclude conditional buffs, like the in-game character screen."],
    )


def parse_profile(assets: Assets, uid: str, data: dict) -> PlayerProfile:
    detail = data.get("detailInfo", {})
    characters = [parse_character(assets, c) for c in detail.get("avatarDetailList", [])]
    return PlayerProfile(
        game="hsr",
        uid=uid,
        nickname=detail.get("nickname", "Unknown"),
        level=int(detail.get("level", 0)),
        characters=characters,
        ttl=int(data.get("ttl", 60)),
        profile_url=f"https://enka.network/hsr/{uid}/",
        showcase_names=[c.name for c in characters],
    )
