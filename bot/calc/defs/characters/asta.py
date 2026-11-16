# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1000/Asta.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Asta. Fribbels has no combo or support score for her, so as the main character there is nothing to score; as a
teammate she gives her team buffs."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, On, P, T, Tag, TogAtLeast, Tog, Toggle, Trace

DEFINITION = CharacterDef(
    id="1009",
    name="Asta",
    source="src/lib/conditionals/character/1000/Asta.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        # A2 "Sparks": Burn equal to 50% of the Basic ATK's DMG, 80% base chance
        "dot": Ability("dot", [Hit("dot", Tag.DOT, atk=T(1, 2) * P("basic", 0), dot_chance=T(1, 0), when=Trace(1))]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("def%", T(3, 0) * Tog("talentBuffStacks"), when=Trace(3), as_teammate="main_only",
               source="Trace A6"),
        Effect("err", 0.15, when=Eidolon(4) & TogAtLeast("talentBuffStacks", 2), as_teammate="main_only",
               source="E4"),
        Effect("spd", P("ult", 0), target="team", when=On("ultSpdBuff"), source="Ultimate"),
        Effect("atk%", P("talent", 0) * Tog("talentBuffStacks"), target="team", source="Talent"),
        Effect("dmg_fire", T(2, 0), target="team", when=Trace(2) & On("fireDmgBoost"), source="Trace A4"),
    ],
    toggles=[
        Toggle("talentBuffStacks", "slider", default=5, max=5, text="Charging stacks"),
        Toggle("ultSpdBuff", default=1, text="Ultimate SPD buff"),
        Toggle("fireDmgBoost", default=1, text="A4: team Fire DMG"),
    ],
    rotation=[],
    notes=["Her Skill is not defined: its extra hits on random enemies are split by the enemy count, which a "
           "definition cannot read."],
)
