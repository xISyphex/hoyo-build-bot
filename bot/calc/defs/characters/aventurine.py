# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/Aventurine.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Aventurine. Fribbels scores him by his shields and sorts his builds by Follow-up DMG; shields are not modelled, so
as the main character he is scored by his Talent's Follow-up ATK."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Min, On, P, Scale, T, Tag, Tog, Toggle,
                      Trace)

# Follow-up hits on the target, at most the Talent's hit count (E4: 3 more)
FUA_HITS = Min(Tog("fuaHitsOnTarget"), P("talent", 1) + IfV(Eidolon(4), 3))

DEFINITION = CharacterDef(
    id="1304",
    name="Aventurine",
    source="src/lib/conditionals/character/1300/Aventurine.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, def_=P("basic", 0), toughness=10)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, def_=P("ult", 1), toughness=30)]),
        # Fribbels: 10/3 Toughness per hit; no Ashblazing hit order
        "fua": Ability("fua", [Hit("crit", Tag.FUA, def_=P("talent", 2) * FUA_HITS, toughness=10 / 3 * FUA_HITS)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # A2: CRIT Rate +2% per 100 DEF above 1600, at most 48%
        Effect("cr", Scale("def", T(1, 0), above=T(1, 2), step=100, cap=T(1, 1)), when=Trace(1) & On("defToCrBoost"),
               as_teammate="main_only", source="Trace A2"),
        Effect("def%", 0.40, when=Eidolon(4) & On("e4DefBuff"), as_teammate="main_only", source="E4"),
        Effect("dmg", Min(1.50, 0.50 * Tog("e6ShieldStacks")), when=Eidolon(6), as_teammate="main_only",
               source="E6"),
        Effect("res", P("talent", 3), target="team", when=On("fortifiedWagerBuff"), source="Talent"),
        Effect("cd_boost", P("ult", 2), target="team", when=On("enemyUnnervedDebuff"), source="Ultimate"),
        Effect("cd", 0.20, target="team", when=Eidolon(1) & On("fortifiedWagerBuff"), source="E1"),
        Effect("res_pen", 0.12, target="team", when=Eidolon(2) & On("e2ResShred"), source="E2"),
    ],
    toggles=[
        Toggle("defToCrBoost", default=1, text="A2: DEF to CRIT Rate"),
        Toggle("fuaHitsOnTarget", "slider", default=10, max=10, text="Follow-up hits on the target (7, E4: 10)"),
        Toggle("fortifiedWagerBuff", default=1, text="Fortified Wager"),
        Toggle("enemyUnnervedDebuff", default=1, text="Enemy Unnerved"),
        Toggle("e2ResShred", default=1, text="E2: RES reduction"),
        Toggle("e4DefBuff", default=1, text="E4: DEF"),
        Toggle("e6ShieldStacks", "slider", default=3, max=3, text="E6: allies with a Shield"),
    ],
    rotation=["fua"],
    notes=["Shields are not modelled: as the main character he is scored by one Talent Follow-up ATK "
           "(Fribbels' sort), counted as one turn.",
           "The Follow-up hits are capped at the Talent's hit count (7, E4: 10)."],
)
