# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/DrRatio.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Dr. Ratio."""

from ...model import (Ability, AshHit, CharacterDef, Effect, Eidolon, Hit, IfV, Min, On, P, T, Tag, Tog, TogAtLeast,
                      Toggle, Trace)

DEBUFFS = Tog("enemyDebuffStacks")
# A2 Summation stacks, at most the trace's limit (E1: 4 more)
SUMMATION = Min(Tog("summationStacks"), T(1, 2) + IfV(Eidolon(1), 4))

DEFINITION = CharacterDef(
    id="1305",
    name="Dr. Ratio",
    source="src/lib/conditionals/character/1300/DrRatio.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=30)]),
        "fua": Ability("fua", [
            Hit("crit", Tag.FUA, atk=P("talent", 0), toughness=10),
            # E2: 20% of ATK as Additional DMG per debuff, at most 4 times
            Hit("additional", Tag.ADDITIONAL, atk=0.20 * Min(4, DEBUFFS), when=Eidolon(2), label="E2 Additional DMG"),
        ], ashblazing=[AshHit("single", 1.0)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cr", T(1, 0) * SUMMATION, when=Trace(1), source="Trace A2"),
        Effect("cd", T(1, 1) * SUMMATION, when=Trace(1), source="Trace A2"),
        # A6: +10% DMG per debuff with 3 (A6's #1) or more debuffs, at most 50%
        Effect("dmg", Min(T(3, 2), T(3, 1) * DEBUFFS), when=Trace(3) & TogAtLeast("enemyDebuffStacks", 3),
               source="Trace A6"),
        Effect("dmg", 0.50, tags=Tag.FUA, when=Eidolon(6), source="E6"),
    ],
    toggles=[
        Toggle("enemyDebuffStacks", "slider", default=5, max=5, text="Debuffs on the enemy"),
        Toggle("summationStacks", "slider", default=10, max=10, text="A2 Summation stacks (6, E1: 10)"),
    ],
    rotation=["ult", "skill", "fua", "fua", "skill", "fua", "fua", "skill", "fua"],
    notes=["Summation stacks are capped at the trace's limit (6, E1: 10)."],
)
