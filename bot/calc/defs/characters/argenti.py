# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/Argenti.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Argenti. Skill 130214 is his 180-Energy Ultimate (Fribbels' ultEnhanced)."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Min, Not, On, P, T, Tag, Tog, Toggle,
                      Trace)

ENH = On("ultEnhanced")
ULT_180 = "{id}14"
# Apotheosis stacks, at most the Talent's limit (E4: 2 more)
STACKS = Min(Tog("talentStacks"), P("talent", 2) + IfV(Eidolon(4), 2))

DEFINITION = CharacterDef(
    id="1302",
    name="Argenti",
    source="src/lib/conditionals/character/1300/Argenti.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=10)]),
        "ult": Ability("ult", [
            Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20, when=Not(ENH)),
            # 180-Energy Ultimate: the AoE hit plus the extra hits on the target
            Hit("crit", Tag.ULT, atk=P("ult", 0, sid=ULT_180) + Tog("ultEnhancedExtraHits") * P("ult", 2, sid=ULT_180),
                toughness=20 + 5 * Tog("ultEnhancedExtraHits"), when=ENH),
        ]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cr", P("talent", 1) * STACKS, source="Talent"),
        Effect("dmg", T(3, 1), when=Trace(3) & On("enemyHp50"), source="Trace A6"),
        Effect("cd", 0.04 * STACKS, when=Eidolon(1), source="E1"),
        Effect("atk%", 0.40, when=Eidolon(2) & On("e2UltAtkBuff"), source="E2"),
        # Fribbels: E6 counted as DEF ignore on Ultimate hits
        Effect("def_pen", 0.30, tags=Tag.ULT, when=Eidolon(6), source="E6"),
    ],
    toggles=[
        Toggle("ultEnhanced", default=0, text="180-Energy Ultimate"),
        Toggle("talentStacks", "slider", default=12, max=12, text="Apotheosis stacks (10, E4: 12)"),
        Toggle("ultEnhancedExtraHits", "slider", default=6, max=6, text="180-Energy Ultimate extra hits on the target"),
        Toggle("e2UltAtkBuff", default=1, text="E2: ATK with 3 or more enemies"),
        Toggle("enemyHp50", default=1, text="A6: enemy at 50% HP or lower"),
    ],
    rotation=["ult", "skill", "ult", "ult", "skill", "ult", "skill"],
    notes=["Apotheosis stacks are capped at the Talent's limit (10, E4: 12)."],
)
