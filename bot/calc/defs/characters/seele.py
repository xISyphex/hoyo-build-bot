# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1100/SeeleB1.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Seele (reworked kit, Fribbels' 1102b1)."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Min, On, P, T, Tag, Tog, Toggle, Trace)

E6 = Eidolon(6) & On("e6UltTargetDebuff")

DEFINITION = CharacterDef(
    id="1102b1",
    name="Seele",
    source="src/lib/conditionals/character/1100/SeeleB1.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10,
                                       # E6 "Butterfly Flurry": Fribbels adds 30% of the Ultimate's multiplier as True DMG
                                       true_dmg=IfV(E6, 0.30 * P("ult", 0) / P("basic", 0)))]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20,
                                       true_dmg=IfV(E6, 0.30 * P("ult", 0) / P("skill", 0)))]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=30, true_dmg=IfV(E6, 0.30))]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cr", 0.15, when=Eidolon(1) & On("e1EnemyHp80CrBoost"), source="E1"),
        Effect("def_pen", 0.20, when=Eidolon(1) & On("e1EnemyHp80CrBoost"), source="E1"),
        # Skill: SPD +25% per stack (2 stacks at E2)
        Effect("spd%", P("skill", 1) * Min(Tog("speedBoostStacks"), IfV(Eidolon(2), 2, 1)), source="Skill"),
        # A2 "Nightshade": DMG +50% per stack, 3 stacks
        Effect("dmg", T(1, 0) * Tog("dmgBoostStacks"), when=Trace(1), source="Trace A2"),
        # Talent: Amplification DMG boost
        Effect("dmg", P("talent", 0), when=On("buffedState"), source="Talent"),
        # A4 "Lacerate": Quantum RES PEN while Amplified
        Effect("res_pen", T(2, 0), element="Quantum", when=On("buffedState") & Trace(2), source="Trace A4"),
    ],
    toggles=[
        Toggle("buffedState", default=1, text="Amplification state"),
        Toggle("speedBoostStacks", "slider", default=2, max=2, text="Skill SPD stacks (2 needs E2)"),
        Toggle("dmgBoostStacks", "slider", default=3, max=3, text="A2 DMG stacks"),
        Toggle("e1EnemyHp80CrBoost", default=0, text="E1: enemy HP at or below 80%"),
        Toggle("e6UltTargetDebuff", default=1, text="E6: Butterfly Flurry on the target"),
    ],
    rotation=["ult", "skill", "skill", "skill", "skill"],
)
