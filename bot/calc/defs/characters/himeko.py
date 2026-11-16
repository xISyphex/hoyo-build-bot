# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1000/Himeko.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Himeko."""

from ...model import Ability, AshHit, CharacterDef, Effect, Eidolon, Hit, On, P, T, Tag, Toggle, Trace

DEFINITION = CharacterDef(
    id="1003",
    name="Himeko",
    source="src/lib/conditionals/character/1000/Himeko.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        # Talent "Victory Rush": Ashblazing order 4 AoE hits worth 20% x3 and 40%
        "fua": Ability("fua", [Hit("crit", Tag.FUA, atk=P("talent", 0), toughness=10)],
                       ashblazing=[AshHit("aoe", 0.20)] * 3 + [AshHit("aoe", 0.40)]),
        # A2 "Starfire": Burn, 50% base chance
        "dot": Ability("dot", [Hit("dot", Tag.DOT, atk=T(1, 2), dot_chance=T(1, 0), when=Trace(1))]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cr", T(3, 1), when=Trace(3) & On("selfCurrentHp80Percent"), source="Trace A6"),
        Effect("spd%", 0.20, when=Eidolon(1) & On("e1TalentSpdBuff"), source="E1"),
        Effect("dmg", T(2, 0), tags=Tag.SKILL, when=Trace(2) & On("targetBurned"), source="Trace A4"),
        Effect("dmg", 0.15, when=Eidolon(2) & On("e2EnemyHp50DmgBoost"), source="E2"),
    ],
    toggles=[
        Toggle("targetBurned", default=1, text="A4: target Burned"),
        Toggle("selfCurrentHp80Percent", default=1, text="A6: HP at or above 80%"),
        Toggle("e1TalentSpdBuff", default=0, text="E1: SPD after Victory Rush"),
        Toggle("e2EnemyHp50DmgBoost", default=1, text="E2: enemy HP at or below 50%"),
    ],
    rotation=["ult", "fua", "skill", "fua", "skill", "break", "fua"],
    notes=["E6's two extra Ultimate hits on random enemies are not counted (Fribbels splits them by the enemy "
           "count, which a definition cannot read)."],
)
