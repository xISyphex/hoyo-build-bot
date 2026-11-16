# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1300/BlackSwanB1.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Black Swan (reworked kit, Fribbels' 1307b1). Fribbels' BlackSwan.ts for the old kit has no effects, so only the
reworked kit is defined. Eidolon numbers come from the Fribbels file (the game data's eidolon text is the old kit's)."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, Min, On, P, Scale, T, Tag, Tog, TogAtLeast, Toggle,
                      Trace)

EPIPHANY = On("epiphanyDebuff")
# Arcana stacks: at most the Talent's limit (#8, 50) before E6, 80 at E6 (Fribbels' arcanaStackLimit)
LIMIT, E6_LIMIT = 50, 80


def _arcana_is(k: int):
    """The effective Arcana stack count is k (the slider is whole stacks)."""
    exact = TogAtLeast("arcanaStacks", k) & ~TogAtLeast("arcanaStacks", k + 1)
    if k < LIMIT:
        return exact
    if k == LIMIT:
        return TogAtLeast("arcanaStacks", k) & (~TogAtLeast("arcanaStacks", k + 1) | ~Eidolon(6))
    if k < E6_LIMIT:
        return Eidolon(6) & exact
    return Eidolon(6) & TogAtLeast("arcanaStacks", k)


# Arcana: one hit per stack count, because the stack count also sets the DoT chance split (dotStacks)
ARCANA = [Hit("dot", Tag.DOT, atk=P("talent", 0) + P("talent", 2) * k, dot_chance=P("talent", 1), dot_split=0.05,
              dot_stacks=float(k), tick=Tog("tickCoefficient"), when=_arcana_is(k), label="Arcana")
          for k in range(1, E6_LIMIT + 1)]

DEFINITION = CharacterDef(
    id="1307b1",
    name="Black Swan",
    source="src/lib/conditionals/character/1300/BlackSwanB1.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=20)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        "dot": Ability("dot", ARCANA),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # Talent: her DoT ignores 20% DEF
        Effect("def_pen", P("talent", 6), tags=Tag.DOT, as_teammate="main_only", source="Talent"),
        # A6: DMG = 60% of her Effect Hit Rate, at most 72% (Fribbels: read from her final EHR)
        Effect("dmg", Scale("ehr", T(3, 0), cap=T(3, 1), convertible=False), when=Trace(3) & On("ehrToDmgBoost"),
               as_teammate="main_only", source="Trace A6"),
        # As a teammate her Effect Hit Rate is an input (combatEhr)
        Effect("dmg", Min(T(3, 1), T(3, 0) * Tog("combatEhr")), target="team", when=Trace(3) & On("ehrToDmgBoost"),
               as_teammate="teammate_only", source="Trace A6"),
        Effect("def_pen", P("skill", 3), target="team", when=On("skillDefShred"), source="Skill"),
        *[Effect("res_pen", 0.25, target="team", element=el, when=Eidolon(1) & On("e1ResReduction"), source="E1")
          for el in ("Wind", "Fire", "Physical", "Lightning")],
        Effect("vuln", P("ult", 2), target="team", when=EPIPHANY, source="Ultimate"),
        Effect("vuln", 0.20, target="team", when=Eidolon(4) & EPIPHANY & On("e4Vulnerability"), source="E4"),
    ],
    toggles=[
        Toggle("tickCoefficient", "slider", default=2, max=10, text="DoT ticks counted per DoT entry"),
        Toggle("skillDefShred", default=1, text="Skill DEF reduction"),
        Toggle("epiphanyDebuff", default=1, text="Epiphany"),
        Toggle("arcanaStacks", "slider", default=80, min=1, max=80, text="Arcana stacks (50, E6: 80)"),
        Toggle("ehrToDmgBoost", default=1, text="A6: DMG from Effect Hit Rate"),
        Toggle("combatEhr", "slider", default=1.20, max=3, text="Black Swan's Effect Hit Rate (as a teammate)"),
        Toggle("e1ResReduction", default=1, text="E1: RES reduction"),
        Toggle("e4Vulnerability", default=1, text="E4: vulnerability"),
    ],
    rotation=["ult", "skill", "dot", "basic", "dot", "skill", "dot", "basic", "dot"],
    notes=["Arcana stacks are capped at 50 (E6: 80)."],
)
