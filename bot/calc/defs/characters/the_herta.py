# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1400/TheHerta.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""The Herta. Skill 140109 is the enhanced Skill ("Hear Me Out")."""

from ...model import (Ability, AshHit, CharacterDef, Call, Effect, Eidolon, Hit, IfV, Not, On, P, T, Tag, TeamPath,
                      Tog, TogAtLeast, Toggle, Trace)

ENH = On("enhancedSkill")
ENH_SKILL = "{id}09"
E1_STACKS = Eidolon(1) & On("e1BonusStacks")
# Erudition characters in the team, at most 2 (the Talent's per-stack bonus counts twice with 2 or more)
ERUDITION_MULT = IfV(On("eruditionTeammate"), Call(lambda ctx: min(2, ctx.team_path_count("Erudition")),
                                                   "min(2, Erudition characters)"), 1)
# Interpretation stacks counted by the enhanced Skill (E1: +50%)
STACKS = Tog("interpretationStacks") * IfV(E1_STACKS, 1.5, 1)
ENH_SCALING = (P("skill", 0, sid=ENH_SKILL) * 3 + P("talent", 0) * STACKS * ERUDITION_MULT
               + P("skill", 2, sid=ENH_SKILL))


def main_is_erudition(ctx) -> float:
    return 0.12 if ctx.team.paths[0] == "Erudition" else 0.0  # E4 literal


DEFINITION = CharacterDef(
    id="1401",
    name="The Herta",
    source="src/lib/conditionals/character/1400/TheHerta.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [
            Hit("crit", Tag.SKILL, atk=P("skill", 0) * 3, toughness=20, when=Not(ENH)),
            Hit("crit", Tag.SKILL, atk=ENH_SCALING, toughness=25, when=ENH),
        ]),
        # A6: +1% per Answer stack; E6: +400% against one enemy (Fribbels: 4.00 for one enemy, 1.40 otherwise)
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0) + T(3, 0) * Tog("totalInterpretationStacks")
                                   + IfV(Eidolon(6) & On("e6Buffs"), 4.00), toughness=20)],
                       ashblazing=[AshHit("aoe", 1.0)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("atk%", P("ult", 3), when=On("ultAtkBuff"), source="Ultimate"),
        # A2: at 42 Interpretation stacks (28 with E1's +50%)
        Effect("dmg", T(1, 1), tags=Tag.SKILL,
               when=Trace(1) & ENH & (TogAtLeast("interpretationStacks", 42)
                                      | (E1_STACKS & TogAtLeast("interpretationStacks", 28))),
               source="Trace A2"),
        Effect("res_pen", 0.20, element="Ice", when=Eidolon(6) & On("e6Buffs"), source="E6"),
        Effect("cd", T(2, 0), target="team", when=Trace(2) & On("eruditionTeammate") & TeamPath("Erudition", 2),
               source="Trace A4"),
        Effect("spd%", Call(main_is_erudition, "0.12 when the main character is Erudition"), target="team",
               when=Eidolon(4) & On("e4EruditionSpdBuff"), source="E4"),
    ],
    toggles=[
        Toggle("enhancedSkill", default=1, text="Enhanced Skill"),
        Toggle("eruditionTeammate", default=1, text="2+ Erudition characters in the team"),
        Toggle("ultAtkBuff", default=1, text="Ultimate ATK buff"),
        Toggle("interpretationStacks", "slider", default=42, min=1, max=42, text="Interpretation stacks (primary)"),
        Toggle("totalInterpretationStacks", "slider", default=99, min=1, max=99, text="A6 Answer stacks"),
        Toggle("e1BonusStacks", default=1, text="E1: extra Interpretation count"),
        Toggle("e4EruditionSpdBuff", default=1, text="E4: Erudition SPD"),
        Toggle("e6Buffs", default=1, text="E6: RES PEN and Ultimate multiplier"),
    ],
    rotation=["skill", "ult", "skill", "skill"],
    notes=["E6's Ultimate multiplier is counted for one enemy (+400%); the definitions can't read the enemy count."],
)
