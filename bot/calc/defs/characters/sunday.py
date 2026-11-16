# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/Sunday.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Sunday. His buffs go to the ally he targets and their summon or memosprite. As the main character he is scored by
his Ultimate CRIT DMG buff (Fribbels' support score)."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, IfV, MainHasMemo, On, P, Tag, Tog, Toggle

SKILL = On("skillDmgBuff")

DEFINITION = CharacterDef(
    id="1313",
    name="Sunday",
    source="src/lib/conditionals/character/1300/Sunday.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        # The Beatified: CRIT DMG + 30% of Sunday's CRIT DMG + 12%
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="cd", ratio=P("ult", 1), flat=P("ult", 3),
                                     label="Ultimate CRIT DMG buff")], turn=False),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # Talent CRIT Rate: one stack before E6, three at E6
        Effect("cr", P("talent", 0) * Tog("talentCrBuff") * IfV(Eidolon(6), 3, 1), target="ally+memo",
               source="Talent"),
        Effect("dmg", P("skill", 1), target="ally+memo", when=SKILL, source="Skill"),
        Effect("dmg", P("skill", 3), target="ally+memo", when=SKILL & MainHasMemo(), source="Skill (summon)"),
        Effect("dmg", 0.50, target="ally+memo", when=On("techniqueDmgBuff"), source="Technique"),
        Effect("def_pen", 0.16, target="ally+memo", when=Eidolon(1) & SKILL & On("e1DefPen"), source="E1"),
        Effect("def_pen", 0.24, target="ally_memo", when=Eidolon(1) & SKILL & On("e1DefPen") & MainHasMemo(),
               source="E1 (summon)"),
        Effect("dmg", 0.30, target="ally+memo", when=Eidolon(2) & On("e2DmgBuff"), source="E2"),
        # As a teammate his CRIT DMG is an input (teammateCDValue); the buff is not convertible
        Effect("cd", P("ult", 1) * Tog("teammateCDValue") + P("ult", 3), target="ally+memo", when=On("beatified"),
               as_teammate="teammate_only", unconvertible=True, source="Ultimate"),
    ],
    toggles=[
        Toggle("skillDmgBuff", default=0, teammate_default=1, text="Skill DMG buff"),
        Toggle("talentCrBuff", default=0, teammate_default=1, text="Talent CRIT Rate (3 stacks at E6)"),
        Toggle("techniqueDmgBuff", default=0, text="Technique DMG"),
        Toggle("e1DefPen", default=0, teammate_default=1, text="E1: DEF ignore"),
        Toggle("e2DmgBuff", default=0, teammate_default=1, text="E2: Beatified DMG"),
        Toggle("beatified", default=1, text="The Beatified"),
        Toggle("teammateCDValue", "slider", default=2.5, max=6, text="Sunday's CRIT DMG (as a teammate)"),
    ],
    rotation=["buff"],
    advance=1.0,
    notes=["E6's CRIT Rate to CRIT DMG conversion for memosprites is not modelled."],
)
