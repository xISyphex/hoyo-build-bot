# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1400/Mydei.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Mydei. Skills 140409 ("Kingslayer Be King") and 140411 ("Godslayer Be God") are his Vendetta Skills."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, On, P, Scale, T, Tag, TogAtLeast, Toggle,
                      Trace)

VENDETTA = On("vendettaState")
GODSLAYER = TogAtLeast("skillEnhances", 2)
KINGSLAYER = TogAtLeast("skillEnhances", 1) & ~GODSLAYER
# E1: +30% multiplier for "Godslayer Be God" (literal)
SKILL_SCALING = IfV(GODSLAYER, P("skill", 0, sid="{id}11") + IfV(Eidolon(1) & On("e1EnhancedSkillBuff"), 0.30),
                    IfV(KINGSLAYER, P("skill", 0, sid="{id}09"), P("skill", 0)))

DEFINITION = CharacterDef(
    id="1404",
    name="Mydei",
    source="src/lib/conditionals/character/1400/Mydei.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, hp=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, hp=SKILL_SCALING, toughness=IfV(GODSLAYER, 30, 20))]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, hp=P("ult", 0), toughness=20)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # Vendetta: Max HP +50% of the current Max HP
        Effect("hp", Scale("hp", P("talent", 4)), when=VENDETTA, source="Talent"),
        # A6: CRIT Rate +1.2% per 100 Max HP above 4000, counting at most 4000 excess HP (step of 100 from the text)
        Effect("cr", Scale("hp", T(3, 2), above=T(3, 0), step=100, cap=T(3, 2) * T(3, 1) / 100),
               when=Trace(3) & On("hpToCrConversion"), unconvertible=True, source="Trace A6"),
        Effect("def_pen", 0.15, when=Eidolon(2) & On("e2DefPen") & VENDETTA, source="E2"),
        Effect("cd", 0.30, when=Eidolon(4) & On("e4CdBuff"), source="E4"),
    ],
    toggles=[
        Toggle("skillEnhances", "select", default=2, max=2, text="Skill used",
               options={0: "Skill", 1: "Kingslayer Be King", 2: "Godslayer Be God"}),
        Toggle("vendettaState", default=1, text="Vendetta"),
        Toggle("hpToCrConversion", default=1, text="A6: HP to CRIT Rate"),
        Toggle("e1EnhancedSkillBuff", default=1, text="E1: Godslayer Be God multiplier"),
        Toggle("e2DefPen", default=1, text="E2: DEF ignore"),
        Toggle("e4CdBuff", default=1, text="E4: CRIT DMG"),
    ],
    rotation=["ult", "skill", "skill"],
    notes=["A6 uses the game data's numbers (1.2% CRIT Rate per 100 HP above 4000, at most 48%); Fribbels has 1.6% "
           "per 100 HP above 5000 (same cap). It reads Max HP before the Vendetta bonus but after combat HP buffs.",
           "Vendetta's DEF of 0 is not modelled (no hit scales with DEF). Cyrene's special effect is not modelled."],
)
