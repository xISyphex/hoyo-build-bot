"""Zenless Zone Zero: https://enka.network/api/zzz/uid/{uid}

Like Star Rail, final stats are not in the response. They are computed with the
formulas from Enka's ZZZ docs (docs/zzz/api.md, "Formulas"): agent base stats
from avatars.json, the "approximate" W-Engine and drive disc scaling, and
substats as base value x roll count.

Property IDs end in 1 (base), 2 (percent) or 3 (flat), so one rule covers all:
final = base * (1 + percent / 10000) + flat.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

from ..assets import Assets
from ..models import CharacterBuild, Gear, PlayerProfile, Stat, Weapon
from . import fmt_int

RARITY = {4: "S", 3: "A", 2: "B"}
ELEMENTS = {
    "Elec": "Electric",
    "Physics": "Physical",
    "Fire": "Fire",
    "Ice": "Ice",
    "Ether": "Ether",
    "FireFrost": "Frost",
    "AuricEther": "Auric Ink",
    "Wind": "Wind",
}

# stat group (property id // 100) -> (display name, kind)
GROUPS = {
    111: ("HP", "int"),
    121: ("ATK", "int"),
    131: ("DEF", "int"),
    122: ("Impact", "int"),
    201: ("CRIT Rate", "pct"),
    211: ("CRIT DMG", "pct"),
    312: ("Anomaly Proficiency", "int"),
    314: ("Anomaly Mastery", "int"),
    231: ("PEN Ratio", "pct"),
    232: ("PEN", "int"),
    305: ("Energy Regen", "regen"),
    315: ("Physical DMG Bonus", "pct"),
    316: ("Fire DMG Bonus", "pct"),
    317: ("Ice DMG Bonus", "pct"),
    318: ("Electric DMG Bonus", "pct"),
    319: ("Ether DMG Bonus", "pct"),
    323: ("Wind DMG Bonus", "pct"),
}
# Energy Regen is left out: Rupture agents have none, so it only shows when non-zero.
ALWAYS_SHOWN = [111, 121, 131, 122, 201, 211, 312, 314, 231, 232]
SHORT = {
    "HP": "HP", "ATK": "ATK", "DEF": "DEF", "Impact": "Impact", "CRIT Rate": "CRIT Rate",
    "CRIT DMG": "CRIT DMG", "Anomaly Proficiency": "AP", "Anomaly Mastery": "AM",
    "PEN Ratio": "PEN Ratio", "PEN": "PEN", "Energy Regen": "ER",
}
DISC_SCALE = {4: 0.2, 3: 0.25, 2: 0.3}
SKILLS = [(0, "Basic"), (2, "Dodge"), (6, "Assist"), (1, "Special"), (3, "Chain"), (5, "Core")]


def _prop_stat(prop_id: int, value: float) -> Stat:
    """A single gear/weapon line, e.g. 'ATK% 9.0%' or 'PEN 18'."""
    group, kind = prop_id // 100, prop_id % 100
    name, display = GROUPS.get(group, (str(prop_id), "int"))
    name = SHORT.get(name, name.replace(" Bonus", ""))
    if kind == 2:
        return Stat(f"{name}%", f"{value / 100:.1f}%")
    if display == "pct":
        return Stat(name, f"{value / 100:.1f}%")
    return Stat(name, fmt_int(value))


def _skill_levels(raw) -> dict[int, int]:
    if isinstance(raw, dict):
        return {int(k): int(v) for k, v in raw.items()}
    return {int(s.get("Index", 0)): int(s.get("Level", 1)) for s in raw or []}


def _effect(assets: Assets, weapon_id, phase: int) -> tuple[str | None, str | None]:
    """W-Engine passive (name, plain text) for its phase, from Hakushin's per-phase talents."""
    talents = assets.data.get("zzz_weapon_effects", {}).get(str(weapon_id)) or {}
    talent = talents.get(str(phase)) or talents.get(str(max(1, min(phase, 5))))
    if not talent or not talent.get("desc"):
        return None, None
    text = re.sub(r"<.*?>|\{SPRITE_PRESET#[^}]+\}", "", talent["desc"])
    text = text.replace("\\n", "\n").replace("\r\n", "\n").strip()
    return talent.get("name") or None, text


