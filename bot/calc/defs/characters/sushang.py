# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1200/Sushang.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Sushang."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Min, On, P, T, Tag, Tog, TogAtLeast, Toggle,
                      Trace)

ULT_BUFF = On("ultBuffedState")
# Sword Stance: one 100% hit, plus two at 50% of it (the Ultimate's extra chances) while the Ultimate is active
STANCE = (IfV(TogAtLeast("skillExtraHits", 1), P("skill", 1))
          + IfV(ULT_BUFF & TogAtLeast("skillExtraHits", 2), P("skill", 1) * P("ult", 2))
          + IfV(ULT_BUFF & TogAtLeast("skillExtraHits", 3), P("skill", 1) * P("ult", 2)))

DEFINITION = CharacterDef(
    id="1206",
    name="Sushang",
    source="src/lib/conditionals/character/1200/Sushang.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [
            Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20),
            Hit("additional", Tag.ADDITIONAL, atk=STANCE, when=TogAtLeast("skillExtraHits", 1), label="Sword Stance"),
        ]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=30)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("be", 0.40, when=Eidolon(4), source="E4"),
        Effect("atk%", P("ult", 3), when=ULT_BUFF, source="Ultimate"),
        # Talent SPD per stack: 1 stack, 2 at E6
        Effect("spd%", P("talent", 0) * Min(Tog("talentSpdBuffStacks"), IfV(Eidolon(6), 2, 1)), source="Talent"),
        # A4 "Riposte": Sword Stance DMG per trigger, at most 10 stacks
        Effect("dmg", T(2, 0) * Min(Tog("skillTriggerStacks"), T(2, 1)), tags=Tag.ADDITIONAL, when=Trace(2),
               source="Trace A4"),
    ],
    toggles=[
        Toggle("ultBuffedState", default=1, text="Ultimate buff"),
        Toggle("skillExtraHits", "slider", default=3, max=3, text="Sword Stance triggers per Skill"),
        Toggle("skillTriggerStacks", "slider", default=10, max=10, text="A4: Sword Stance DMG stacks"),
        Toggle("talentSpdBuffStacks", "slider", default=2, max=2, text="Talent SPD stacks (2 needs E6)"),
        Toggle("e2DmgReductionBuff", default=1, text="E2: DMG reduction (not counted: does not change damage dealt)"),
    ],
    rotation=["skill", "ult", "break", "skill", "skill", "skill"],
    notes=["The E2 DMG reduction is not counted (it does not change damage dealt)."],
)
