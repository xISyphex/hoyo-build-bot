# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1400/Tribbie.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Tribbie."""

from ...model import DIRECT, Ability, CharacterDef, Effect, Eidolon, Hit, IfV, On, P, T, Tag, Tog, Toggle, Trace

ZONE = On("ultZone")
# The Zone's Additional DMG after each ally attack (E2: x1.2 and one more instance)
ZONE_ADD = P("ult", 2) * IfV(Eidolon(2) & On("e2AdditionalDmg"), 2.4, 1)


def zone(tick=1.0):
    return Hit("additional", Tag.ADDITIONAL, hp=ZONE_ADD, tick=tick, when=ZONE, label="Zone Additional DMG")


DEFINITION = CharacterDef(
    id="1403",
    name="Tribbie",
    source="src/lib/conditionals/character/1400/Tribbie.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, hp=P("basic", 0), toughness=10), zone()]),
        "skill": Ability("skill", []),  # Numinosity; no damage
        "ult": Ability("ult", [Hit("crit", Tag.ULT, hp=P("ult", 0), toughness=20), zone()]),
        "fua": Ability("fua", [Hit("crit", Tag.FUA, hp=P("talent", 0), toughness=5), zone()]),
        # Zone procs from the teammates' attacks
        "unique": Ability("unique", [zone(Tog("uniqueTickCoefficient"))], turn=False),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("dmg", T(1, 0) * Tog("talentFuaStacks"), when=Trace(1), source="Trace A2"),
        Effect("dmg", 7.29, tags=Tag.FUA, when=Eidolon(6) & On("e6FuaScaling"), source="E6"),
        Effect("hp", T(2, 0) * Tog("alliesMaxHp"), when=Trace(2) & ZONE, source="Trace A4"),
        Effect("res_pen", P("skill", 0), target="team", when=On("numinosity"), source="Skill"),
        Effect("vuln", P("ult", 1), target="team", when=ZONE, source="Ultimate"),
        Effect("true", 0.24, target="team", tags=DIRECT, when=Eidolon(1) & ZONE & On("e1TrueDmg"), source="E1"),
        Effect("def_pen", 0.18, target="team", when=Eidolon(4) & On("numinosity") & On("e4DefPen"), source="E4"),
    ],
    toggles=[
        Toggle("numinosity", default=1, text="Numinosity"),
        Toggle("ultZone", default=1, text="Ultimate Zone"),
        Toggle("alliesMaxHp", "slider", default=25000, max=100000, text="Sum of the allies' Max HP"),
        Toggle("talentFuaStacks", "slider", default=3, max=3, text="A2 DMG stacks"),
        Toggle("uniqueTickCoefficient", "slider", default=8, max=30, text="Zone procs from teammates per combo"),
        Toggle("e1TrueDmg", default=1, text="E1: True DMG"),
        Toggle("e2AdditionalDmg", default=1, text="E2: extra Zone DMG"),
        Toggle("e4DefPen", default=1, text="E4: DEF ignore"),
        Toggle("e6FuaScaling", default=1, text="E6: Follow-up DMG"),
    ],
    rotation=["skill", "ult", "fua", "basic", "fua", "fua", "unique"],
    notes=["Cyrene's special effect is not modelled."],
)
