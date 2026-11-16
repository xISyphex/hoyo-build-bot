# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/RuanMei.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Ruan Mei. As the main character she is scored by her A6 DMG buff from Break Effect (Fribbels' support score)."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, On, P, T, Tag, Tog, Toggle, Trace

DEFINITION = CharacterDef(
    id="1303",
    name="Ruan Mei",
    source="src/lib/conditionals/character/1300/RuanMei.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        # A6: DMG +6% per 10% Break Effect above 120%, at most 36%
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="be", above=1.2, step=0.1, per=0.06, cap=0.36,
                                     label="A6 DMG buff")], turn=False),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("be", T(1, 0), target="team", when=Trace(1) & On("teamBEBuff"), source="Trace A2"),
        Effect("dmg", P("skill", 0), target="team", when=On("skillOvertoneBuff"), source="Skill"),
        Effect("break_eff", P("skill", 1), target="team", when=On("skillOvertoneBuff"), source="Skill"),
        Effect("res_pen", P("ult", 0), target="team", when=On("ultFieldActive"), source="Ultimate"),
        Effect("def_pen", 0.20, target="team", when=Eidolon(1) & On("ultFieldActive"), source="E1"),
        Effect("spd%", P("talent", 0), target="team", when=On("teamSpdBuff"), as_teammate="teammate_only",
               source="Talent"),
        # As a teammate her A6 buff is an input (Fribbels' teamDmgBuff, default the 36% cap)
        Effect("dmg", Tog("teamDmgBuff"), target="team", when=Trace(3), as_teammate="teammate_only",
               source="Trace A6"),
        Effect("atk%", 0.40, target="team", when=Eidolon(2) & On("e2AtkBoost"), source="E2"),
        Effect("be", 1.00, when=Eidolon(4) & On("e4BeBuff"), as_teammate="main_only", source="E4"),
    ],
    toggles=[
        Toggle("skillOvertoneBuff", default=1, text="Overtone"),
        Toggle("teamBEBuff", default=1, text="A2: team Break Effect"),
        Toggle("ultFieldActive", default=1, text="Ultimate Zone"),
        Toggle("teamSpdBuff", default=1, text="Talent SPD (as a teammate)"),
        Toggle("teamDmgBuff", "slider", default=0.36, max=0.36, text="A6 DMG buff (as a teammate)"),
        Toggle("e2AtkBoost", default=0, text="E2: ATK vs Weakness Broken"),
        Toggle("e4BeBuff", default=0, text="E4: Break Effect"),
    ],
    rotation=["buff"],
    notes=["Her Talent and Ultimate Break DMG are not counted."],
)
