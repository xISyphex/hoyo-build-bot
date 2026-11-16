# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/Acheron.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Acheron."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Not, On, P, T, Tag, TeamPath, Tog, Toggle,
                      Trace)

E6 = Eidolon(6) & On("e6UltBuffs")
# Ultimate: 3 Rainblades, 3 Crimson Knot removals plus one per knot stack, Stygian Resurge, and the A6 Thunder Core hits
ULT = (3 * P("ult", 0) + 3 * P("ult", 1) + P("ult", 1) * Tog("crimsonKnotStacks") + P("ult", 2)
       + Tog("stygianResurgeHitsOnTarget") * T(3, 4))
# A4 "The Abyss": DMG x1.15 / x1.60 with 1 / 2 other Nihility characters (E2: x1.60 with 1). With none, Fribbels
# counts nothing even at E2.
ABYSS = IfV(TeamPath("Nihility", 3), T(2, 1) - 1,
            IfV(TeamPath("Nihility", 2), IfV(Eidolon(2), T(2, 1) - 1, T(2, 0) - 1)))

DEFINITION = CharacterDef(
    id="1308",
    name="Acheron",
    source="src/lib/conditionals/character/1300/Acheron.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10, when=Not(E6)),
                                   Hit("crit", Tag.BASIC | Tag.ULT, atk=P("basic", 0), toughness=10, when=E6)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20, when=Not(E6)),
                                   Hit("crit", Tag.SKILL | Tag.ULT, atk=P("skill", 0), toughness=20, when=E6)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=ULT, toughness=35)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("cr_boost", 0.18, when=Eidolon(1) & On("e1EnemyDebuffed"), source="E1"),
        Effect("dmg", T(3, 0) * Tog("thunderCoreStacks"), when=Trace(3), source="Trace A6"),
        Effect("res_pen", P("talent", 1), actions=("ult",), source="Talent"),
        Effect("res_pen", 0.20, tags=Tag.ULT, when=E6, source="E6"),
        Effect("final", ABYSS, tags=Tag.BASIC | Tag.SKILL | Tag.ULT, when=Trace(2) & On("nihilityTeammatesBuff"),
               source="Trace A4"),
        Effect("vuln", 0.08, target="team", tags=Tag.ULT, when=Eidolon(4) & On("e4UltVulnerability"), source="E4"),
    ],
    toggles=[
        Toggle("crimsonKnotStacks", "slider", default=9, max=9, text="Crimson Knot stacks on the target"),
        Toggle("nihilityTeammatesBuff", default=1, text="A4: Nihility teammates"),
        Toggle("e1EnemyDebuffed", default=1, text="E1: enemy debuffed"),
        Toggle("thunderCoreStacks", "slider", default=3, max=3, text="A6 DMG stacks"),
        Toggle("stygianResurgeHitsOnTarget", "slider", default=6, max=6, text="A6 extra hits on the target"),
        Toggle("e4UltVulnerability", default=1, text="E4: Ultimate vulnerability"),
        Toggle("e6UltBuffs", default=1, text="E6: Ultimate RES PEN"),
    ],
    rotation=["ult", "ult", "skill", "ult"],
    notes=["Fribbels' combo has three Ultimates per Skill; damage per turn is the combo's total (no Slashed Dream "
           "model), so absolute numbers run high. Compare builds rather than reading the total."],
)
