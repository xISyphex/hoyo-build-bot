# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1200/Yukong.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Yukong. Fribbels has no damage combo for her and sorts her builds by Ultimate DMG, so as the main character she is
scored by her Ultimate."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, On, P, T, Tag, Toggle, Trace

BOWSTRINGS = On("roaringBowstringsActive")

DEFINITION = CharacterDef(
    id="1207",
    name="Yukong",
    source="src/lib/conditionals/character/1200/Yukong.ts",
    abilities={
        # Basic ATK with the Talent's extra 80%
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0) + P("talent", 0), toughness=10)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=30)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("dmg", 0.30, when=Eidolon(4) & BOWSTRINGS, as_teammate="main_only", source="E4"),
        Effect("atk%", P("skill", 1), target="team", when=BOWSTRINGS, source="Skill"),
        Effect("cr", P("ult", 1), target="team", when=On("ultBuff") & BOWSTRINGS, source="Ultimate"),
        Effect("cd", P("ult", 2), target="team", when=On("ultBuff") & BOWSTRINGS, source="Ultimate"),
        Effect("spd%", 0.10, target="team", when=Eidolon(1) & On("initialSpeedBuff"), source="E1"),
        Effect("dmg_imaginary", T(2, 0), target="team", when=Trace(2) & On("teamImaginaryDmgBoost"),
               source="Trace A4"),
    ],
    toggles=[
        Toggle("teamImaginaryDmgBoost", default=1, text="A4: team Imaginary DMG"),
        Toggle("roaringBowstringsActive", default=1, text="Roaring Bowstrings"),
        Toggle("ultBuff", default=1, text="Ultimate CRIT buffs"),
        Toggle("initialSpeedBuff", default=1, text="E1: SPD at battle start"),
    ],
    rotation=["ult"],
    notes=["As the main character she is scored by her Ultimate (Fribbels' sort); Fribbels has no combo for her.",
           "The Ultimate's CRIT buffs follow the Ultimate's level (Fribbels reads them at the Skill's level)."],
)