def _element(types: list[str]) -> str:
    """First element we have a name for; e.g. Ye Shunguang is ["ZhenZhenAssault", "Physics"]."""
    for t in types:
        if t in ELEMENTS:
            return ELEMENTS[t]
    return types[0] if types else ""


def parse_character(assets: Assets, info: dict) -> CharacterBuild:
    avatar_id = str(info["Id"])
    meta = assets.data["zzz_avatars"].get(avatar_id, {})
    level = int(info.get("Level", 1))
    promotion = int(info.get("PromotionLevel", 1))
    core = int(info.get("CoreSkillEnhancement", 0))
    mindscape = int(info.get("TalentLevel", 0))
    name = assets.zzz_text(meta.get("Name")) or f"Agent {avatar_id}"

    base: dict[int, float] = defaultdict(float)
    pct: dict[int, float] = defaultdict(float)
    flat: dict[int, float] = defaultdict(float)

    def add(prop_id: int, value: float) -> None:
        group, kind = divmod(int(prop_id), 100)
        {1: base, 2: pct, 3: flat}.get(kind, flat)[group] += value

    # Agent base stats (floored, as the docs recommend)
    promotions = meta.get("PromotionProps", [])
    cores = meta.get("CoreEnhancementProps", [])
    for prop, value in meta.get("BaseProps", {}).items():
        total = value + meta.get("GrowthProps", {}).get(prop, 0) * (level - 1) / 10000
        if 0 < promotion <= len(promotions):
            total += promotions[promotion - 1].get(prop, 0)
        if 0 <= core < len(cores):
            total += cores[core].get(prop, 0)
        add(int(prop), math.floor(total))

    # W-Engine
    weapon = None
    w = info.get("Weapon")
    if w:
        wmeta = assets.data["zzz_weapons"].get(str(w.get("Id")), {})
        wlevel = int(w.get("Level", 1))
        brk = int(w.get("BreakLevel", 0))
        stats = []
        main = wmeta.get("MainStat")
        if main:
            val = math.floor(main["PropertyValue"] * (1 + 0.1568166666666667 * wlevel + 0.8922 * brk))
            add(main["PropertyId"], val)
            stats.append(_prop_stat(main["PropertyId"], val))
        second = wmeta.get("SecondaryStat")
        if second:
            val = math.floor(second["PropertyValue"] * (1 + 0.3 * brk))
            add(second["PropertyId"], val)
            stats.append(_prop_stat(second["PropertyId"], val))
        effect_name, effect = _effect(assets, w.get("Id"), int(w.get("UpgradeLevel", 1)))
        weapon = Weapon(
            name=assets.zzz_text(wmeta.get("ItemName")) or f"W-Engine {w.get('Id')}",
            level=wlevel,
            refinement=int(w.get("UpgradeLevel", 1)),
            rarity=int(wmeta.get("Rarity", 0)),
            stats=stats,
            effect_name=effect_name,
            effect=effect,
        )

    # Drive discs
    equipments = assets.data["zzz_equipments"]
    gear: list[Gear] = []
    suit_counts: dict[str, int] = defaultdict(int)
    for slot_entry in info.get("EquippedList", []):
        disc = slot_entry.get("Equipment", {})
        item = equipments.get("Items", {}).get(str(disc.get("Id")), {})
        rarity = int(item.get("Rarity", 4))
        suit_id = str(item.get("SuitId", ""))
        suit = equipments.get("Suits", {}).get(suit_id, {})
        suit_counts[suit_id] += 1
        dlevel = int(disc.get("Level", 0))
        # Live responses use MainPropertyList; the docs call it MainStatList.
        mains = disc.get("MainPropertyList") or disc.get("MainStatList") or []
        main_stat = Stat("?", "?")
        if mains:
            m = mains[0]
            val = math.floor(m["PropertyValue"] * (1 + dlevel * DISC_SCALE.get(rarity, 0.2)))
            add(m["PropertyId"], val)
            main_stat = _prop_stat(m["PropertyId"], val)
        subs = []
        for sub in disc.get("RandomPropertyList") or []:
            rolls = int(sub.get("PropertyLevel", 1))
            val = sub["PropertyValue"] * rolls
            add(sub["PropertyId"], val)
            stat = _prop_stat(sub["PropertyId"], val)
            stat.rolls = rolls
            subs.append(stat)
        gear.append(
            Gear(
                slot=f"Disc {slot_entry.get('Slot', '?')}",
                set_name=assets.zzz_text(suit.get("Name")) or f"Set {suit_id}",
                level=dlevel,
                rarity=rarity,
                main=main_stat,
                subs=subs,
                # A disc's picture is its set's picture.
                piece_icon=f"https://enka.network{suit['Icon']}" if suit.get("Icon") else None,
            )
        )
    gear.sort(key=lambda g: g.slot)

    set_bonuses = []
    for suit_id, count in sorted(suit_counts.items(), key=lambda kv: -kv[1]):
        suit = equipments.get("Suits", {}).get(suit_id, {})
        if count >= 2:
            for prop, value in suit.get("SetBonusProps", {}).items():
                add(int(prop), value)
        suit_name = assets.zzz_text(suit.get("Name")) or f"Set {suit_id}"
        if count >= 4:
            set_bonuses.append(f"4pc {suit_name}")
        elif count >= 2:
            set_bonuses.append(f"2pc {suit_name}")

    stats = []
    for group, (label, display) in GROUPS.items():
        total = base[group] * (1 + pct[group] / 10000) + flat[group]
        if group not in ALWAYS_SHOWN and not total:
            continue
        if display == "pct":
            stats.append(Stat(label, f"{total / 100:.1f}%"))
        elif display == "regen":
            stats.append(Stat(label, f"{total / 100:.2f}"))
        else:
            stats.append(Stat(label, fmt_int(math.floor(total))))

    levels = _skill_levels(info.get("SkillLevelList"))
    bonus = 4 if mindscape >= 5 else 2 if mindscape >= 3 else 0
    talents = []
    for index, label in SKILLS:
        if index == 5:
            talents.append(Stat(label, "ABCDEF"[core - 1] if core else "-"))
        elif index in levels:
            talents.append(Stat(label, f"{levels[index] + bonus}" + (" ★" if bonus else "")))

    elements = meta.get("ElementTypes", [])
    icon = meta.get("CircleIcon") or meta.get("Image")
    return CharacterBuild(
        game="zzz",
        character_id=avatar_id,
        name=name,
        level=level,
        rarity=int(meta.get("Rarity", 0)),
        element=_element(elements),
        constellation=mindscape,
        icon_url=f"https://enka.network{icon}" if icon else None,
        stats=stats,
        talents=talents,
        weapon=weapon,
        gear=gear,
        set_bonuses=set_bonuses,
        notes=["W-Engine and disc main stats use Enka's approximate formulas and may be off by 1."],
    )


def parse_profile(assets: Assets, uid: str, data: dict) -> PlayerProfile:
    player = data.get("PlayerInfo", {})
    profile = player.get("SocialDetail", {}).get("ProfileDetail", {})
    avatars = (player.get("ShowcaseDetail") or {}).get("AvatarList") or []
    characters = [parse_character(assets, a) for a in avatars]
    return PlayerProfile(
        game="zzz",
        uid=uid,
        nickname=profile.get("Nickname", "Unknown"),
        level=int(profile.get("Level", 0)),
        characters=characters,
        ttl=int(data.get("ttl", 60)),
        profile_url=f"https://enka.network/zzz/{uid}/",
        showcase_names=[c.name for c in characters],
    )


def rarity_letter(rarity: int) -> str:
    return RARITY.get(rarity, "?")
