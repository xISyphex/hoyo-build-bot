# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1000/Arlan.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Arlan."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, Min, P, Tag, TogAtLeast, Tog, Toggle

# HP at or below 50% (the slider moves in steps of 1%)
HP_HALF = ~TogAtLeast("selfCurrentHpPercent", 0.505)

DEFINITION = CharacterDef(
    id="1008",
    name="Arlan",
    source="src/lib/conditionals/character/1000/Arlan.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 1), toughness=20)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # Talent: Fribbels counts DMG = missing HP share, at most the Talent's maximum
        Effect("dmg", Min(P("talent", 0), 1 - Tog("selfCurrentHpPercent")), source="Talent"),
        Effect("dmg", 0.10, tags=Tag.SKILL, when=Eidolon(1) & HP_HALF, source="E1"),
        Effect("dmg", 0.20, tags=Tag.ULT, when=Eidolon(6) & HP_HALF, source="E6"),
    ],
    toggles=[
        Toggle("selfCurrentHpPercent", "slider", default=1.0, min=0.01, max=1.0, text="Arlan's current HP %"),
    ],
    rotation=["ult", "skill", "skill", "skill"],
)
