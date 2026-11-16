# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1000/DanHeng.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Dan Heng."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, IfV, On, P, T, Tag, Toggle, Trace

DEFINITION = CharacterDef(
    id="1002",
    name="Dan Heng",
    source="src/lib/conditionals/character/1000/DanHeng.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20)]),
        # Ultimate: the multiplier rises against a Slowed enemy
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0) + IfV(On("enemySlowed"), P("ult", 1)),
                                   toughness=30)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cr", 0.12, when=Eidolon(1) & On("e1EnemyHp50"), source="E1"),
        Effect("spd%", T(2, 1), when=Trace(2) & On("spdBuff"), source="Trace A4"),
        Effect("res_pen", P("talent", 0), element="Wind", when=On("talentPenBuff"), source="Talent"),
        Effect("dmg", T(3, 0), tags=Tag.BASIC, when=Trace(3) & On("enemySlowed"), source="Trace A6"),
    ],
    toggles=[
        Toggle("talentPenBuff", default=1, text="Talent: Wind RES PEN"),
        Toggle("enemySlowed", default=1, text="Enemy Slowed"),
        Toggle("spdBuff", default=1, text="A4: SPD after attacking"),
        Toggle("e1EnemyHp50", default=1, text="E1: enemy HP at or above 50%"),
    ],
    rotation=["skill", "ult", "skill", "skill"],
)
