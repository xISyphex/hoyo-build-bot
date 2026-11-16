# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1400/Aglaea.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Aglaea and her memosprite Garmentmaker. Skill 140208 is the enhanced Basic ATK ("Slash by a Thousandfold Kiss");
1140201 is Garmentmaker's skill and 1140203 its SPD talent."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Memo, Min, Not, On, P, Scale, StatAtLeast, T,
                      Tag, Tog, Toggle, Trace)

STANCE = On("supremeStanceState")
SEAM = On("seamStitch")
ENH_BASIC = "{id}08"
MEMO_SKILL = "1{id}01"
MEMO_SPD = "1{id}03"
E6 = Eidolon(6) & STANCE & On("e6Buffs")
# Garmentmaker SPD stacks: 6, 7 from E4
STACKS = Min(Tog("memoSpdStacks"), IfV(Eidolon(4), 7, 6))


def additional():
    return Hit("additional", Tag.ADDITIONAL, atk=P("talent", 0), when=SEAM, label="Seam Stitch Additional DMG")


DEFINITION = CharacterDef(
    id="1402",
    name="Aglaea",
    source="src/lib/conditionals/character/1400/Aglaea.ts",
    abilities={
        "basic": Ability("basic", [
            Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10, when=Not(STANCE)),
            Hit("crit", Tag.BASIC, atk=P("basic", 0, sid=ENH_BASIC), toughness=20, when=STANCE),
            Hit("crit", Tag.BASIC | Tag.MEMO, entity="memo", atk=P("basic", 2, sid=ENH_BASIC), when=STANCE,
                label="basic (Garmentmaker)"),
            additional(),
        ]),
        "ult": Ability("ult", [], turn=False),  # Supreme Stance; no damage
        "memo_skill": Ability("memo_skill", [Hit("crit", Tag.MEMO, entity="memo", atk=P("memo_skill", 0, sid=MEMO_SKILL),
                                                 toughness=10)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("spd%", P("ult", 0) * STACKS, when=STANCE, source="Ultimate"),
        Effect("spd", P("memo_talent", 0, sid=MEMO_SPD) * STACKS, target="memo",
               source="Garmentmaker talent"),
        # A2: ATK + 720% of Aglaea's SPD (+ 360% of Garmentmaker's SPD: only its flat SPD stacks are counted)
        Effect("atk", Scale("spd", T(1, 0), convertible=False), target="self+memo", when=Trace(1) & STANCE,
               unconvertible=True, source="Trace A2"),
        Effect("atk", T(1, 1) * P("memo_talent", 0, sid=MEMO_SPD) * STACKS, target="self+memo",
               when=Trace(1) & STANCE, unconvertible=True, source="Trace A2 (Garmentmaker SPD stacks)"),
        Effect("def_pen", 0.14 * Tog("e2DefShredStacks"), target="self+memo", when=Eidolon(2), source="E2"),
        Effect("res_pen", 0.20, target="self+memo", element="Lightning", when=E6, source="E6"),
        # E6: Joint ATK DMG +10% / 30% / 60% above 160 / 240 / 320 SPD (only Aglaea's SPD is checked here)
        Effect("dmg", 0.10, target="self+memo", tags=Tag.BASIC, when=E6 & StatAtLeast("spd", 160), source="E6"),
        Effect("dmg", 0.20, target="self+memo", tags=Tag.BASIC, when=E6 & StatAtLeast("spd", 240), source="E6"),
        Effect("dmg", 0.30, target="self+memo", tags=Tag.BASIC, when=E6 & StatAtLeast("spd", 320), source="E6"),
        Effect("vuln", 0.15, target="team", when=Eidolon(1) & SEAM & On("e1Vulnerability"), source="E1"),
    ],
    toggles=[
        Toggle("supremeStanceState", default=1, text="Supreme Stance"),
        Toggle("seamStitch", default=1, text="Seam Stitch on the target"),
        Toggle("memoSpdStacks", "slider", default=7, max=7, text="Garmentmaker SPD stacks (E4: 7)"),
        Toggle("e1Vulnerability", default=1, text="E1: DMG taken"),
        Toggle("e2DefShredStacks", "slider", default=3, min=1, max=3, text="E2: DEF ignore stacks"),
        Toggle("e6Buffs", default=1, text="E6: RES PEN and Joint ATK DMG"),
    ],
    rotation=["ult", "basic", "memo_skill", "memo_skill", "memo_skill", "basic", "basic", "memo_skill", "memo_skill",
              "memo_skill", "basic"],
    # Fribbels gives Garmentmaker no base ATK: its ATK is the A2 buff alone
    memo=Memo("Garmentmaker", spd_scale=0.35, summon=True),
    notes=["The A2 ATK buff counts Garmentmaker's SPD stacks but not its base SPD (35% of Aglaea's); E6's SPD "
           "thresholds read Aglaea's SPD only.",
           "Cyrene's special effect and the buff-priority switch are not modelled.",
           "Garmentmaker's actions come with the combo, not from its own SPD."],
)
