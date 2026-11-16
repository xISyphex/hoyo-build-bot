# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1000/KafkaB1.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Kafka (reworked kit, Fribbels' 1005b1)."""

from ...model import (Ability, AshHit, CharacterDef, Effect, Eidolon, Hit, IfV, On, P, StatAtLeast, T, Tag, Tog, Toggle,
                      Trace)

DEFINITION = CharacterDef(
    id="1005b1",
    name="Kafka",
    source="src/lib/conditionals/character/1000/KafkaB1.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        # Talent Follow-up ATK; Ashblazing order: 6 hits worth 15% x5 and 25%
        "fua": Ability("fua", [Hit("crit", Tag.FUA, atk=P("talent", 0), toughness=10)],
                       ashblazing=[AshHit("single", 0.15)] * 5 + [AshHit("single", 0.25)]),
        # Shock: the Ultimate's DoT multiplier (E6 adds 156%), counted tickCoefficient times per DoT entry
        "dot": Ability("dot", [Hit("dot", Tag.DOT, atk=P("ult", 3) + IfV(Eidolon(6), 1.56), dot_chance=1.0,
                                   tick=Tog("tickCoefficient"))]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # A2 "Torture": ATK +100% for an ally (the main character) with EHR >= 75%
        Effect("atk%", T(1, 1), target="team", when=Trace(1) & On("ehrBasedBuff") & StatAtLeast("ehr", 0.75),
               source="Trace A2"),
        Effect("vuln", 0.30, target="team", tags=Tag.DOT, when=Eidolon(1) & On("e1DotDmgReceivedDebuff"), source="E1"),
        Effect("dmg", 0.33, target="team", tags=Tag.DOT, when=Eidolon(2) & On("e2TeamDotDmg"), source="E2"),
    ],
    toggles=[
        Toggle("tickCoefficient", "slider", default=4, max=20, text="DoT ticks/detonations counted per DoT entry"),
        Toggle("ehrBasedBuff", default=1, text="A2: ATK buff at 75% EHR"),
        Toggle("e1DotDmgReceivedDebuff", default=1, text="E1: DoT vulnerability"),
        Toggle("e2TeamDotDmg", default=1, text="E2: team DoT DMG"),
    ],
    rotation=["ult", "dot", "skill", "dot", "fua", "skill", "dot", "fua", "skill", "dot", "fua"],
    notes=["Skill and Follow-up detonations are folded into the DoT tick count (Fribbels' tickCoefficient)."],
)
