# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1200/Qingque.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Qingque. Skill 120108 is the enhanced Basic ATK "Cherry on Top!" (Hidden Hand)."""

from ...model import (Ability, AshHit, CharacterDef, Effect, Eidolon, Hit, Not, On, P, T, Tag, Tog, Toggle, Trace)

ENH = On("basicEnhanced")
ENH_BASIC = "{v}{id}08"


def basic_hits(tags: Tag, when=None):
    # Fribbels counts the main target only: 100% / "Cherry on Top!" 240%
    w = (lambda c: c & when) if when is not None else (lambda c: c)
    return [Hit("crit", tags, atk=P("basic", 0), toughness=10, when=w(Not(ENH))),
            Hit("crit", tags, atk=P("basic", 0, sid=ENH_BASIC), toughness=20, when=w(ENH))]


DEFINITION = CharacterDef(
    id="1201",
    name="Qingque",
    source="src/lib/conditionals/character/1200/Qingque.ts",
    abilities={
        "basic": Ability("basic", basic_hits(Tag.BASIC)),
        "skill": Ability("skill", [], turn=False),  # draws tiles; the turn does not end
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        # E4 "Self-Sufficer": a Follow-up ATK copying the (enhanced) Basic ATK; Ashblazing order: one blast hit
        "fua": Ability("fua", basic_hits(Tag.FUA, Eidolon(4)), ashblazing=[AshHit("blast", 1.0)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("atk%", P("talent", 0), when=ENH, source="Talent"),
        # A6 "Winning Hand": SPD after the enhanced Basic ATK
        Effect("spd%", T(3, 0), when=Trace(3) & On("basicEnhancedSpdBuff"), source="Trace A6"),
        # Skill: DMG per stack, A4 "Bide Time" adds 10% per stack
        Effect("dmg", (P("skill", 1) + T(2, 0)) * Tog("skillDmgIncreaseStacks"), source="Skill"),
        Effect("dmg", 0.10, tags=Tag.ULT, when=Eidolon(1), source="E1"),
    ],
    toggles=[
        Toggle("basicEnhanced", default=1, text="Hidden Hand (enhanced Basic ATK)"),
        Toggle("basicEnhancedSpdBuff", default=0, text="A6: SPD after the enhanced Basic ATK"),
        Toggle("skillDmgIncreaseStacks", "slider", default=4, max=4, text="Skill DMG stacks"),
    ],
    rotation=["skill", "ult", "basic", "fua", "skill", "basic", "fua"],
    notes=["The E4 Follow-up ATK has a 24% chance; Fribbels counts it after every Basic ATK at E4."],
)
