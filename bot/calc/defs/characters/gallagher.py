# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/Gallagher.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Gallagher. Fribbels has no damage combo for him and sorts his builds by Break Effect, so as the main character he
is scored by his Break Effect. Skill 130108 is Nectar Blitz, the enhanced Basic ATK."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, Not, On, P, Scale, T, Tag, Toggle, Trace

ENH = On("basicEnhanced")
NECTAR_BLITZ = "{id}08"

DEFINITION = CharacterDef(
    id="1301",
    name="Gallagher",
    source="src/lib/conditionals/character/1300/Gallagher.ts",
    abilities={
        "basic": Ability("basic", [
            Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10, when=Not(ENH)),
            Hit("crit", Tag.BASIC, atk=P("basic", 0, sid=NECTAR_BLITZ), toughness=30, when=ENH),
        ]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
        # Fribbels' sort option for Gallagher: Break Effect
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="be", ratio=1.0, label="Break Effect")], turn=False),
    },
    effects=[
        # A2: Outgoing Healing = 50% of Break Effect, at most 75%
        Effect("ohb", Scale("be", T(1, 0), cap=T(1, 1)), when=Trace(1) & On("breakEffectToOhbBoost"),
               as_teammate="main_only", source="Trace A2"),
        Effect("res", 0.50, when=Eidolon(1) & On("e1ResBuff"), as_teammate="main_only", source="E1"),
        Effect("be", 0.20, when=Eidolon(6) & On("e6BeBuff"), as_teammate="main_only", source="E6"),
        Effect("break_eff", 0.20, when=Eidolon(6) & On("e6BeBuff"), as_teammate="main_only", source="E6"),
        Effect("res", 0.30, target="ally", when=Eidolon(2) & On("e2ResBuff"), as_teammate="teammate_only",
               source="E2"),
        # Besotted: enemies take more Break DMG
        Effect("vuln", P("talent", 0), target="team", tags=Tag.BREAK, when=On("targetBesotted"), source="Talent"),
    ],
    toggles=[
        Toggle("basicEnhanced", default=1, text="Nectar Blitz (enhanced Basic ATK)"),
        Toggle("breakEffectToOhbBoost", default=1, text="A2: Break Effect to Outgoing Healing"),
        Toggle("targetBesotted", default=1, text="Enemy Besotted"),
        Toggle("e1ResBuff", default=1, text="E1: Effect RES"),
        Toggle("e2ResBuff", default=0, text="E2: Effect RES for the Skill's target"),
        Toggle("e6BeBuff", default=1, text="E6: Break Effect and Break Efficiency"),
    ],
    rotation=["buff"],
    notes=["His heals are not modelled; as the main character he is scored by Break Effect (Fribbels' sort)."],
)
