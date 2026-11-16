# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/Robin.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Robin. As the main character she is scored by her Concerto ATK buff (Fribbels' support score)."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, On, P, T, Tag, Tog, Toggle, Trace

CONCERTO = On("concertoActive")

DEFINITION = CharacterDef(
    id="1309",
    name="Robin",
    source="src/lib/conditionals/character/1300/Robin.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        # Concerto: ATK + 22.8% of Robin's ATK + 200
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="atk", ratio=P("ult", 0), flat=P("ult", 2),
                                     label="Concerto ATK buff")], turn=False),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # Robin as a teammate: her own ATK is an input (teammateATKValue); the buff is not convertible
        Effect("atk", Tog("teammateATKValue") * P("ult", 0) + P("ult", 2), target="team", when=CONCERTO,
               as_teammate="teammate_only", unconvertible=True, source="Ultimate"),
        Effect("cd", T(2, 0), target="team", tags=Tag.FUA, when=Trace(2) & CONCERTO & On("traceFuaCdBoost"),
               as_teammate="teammate_only", source="Trace A4"),
        Effect("cd", P("talent", 0), target="team", when=On("talentCdBuff"), source="Talent"),
        Effect("dmg", P("skill", 0), target="team", when=On("skillDmgBuff"), source="Skill"),
        Effect("res_pen", 0.24, target="team", when=Eidolon(1) & CONCERTO & On("e1UltResPen"), source="E1"),
        Effect("spd%", 0.16, target="team", when=Eidolon(2) & CONCERTO & On("e2UltSpdBuff"), source="E2"),
        Effect("res", 0.50, target="team", when=Eidolon(4) & CONCERTO & On("e4TeamResBuff"), source="E4"),
    ],
    toggles=[
        Toggle("concertoActive", default=1, text="Concerto"),
        Toggle("skillDmgBuff", default=1, text="Skill DMG buff"),
        Toggle("talentCdBuff", default=1, text="Talent CRIT DMG buff"),
        Toggle("teammateATKValue", "slider", default=4500, max=20000, text="Robin's ATK (as a teammate)"),
        Toggle("traceFuaCdBoost", default=1, text="A4: Follow-up CRIT DMG"),
        Toggle("e1UltResPen", default=1, text="E1: RES PEN"),
        Toggle("e2UltSpdBuff", default=0, teammate_default=1, text="E2: SPD"),
        Toggle("e4TeamResBuff", default=0, teammate_default=1, text="E4: Effect RES"),
    ],
    rotation=["buff"],
    notes=["Her Ultimate's extra action for the team and her Additional DMG are not counted.",
           "As the main character her own ATK buffs are not added before the score is read."],
)
