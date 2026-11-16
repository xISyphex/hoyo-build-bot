# Ported in part from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/optimization/engine/damage/damageCalculator.ts and its constants, branch main as of 2026-11-16.
"""The damage formulas, as plain functions of numbers (or numpy arrays of them, one per relic combination).

They follow Fribbels' damageCalculator.ts (fribbels/hsr-optimizer, MIT): see THIRD_PARTY_NOTICES.md. Two
differences, both because the user chooses the character's level: the DEF multiplier uses the attacker's level
instead of a fixed 80, and the level multiplier of Break, Super Break and Elation DMG is looked up by level.
"""

from __future__ import annotations

import numpy as np

# Break DMG's level multiplier ("LvMult"). Only Lv. 80 is verified (Fribbels' constant 3767.5533). The other
# anchors are the HSR wiki's Toughness page as quoted by search engines, not checked against game data, and the
# levels between them are interpolated, so any level but 80 gives an approximate Break / Super Break / Elation DMG.
LEVEL_MULTIPLIER_80 = 3767.5533
LEVEL_ANCHORS = {60: 1640.3068, 70: 2659.6406, 79: 3665.9099, 80: LEVEL_MULTIPLIER_80}
ELATION_BASE_80 = 7535.107  # Fribbels' Elation base DMG at Lv. 80 (2 x the level multiplier)

# Break DMG's element multiplier (Fribbels: elementalBreakScaling).
BREAK_ELEMENT = {"Physical": 2.0, "Fire": 2.0, "Wind": 1.5, "Ice": 1.0, "Lightning": 1.0, "Quantum": 0.5, "Imaginary": 0.5}

VULN_CAP = 2.5  # Fribbels clamps DMG taken to [0, 2.5]


def level_multiplier(level: int) -> tuple[float, bool]:
    """(LvMult, exact). Exact only at Lv. 80; other levels interpolate the unverified anchors."""
    if level == 80:
        return LEVEL_MULTIPLIER_80, True
    points = sorted(LEVEL_ANCHORS.items())
    if level <= points[0][0]:
        # below Lv. 60 no anchor is known: scale the Lv. 60 value linearly towards 0 at Lv. 0 (a rough guess)
        return points[0][1] * level / points[0][0], False
    for (l1, v1), (l2, v2) in zip(points, points[1:]):
        if l1 <= level <= l2:
            return v1 + (v2 - v1) * (level - l1) / (l2 - l1), False
    return points[-1][1], False


def def_multiplier(level: int, enemy_level: int, def_pen):
    """(L + 20) / ((Le + 20) x max(0, 1 - DEF ignore - DEF reduction) + L + 20). Fribbels fixes L = 80."""
    c = level + 20
    return c / ((enemy_level + 20) * np.maximum(0.0, 1.0 - def_pen) + c)


def res_multiplier(enemy_res: float, res_pen):
    """1 - (RES - RES PEN), with RES - RES PEN clamped to [-1, 0.9]."""
    return 1.0 - np.minimum(0.90, np.maximum(-1.0, enemy_res - res_pen))


def vuln_multiplier(vuln):
    return 1.0 + np.minimum(VULN_CAP, np.maximum(0.0, vuln))


def crit_multiplier(cr, cd):
    """Expected crit multiplier: CR clamped to at most 1 (Fribbels) and at least 0."""
    cr = np.minimum(1.0, np.maximum(0.0, cr))
    return cr * (1.0 + cd) + (1.0 - cr)


def common(level, enemy_level, enemy_res, broken: bool, def_pen, res_pen, vuln, final, true_dmg):
    """The multipliers every damage type shares: broken x DEF x RES x DMG taken x final x True DMG."""
    return ((1.0 if broken else 0.9) * def_multiplier(level, enemy_level, def_pen) * res_multiplier(enemy_res, res_pen)
            * vuln_multiplier(vuln) * (1.0 + final) * (1.0 + true_dmg))


def crit_damage(base, dmg_boost, cr, cd, mult):
    """Direct hits (Basic, Skill, Ultimate, Follow-up, memosprite) and Additional DMG: base x (1 + DMG%) x crit x common."""
    return base * (1.0 + dmg_boost) * crit_multiplier(cr, cd) * mult


def dot_chance(base_chance, ehr, enemy_effect_res, effect_res_pen, split=0.0, stacks=1.0):
    """Fribbels' expected DoT uptime from the chance to apply it."""
    p = np.minimum(1.0, base_chance * (1.0 + ehr) * (1.0 - enemy_effect_res + effect_res_pen))
    if split:
        return (1.0 + split * p * (stacks - 1.0)) / (1.0 + split * (stacks - 1.0))
    return p


def dot_damage(base, dmg_boost, chance, mult, tick=1.0):
    """DoT: no crit; base x (1 + DMG%) x apply chance x common x ticks."""
    return base * (1.0 + dmg_boost) * chance * mult * tick


def toughness_multiplier(max_toughness: float) -> float:
    """0.5 + max Toughness / 40, Toughness in displayed units (Fribbels stores it x3 and divides by 120)."""
    return 0.5 + max_toughness / 40.0


def break_damage(level_mult, element: str, max_toughness, be, break_boost, mult, special=1.0):
    """The Weakness Break hit: LvMult x element x Toughness term x (1 + BE) x (1 + Break DMG boost) x common."""
    return (level_mult * BREAK_ELEMENT[element] * toughness_multiplier(max_toughness) * special
            * (1.0 + be) * (1.0 + break_boost) * mult)


def super_break_damage(level_mult, toughness, break_eff, fixed_toughness, be, modifier, boost, mult):
    """Super Break: LvMult / 10 x Toughness reduced x (1 + BE) x Super Break multiplier x (1 + boost) x common."""
    reduced = (1.0 + break_eff) * toughness + fixed_toughness
    return (level_mult / 10.0) * reduced * (1.0 + be) * modifier * (1.0 + boost) * mult


def elation_damage(base, scaling, elation, merrymaking, punchline, cr, cd, mult, min_elation=0.0):
    """Elation DMG: base (2 x LvMult) x scaling x (1 + Elation) x (1 + Merrymaking) x (1 + 5P / (P + 240)) x crit
    x common. DMG% does not apply."""
    punch = 1.0 + 5.0 * punchline / (punchline + 240.0)
    return (base * scaling * (1.0 + np.maximum(elation, min_elation)) * (1.0 + merrymaking) * punch
            * crit_multiplier(cr, cd) * mult)


def expected_turns(spd, cycles: int = 5):
    """Own turns in Memory of Chaos, averaged over clears of 1 to `cycles` cycles: the first cycle is 150 action
    value long and every later one 100, a turn costs 10000 / SPD. Same model as bot/optimize.py turns(), but as a
    turn count rather than per 100 action value."""
    spd = np.asarray(spd, dtype=float)
    total = np.zeros_like(spd)
    for n in range(1, cycles + 1):
        length = 50 + 100 * n
        total = total + np.floor(length * spd / 10000 + 1e-9)
    return total / cycles
