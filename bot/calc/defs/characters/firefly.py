# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/FireflyB1.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Firefly (reworked kit, Fribbels' 1310b1). Skill ids 1131008/1131009 are the enhanced Basic ATK and Skill."""

from ...model import (Ability, Broken, CharacterDef, Effect, Eidolon, Hit, Not, On, P, Scale, StatAtLeast, T, Tag,
                      Toggle, Trace)

ENH = On("enhancedStateActive")
SUPER = ENH & On("superBreakDmg")
ENH_BASIC = "{v}{id}08"
ENH_SKILL = "{v}{id}09"

DEFINITION = CharacterDef(
    id="1310b1",
    name="Firefly",
    source="src/lib/conditionals/character/1300/FireflyB1.ts",
    abilities={
        "basic": Ability("basic", [
            Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10, when=Not(ENH)),
            Hit("crit", Tag.BASIC, atk=P("basic", 0, sid=ENH_BASIC), toughness=15, when=ENH),
            Hit("super_break", Tag.SUPER_BREAK, toughness=15, when=SUPER, label="basic (Super Break)"),
        ]),
        "skill": Ability("skill", [
            Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20, when=Not(ENH)),
            # (0.2 x Break Effect + 200%) of ATK, Break Effect capped at 360%
            Hit("crit", Tag.SKILL, atk=P("skill", 0, sid=ENH_SKILL), be_atk=P("skill", 4, sid=ENH_SKILL), be_cap=3.6,
                toughness=30, when=ENH),
            Hit("super_break", Tag.SUPER_BREAK, toughness=30, when=SUPER, label="skill (Super Break)"),
        ]),
        "ult": Ability("ult", [], turn=False),  # enters Complete Combustion; no damage
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("res", P("talent", 3), when=ENH, source="Talent"),
        Effect("spd", P("ult", 2), when=ENH & On("enhancedStateSpdBuff"), source="Ultimate"),
        Effect("break_eff", P("ult", 1), when=ENH, source="Ultimate"),
        Effect("vuln", P("ult", 0), tags=Tag.BREAK | Tag.SUPER_BREAK, when=ENH & Broken(), source="Ultimate"),
        Effect("be", T(1, 0), when=ENH & Trace(1), source="Trace A2"),
        # A4: Super Break at 150% / 300% Break Effect (Fribbels: +1.0, then +0.5 more)
        Effect("super_break", T(2, 2), when=SUPER & Trace(2) & StatAtLeast("be", 1.5), source="Trace A4"),
        Effect("super_break", T(2, 3) - T(2, 2), when=SUPER & Trace(2) & StatAtLeast("be", 3.0), source="Trace A4"),
        # A6: BE +0.8% per 10 ATK above 1800
        Effect("be", Scale("atk", T(3, 2), above=T(3, 0), step=T(3, 1)), when=Trace(3) & On("atkToBeConversion"),
               source="Trace A6"),
        Effect("def_pen", 0.15, when=Eidolon(1) & ENH & On("e1DefShred"), source="E1"),
        Effect("res", 0.50, when=Eidolon(4) & ENH & On("e4ResBuff"), source="E4"),
        Effect("res_pen", 0.20, element="Fire", when=Eidolon(6) & ENH & On("e6Buffs"), source="E6"),
        Effect("break_eff", 0.50, when=Eidolon(6) & ENH & On("e6Buffs"), source="E6"),
    ],
    toggles=[
        Toggle("enhancedStateActive", default=1, text="Complete Combustion"),
        Toggle("enhancedStateSpdBuff", default=1, text="Complete Combustion SPD"),
        Toggle("superBreakDmg", default=1, text="Super Break (enemy Weakness Broken)"),
        Toggle("atkToBeConversion", default=1, text="A6: ATK to Break Effect"),
        Toggle("e1DefShred", default=1, text="E1: DEF ignore"),
        Toggle("e4ResBuff", default=1, text="E4: Effect RES"),
        Toggle("e6Buffs", default=1, text="E6: RES PEN and Break Efficiency"),
    ],
    rotation=["ult", "skill", "break", "skill", "skill", "skill"],
    broken_when=On("superBreakDmg"),
    notes=["The Talent's DMG reduction is not counted (it does not change damage dealt)."],
)
