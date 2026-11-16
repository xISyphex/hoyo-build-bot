# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/SparkleB1.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Sparkle (reworked kit, Fribbels' 1306b1). As the main character she is scored by her Skill CRIT DMG buff (Fribbels'
support score). Fribbels' Sparkle.ts for the old kit has no effects, so only the reworked kit is defined. Eidolon
numbers come from the Fribbels file (the game data's eidolon text is the old kit's)."""

from ...model import Ability, CharacterDef, Effect, Eidolon, Hit, IfV, On, P, Scale, T, Tag, Tog, Toggle, Trace

SKILL = On("skillBuffs")
CIPHER = On("cipherBuff")
STACKS = Tog("talentStacks")
# Skill: CRIT DMG + 24% of Sparkle's CRIT DMG (E6: 30% more) + 45%
CD_SCALING = P("skill", 0) + IfV(Eidolon(6), 0.30)

DEFINITION = CharacterDef(
    id="1306b1",
    name="Sparkle",
    source="src/lib/conditionals/character/1300/SparkleB1.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "buff": Ability("buff", [Hit("buff", Tag.NONE, src="cd", ratio=CD_SCALING, flat=P("skill", 1),
                                     label="Skill CRIT DMG buff")], turn=False),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # Her Skill on herself: the flat part is unconvertible, the part from her CRIT DMG is a conversion
        Effect("cd", P("skill", 1), when=SKILL, as_teammate="main_only", unconvertible=True, source="Skill"),
        Effect("cd", Scale("cd", CD_SCALING), when=SKILL, as_teammate="main_only", source="Skill"),
        Effect("spd%", 0.15, when=Eidolon(1) & On("e1SpdBuff"), as_teammate="main_only", source="E1"),
        Effect("atk%", T(3, 0), target="team", when=Trace(3) & On("teamAtkBuff"), source="Trace A6"),
        Effect("atk%", 0.40, target="team", when=Eidolon(1) & CIPHER, source="E1"),
        # A6 RES PEN for the holder of the Skill buff (Fribbels: single target; herself as the main character)
        Effect("res_pen", T(3, 1), when=Trace(3) & SKILL, as_teammate="main_only", source="Trace A6"),
        Effect("res_pen", T(3, 1), target="ally", when=Trace(3) & SKILL, as_teammate="teammate_only",
               source="Trace A6"),
        Effect("vuln", STACKS * (P("talent", 1) + IfV(CIPHER, P("ult", 2))), target="team", source="Talent"),
        Effect("def_pen", 0.10 * STACKS, target="team", when=Eidolon(2) & On("e2DefPen"), source="E2"),
        # As a teammate her CRIT DMG is an input (teammateCDValue); the buff is not convertible. E6: whole team.
        Effect("cd", P("skill", 1) + CD_SCALING * Tog("teammateCDValue"), target="ally", when=SKILL & ~Eidolon(6),
               as_teammate="teammate_only", unconvertible=True, source="Skill"),
        Effect("cd", P("skill", 1) + CD_SCALING * Tog("teammateCDValue"), target="team", when=SKILL & Eidolon(6),
               as_teammate="teammate_only", unconvertible=True, source="Skill"),
    ],
    toggles=[
        Toggle("skillBuffs", default=0, teammate_default=1, text="Skill CRIT DMG buff"),
        Toggle("cipherBuff", default=1, text="Cipher"),
        Toggle("talentStacks", "slider", default=3, max=3, text="Talent stacks"),
        Toggle("teamAtkBuff", default=1, text="A6: team ATK"),
        Toggle("teammateCDValue", "slider", default=2.5, max=6, text="Sparkle's CRIT DMG (as a teammate)"),
        Toggle("e1SpdBuff", default=1, text="E1: SPD"),
        Toggle("e2DefPen", default=1, text="E2: DEF ignore"),
    ],
    rotation=["buff"],
    # Her Skill advances the ally's action by 50%
    advance=P("skill", 3),
    notes=["Her Skill Point and Energy effects are not modelled."],
)
