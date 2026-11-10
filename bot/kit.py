"""What a Star Rail character's own abilities add to /hsr-optimize's score: the multiplier of their strongest hit and
the buffs their kit gives them.

Both are read from the ability texts in the game data (StarRailRes: a sentence with numbered blanks and the numbers
per level), at the levels a fully built character has: Basic ATK 6, everything else 10, every trace. Eidolons aren't
counted. Buffs are read the way light cone passives are (bot/cone_effects.py): as active, at full stacks. Buffs for
the whole team count, since the character is on it; buffs for one other ally don't.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import cone_effects
from .assets import Assets

HIT = re.compile(rf"DMG equal to {cone_effects.BLANK}% of [^,;]{{0,60}}?\b(ATK|Max HP|HP|DEF)\b")
STAT = {"ATK": "atk", "Max HP": "hp", "HP": "hp", "DEF": "def"}
ATTACKS = ("Normal", "BPSkill", "Ultra", "Talent")
# Buffs the text reader gets wrong, by character id: the value to count for a stat instead (None: don't count it).
FIXES: dict[str, dict[str, float | None]] = {}


@dataclass
class Kit:
    multiplier: float = 1.0  # the strongest hit, as a share of the stat it scales with (3.6 = 360%)
    scaling: str | None = None  # "atk", "hp" or "def"
    hit: str | None = None  # the ability that hit belongs to
    buffs: dict[str, float] = field(default_factory=dict)


def _params(entry: dict, level: int) -> list[float]:
    rows = entry.get("params") or []
    if not rows:
        return []
    return [float(p) for p in rows[min(level, len(rows)) - 1]]


# Sentences that aren't a buff on the character's own damage: a buff for one other ally, healing, shields. Reading
# them as buffs is the usual way to get a wrong number, so they are left out. Buffs for all allies stay in: the
# character is one of them.
NOT_SELF = re.compile(r"(?:\bone|single|designated|target|\ban|\bthat|another|other|chosen|specific) all(?:y|ies)\b|\bally target\b(?!s)"
                      r"|\ball(?:y|ies) (?:target |character )?(?:with|who|whose|that)\b|\bexcept\b|excluding|teammate|that target|\btheir ATK\b|the target's (?:CRIT|ATK|DMG)|target has a summon"
                      r"|Toughness|SPD by default|has #\d\[\w+\] SPD|is reduced|are reduced|DMG taken by|DMG dealt to (?!enem)"
                      r"|Outgoing Healing|Shield|restores?|heals?|Weakness Break Efficiency|\bRES\b", re.I)
LIMITS = {"CriticalChanceBase": 1.0, "CriticalDamageBase": 2.5, "AttackAddedRatio": 2.0, "HPAddedRatio": 1.0,
          "DefenceAddedRatio": 1.0, "SpeedAddedRatio": 0.5, "DMG": 2.0, "DefIgnore": 0.6, "Vulnerability": 0.6,
          "BreakDMG": 1.0, "BreakDefIgnore": 0.6, "BreakDamageAddedRatioBase": 1.5, "ElationDamageAddedRatioBase": 1.5}


def _buffs(desc: str, params: list[float]) -> dict[str, float]:
    kept = " ".join(s for s in re.split(r"(?<=[.!])\s+", desc) if not NOT_SELF.search(s))
    found = cone_effects.parse(kept, params)
    if "DefenceAddedRatio" in found and re.search(r"enem|target", kept):  # the enemy's DEF going down, not the character's up
        found["DefIgnore"] = found.get("DefIgnore", 0.0) + found.pop("DefenceAddedRatio")
    return {k: v for k, v in found.items() if 0.02 <= v <= LIMITS.get(k, 1.0)}


def kit(assets: Assets, avatar_id, enhanced: bool = False, scaling: str | None = None) -> Kit:
    """The character's strongest hit (on the stat called scaling, when they have one on it) and their self-buffs."""
    cid = str(avatar_id)
    character = assets.data.get("srr_characters", {}).get(cid)
    skills = assets.data.get("srr_character_skills", {})
    if not character or not skills:
        return Kit()
    lead = ("1" if enhanced else "") + cid
    result = Kit()
    hits: list[tuple[float, str, str]] = []
    by_type: dict[str, dict[str, float]] = {}
    for sid in character.get("skills", []):
        entry = skills.get(str(sid))
        if not entry or not str(sid).startswith(lead) or entry.get("type") not in ATTACKS:
            continue
        params = _params(entry, 6 if entry["type"] == "Normal" else 10)
        desc = entry.get("desc", "")
        for match in HIT.finditer(desc):
            index = int(match.group(1)) - 1
            if index < len(params):
                hits.append((params[index], STAT[match.group(2)], entry.get("name", "")))
        # An ability can be listed in two versions (before and after a rework): the larger reading of each buff counts.
        found = by_type.setdefault(entry["type"], {})
        for key, value in _buffs(desc, params).items():
            found[key] = max(found.get(key, 0.0), value)
    for buffs in by_type.values():
        for key, value in buffs.items():
            result.buffs[key] = result.buffs.get(key, 0.0) + value
    for pid in character.get("skill_trees", []):  # the three ability traces
        point = assets.data.get("srr_skill_trees", {}).get(str(pid), {})
        if point.get("desc") and not point.get("level_up_skills"):
            for key, value in _buffs(point["desc"], _params(point, 1)).items():
                result.buffs[key] = result.buffs.get(key, 0.0) + value
    for key, value in FIXES.get(cid, {}).items():  # corrections by hand (None: don't count it)
        result.buffs.pop(key, None) if value is None else result.buffs.__setitem__(key, value)
    on_stat = [h for h in hits if h[1] == scaling] or hits
    if on_stat:
        result.multiplier, result.scaling, result.hit = max(on_stat)
    result.buffs = {k: round(v, 6) for k, v in result.buffs.items()}
    return result
