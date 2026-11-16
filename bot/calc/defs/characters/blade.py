# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1200/BladeB1.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Blade (reworked kit, Fribbels' 1205b1). Skill 1120508 is the enhanced Basic ATK "Forest of Swords"."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Min, Not, On, P, T, Tag, Tog, Toggle, Trace)

ENH = On("enhancedStateActive")
FOREST = "{v}{id}08"
# Tally of HP loss, as a share of Max HP (capped at 90%)
TALLY = Min(Tog("hpPercentLostTotal"), P("ult", 6))
# E1: the Ultimate and the enhanced Basic ATK deal 150% of the tally more on the main target
E1 = IfV(Eidolon(1) & On("e1BasicUltMultiBoost"), 1.50 * TALLY)

DEFINITION = CharacterDef(
    id="1205b1",
    name="Blade",
    source="src/lib/conditionals/character/1200/BladeB1.ts",
    abilities={
        "basic": Ability("basic", [
            Hit("crit", Tag.BASIC, hp=P("basic", 0), toughness=10, when=Not(ENH)),
            Hit("crit", Tag.BASIC, hp=P("basic", 1, sid=FOREST) + E1, toughness=20, when=ENH),
        ]),
        "skill": Ability("skill", [], turn=False),  # enters Hellscape; the turn does not end
        "ult": Ability("ult", [Hit("crit", Tag.ULT, hp=P("ult", 0) + P("ult", 4) * TALLY + E1, toughness=20)]),
        # Talent Follow-up ATK; E6 adds 50% of Max HP
        "fua": Ability("fua", [Hit("crit", Tag.FUA, hp=P("talent", 1) + IfV(Eidolon(6), 0.50), toughness=10)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("dmg", P("skill", 3), when=ENH, source="Skill"),
        Effect("dmg", T(3, 0), tags=Tag.FUA, when=Trace(3), source="Trace A6"),
        Effect("cr", 0.15, when=Eidolon(2) & ENH & On("e2CrBuff"), source="E2"),
        Effect("hp%", 0.20 * Tog("e4MaxHpIncreaseStacks"), when=Eidolon(4), source="E4"),
    ],
    toggles=[
        Toggle("enhancedStateActive", default=1, text="Hellscape"),
        Toggle("hpPercentLostTotal", "slider", default=0.9, max=0.9, text="Tally of HP loss (share of Max HP)"),
        Toggle("e1BasicUltMultiBoost", default=1, text="E1: extra DMG from the HP loss tally"),
        Toggle("e2CrBuff", default=1, text="E2: CRIT Rate in Hellscape"),
        Toggle("e4MaxHpIncreaseStacks", "slider", default=2, max=2, text="E4: Max HP stacks"),
    ],
    rotation=["skill", "ult", "basic", "fua", "basic", "basic", "fua", "basic"],
)
