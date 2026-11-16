# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/Misha.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Misha."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Min, On, P, T, Tag, Tog, Toggle, Trace

# Ultimate hits on the target, at most the Ultimate's hit limit; E4: +6% per hit
HITS = Min(Tog("ultHitsOnTarget"), P("ult", 4))
PER_HIT = P("ult", 1) + IfV(Eidolon(4), 0.06)

DEFINITION = CharacterDef(
    id="1312",
    name="Misha",
    source="src/lib/conditionals/character/1300/Misha.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=PER_HIT * HITS, toughness=10 + 5 * (HITS - 1))]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cd", T(3, 0), when=Trace(3) & On("enemyFrozen"), source="Trace A6"),
        # Fribbels counts E6 as Ice DMG Boost
        Effect("dmg_ice", 0.30, when=Eidolon(6) & On("e6UltDmgBoost"), as_teammate="main_only", source="E6"),
        Effect("def_pen", 0.16, target="team", when=Eidolon(2) & On("e2DefReduction"), source="E2"),
    ],
    toggles=[
        Toggle("ultHitsOnTarget", "slider", default=10, min=1, max=10, text="Ultimate hits on the target"),
        Toggle("enemyFrozen", default=1, text="A6: enemy Frozen"),
        Toggle("e2DefReduction", default=1, text="E2: DEF reduction"),
        Toggle("e6UltDmgBoost", default=1, text="E6: DMG"),
    ],
    rotation=["ult", "skill", "skill", "skill"],
)
