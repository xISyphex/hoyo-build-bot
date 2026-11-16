# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1100/Bronya.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Bronya. As the main character she is scored by her Ultimate CRIT DMG buff (Fribbels' support score)."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, On, P, T, Tag, Tog, Toggle, Trace

DEFINITION = CharacterDef(
    id="1101",
    name="Bronya",
    source="src/lib/conditionals/character/1100/Bronya.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        # Ultimate: CRIT DMG + 16% of Bronya's CRIT DMG + 20%
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="cd", ratio=P("ult", 1), flat=P("ult", 2),
                                     label="Ultimate CRIT DMG buff")], turn=False),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cr", 1.00, tags=Tag.BASIC, when=Trace(1), as_teammate="main_only", source="Trace A2"),
        Effect("def%", T(2, 1), target="team", when=Trace(2) & On("battleStartDefBuff"), source="Trace A4"),
        Effect("atk%", 0.15, target="team", when=On("techniqueBuff"), source="Technique"),
        Effect("atk%", P("ult", 0), target="team", when=On("ultBuff"), source="Ultimate"),
        Effect("dmg", T(3, 0), target="team", when=Trace(3) & On("teamDmgBuff"), source="Trace A6"),
        Effect("spd%", 0.30, target="ally", when=Eidolon(2) & On("e2SkillSpdBuff"), source="E2"),
        Effect("dmg", P("skill", 0), target="ally", when=On("skillBuff"), source="Skill"),
        # As a teammate her CRIT DMG is an input (teammateCDValue); the buff is not convertible
        Effect("cd", P("ult", 1) * Tog("teammateCDValue") + P("ult", 2), target="team", when=On("ultBuff"),
               as_teammate="teammate_only", unconvertible=True, source="Ultimate"),
    ],
    toggles=[
        Toggle("teamDmgBuff", default=1, text="A6: team DMG"),
        Toggle("skillBuff", default=1, text="Skill DMG buff"),
        Toggle("ultBuff", default=1, text="Ultimate buffs"),
        Toggle("battleStartDefBuff", default=0, text="A4: DEF at battle start"),
        Toggle("techniqueBuff", default=0, text="Technique ATK"),
        Toggle("e2SkillSpdBuff", default=0, teammate_default=1, text="E2: SPD after the Skill"),
        Toggle("teammateCDValue", "slider", default=2.5, max=6, text="Bronya's CRIT DMG (as a teammate)"),
    ],
    rotation=["buff"],
    advance=1.0,
)
