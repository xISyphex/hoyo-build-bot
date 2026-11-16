# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1000/Herta.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Herta."""

from ...model import Ability, AshHit, CharacterDef, Effect, Eidolon, Hit, On, P, T, Tag, Tog, Toggle, Trace

DEFINITION = CharacterDef(
    id="1013",
    name="Herta",
    source="src/lib/conditionals/character/1000/Herta.ts",
    abilities={
        "basic": Ability("basic", [
            Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10),
            # E1: Ice Additional DMG equal to 40% of ATK against an enemy at or below 50% HP
            Hit("additional", Tag.ADDITIONAL, atk=0.40, when=Eidolon(1) & On("enemyHpLte50")),
        ]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=10)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        # Talent: one Follow-up ATK per stack, 5 Toughness each. Ashblazing order: Fribbels' default of 5 AoE hits
        "fua": Ability("fua", [Hit("crit", Tag.FUA, atk=P("talent", 1) * Tog("fuaStacks"),
                                   toughness=5 * Tog("fuaStacks"))],
                       ashblazing=[AshHit("aoe", 0.20)] * 5),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # Technique: ATK +40% (Fribbels' constant)
        Effect("atk%", 0.40, when=On("techniqueBuff"), source="Technique"),
        Effect("cr", 0.03 * Tog("e2TalentCritStacks"), when=Eidolon(2), source="E2"),
        Effect("atk%", 0.25, when=Eidolon(6) & On("e6UltAtkBuff"), source="E6"),
        Effect("dmg", P("skill", 2), tags=Tag.SKILL, when=On("enemyHpGte50"), source="Skill"),
        Effect("dmg", T(1, 0), tags=Tag.SKILL, when=Trace(1) & On("enemyHpGte50"), source="Trace A2"),
        Effect("dmg", T(3, 0), tags=Tag.ULT, when=Trace(3) & On("targetFrozen"), source="Trace A6"),
        Effect("dmg", 0.10, tags=Tag.FUA, when=Eidolon(4), source="E4"),
    ],
    toggles=[
        Toggle("fuaStacks", "slider", default=5, min=1, max=5, text="Talent Follow-up ATK stacks"),
        Toggle("targetFrozen", default=1, text="A6: target Frozen"),
        Toggle("enemyHpGte50", default=1, text="Skill: enemy HP at or above 50%"),
        Toggle("techniqueBuff", default=0, text="Technique ATK"),
        Toggle("enemyHpLte50", default=0, text="E1: enemy HP at or below 50%"),
        Toggle("e2TalentCritStacks", "slider", default=5, max=5, text="E2: CRIT Rate stacks"),
        Toggle("e6UltAtkBuff", default=1, text="E6: ATK after the Ultimate"),
    ],
    rotation=["ult", "fua", "skill", "fua", "skill", "fua"],
    notes=["The Ashblazing Grand Duke stack order always counts 5 Follow-up hits (Fribbels' default); fewer Talent "
           "stacks change only the damage, not the stack order."],
)
