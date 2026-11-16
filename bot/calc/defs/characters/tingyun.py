# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1200/Tingyun.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Tingyun. Fribbels has no damage combo for her and sorts her builds by SPD, so as the main character she is scored
by her SPD."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Min, On, P, Scale, T, Tag, Tog, Toggle, Trace)

BENEDICTION = On("benedictionBuff")
# Benediction's Additional DMG: Skill 40% + Talent 60% of ATK, each +20% at E4
ADDITIONAL = P("skill", 0) + P("talent", 0) + IfV(Eidolon(4), 0.40)

DEFINITION = CharacterDef(
    id="1202",
    name="Tingyun",
    source="src/lib/conditionals/character/1200/Tingyun.ts",
    abilities={
        "basic": Ability("basic", [
            Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10),
            Hit("additional", Tag.ADDITIONAL, atk=ADDITIONAL, when=BENEDICTION, label="Benediction Additional DMG"),
        ]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
        # Fribbels' sort option for Tingyun: SPD
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="spd", ratio=1.0, label="SPD")], turn=False),
    },
    effects=[
        Effect("spd%", T(1, 0), when=Trace(1) & On("skillSpdBuff"), as_teammate="main_only", source="Trace A2"),
        Effect("dmg", T(2, 0), tags=Tag.BASIC, when=Trace(2), as_teammate="main_only", source="Trace A4"),
        # Benediction on herself: ATK + 25% of her ATK (Fribbels converts her convertible ATK)
        Effect("atk", Scale("atk", P("skill", 3)), when=BENEDICTION, as_teammate="main_only", source="Skill"),
        Effect("spd%", 0.20, target="ally", when=Eidolon(1) & On("ultSpdBuff"), source="E1"),
        Effect("dmg", P("ult", 2), target="ally", when=On("ultDmgBuff"), source="Ultimate"),
        # As a teammate: ATK% given by Benediction is an input (Fribbels' teammateAtkBuffValue), at most the Skill's 50%
        Effect("atk%", Min(Tog("teammateAtkBuffValue"), P("skill", 1)), target="ally", when=BENEDICTION,
               as_teammate="teammate_only", source="Skill"),
    ],
    toggles=[
        Toggle("benedictionBuff", default=0, teammate_default=1, text="Benediction"),
        Toggle("skillSpdBuff", default=0, text="A2: SPD after the Skill"),
        Toggle("ultSpdBuff", default=0, text="E1: SPD after the Ultimate (ally with Benediction)"),
        Toggle("ultDmgBuff", default=0, teammate_default=1, text="Ultimate DMG buff"),
        Toggle("teammateAtkBuffValue", "slider", default=0.55, max=0.55,
               text="Benediction ATK% on the carry (as a teammate; at most the Skill's value)"),
    ],
    rotation=["buff"],
    notes=["As the main character she is scored by SPD (Fribbels' sort); her damage is not the score."],
)
