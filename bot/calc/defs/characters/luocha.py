# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1200/Luocha.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Luocha. Fribbels' combo for him is a healing one (Skill heal, Talent heal), which the engine does not model; his
builds are sorted by SPD, so as the main character he is scored by his SPD."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, On, P, Tag, Toggle

DEFINITION = CharacterDef(
    id="1203",
    name="Luocha",
    source="src/lib/conditionals/character/1200/Luocha.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
        # Fribbels' sort option for Luocha: SPD
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="spd", ratio=1.0, label="SPD")], turn=False),
    },
    effects=[
        Effect("atk%", 0.20, target="team", when=Eidolon(1) & On("fieldActive"), source="E1"),
        Effect("res_pen", 0.20, target="team", when=Eidolon(6) & On("e6ResReduction"), source="E6"),
    ],
    toggles=[
        Toggle("fieldActive", default=1, text="Zone active (E1: team ATK)"),
        Toggle("e6ResReduction", default=1, text="E6: enemy All-Type RES reduction"),
    ],
    rotation=["buff"],
    notes=["His heals are not modelled; as the main character he is scored by SPD (Fribbels' sort)."],
)
