# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1400/Castorice.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Castorice and her memosprite Netherwing. Skill 140709 is the enhanced Skill; 11407xx are Netherwing's abilities."""

from ...model import (Ability, CharacterDef, Effect, Eidolon, Hit, IfV, Memo, Not, On, P, T, Tag, Tog, TogAtLeast,
                      Toggle, Trace)

MEMO_ON = On("memospriteActive")
ENH_SKILL = "{id}09"
MEMO_SKILL = "1{id}02"
MEMO_TALENT = "1{id}06"
MEMO_TEAM = "1{id}05"
# "Breath Scorches the Shadow": 1st / 2nd / 3rd+ enhancement multipliers
BREATH = IfV(TogAtLeast("memoSkillEnhances", 3), P("memo_skill", 3, sid=MEMO_SKILL),
             IfV(TogAtLeast("memoSkillEnhances", 2), P("memo_skill", 2, sid=MEMO_SKILL), P("memo_skill", 1, sid=MEMO_SKILL)))
WINGS_HITS = Tog("memoTalentHits") + IfV(Eidolon(6), 3)

DEFINITION = CharacterDef(
    id="1407",
    name="Castorice",
    source="src/lib/conditionals/character/1400/Castorice.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, hp=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [
            Hit("crit", Tag.SKILL, hp=P("skill", 1), toughness=20, when=Not(MEMO_ON)),
            Hit("crit", Tag.SKILL, hp=P("skill", 1, sid=ENH_SKILL), toughness=20, when=MEMO_ON),
            Hit("crit", Tag.SKILL | Tag.MEMO, entity="memo", scale="self", hp=P("skill", 2, sid=ENH_SKILL),
                when=MEMO_ON, label="skill (Netherwing)"),
        ]),
        "ult": Ability("ult", [], turn=False),  # summons Netherwing; no damage
        "memo_skill": Ability("memo_skill", [Hit("crit", Tag.MEMO, entity="memo", scale="self", hp=BREATH,
                                                 toughness=10)]),
        "memo_talent": Ability("memo_talent", [Hit("crit", Tag.MEMO, entity="memo", scale="self",
                                                   hp=P("memo_talent", 0, sid=MEMO_TALENT) * WINGS_HITS,
                                                   toughness=5 * WINGS_HITS)]),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        Effect("spd%", T(2, 1), when=Trace(2) & On("spdBuff"), source="Trace A4"),
        Effect("dmg", P("talent", 1) * Tog("talentDmgStacks"), target="self+memo", source="Talent"),
        Effect("final", IfV(On("e1EnemyHp50"), 0.40, 0.20), target="memo", when=Eidolon(1), source="E1"),
        Effect("res_pen", 0.20, target="self+memo", element="Quantum", when=Eidolon(6) & On("e6Buffs"), source="E6"),
        Effect("dmg", T(3, 0) * Tog("memoDmgStacks"), target="memo", when=Trace(3), source="Trace A6"),
        Effect("res_pen", P("ult", 3), target="team", when=MEMO_ON, source="Ultimate"),
        Effect("dmg", P("memo_talent", 0, sid=MEMO_TEAM), target="team", when=On("teamDmgBoost"),
               source="Netherwing talent"),
    ],
    toggles=[
        Toggle("memospriteActive", default=1, text="Netherwing on the field"),
        Toggle("spdBuff", default=1, text="A4: SPD at 50% HP or more"),
        Toggle("talentDmgStacks", "slider", default=3, max=3, text="Talent DMG stacks"),
        Toggle("memoSkillEnhances", "slider", default=3, min=1, max=3, text="Breath Scorches the Shadow enhancement"),
        Toggle("memoTalentHits", "slider", default=6, max=6, text="Wings Sweep the Ruins bounces (E6 adds 3)"),
        Toggle("teamDmgBoost", default=1, text="Netherwing's team DMG buff"),
        Toggle("memoDmgStacks", "slider", default=3, max=6, text="A6 Netherwing DMG stacks"),
        Toggle("e1EnemyHp50", default=1, text="E1: enemy at 50% HP or lower"),
        Toggle("e6Buffs", default=1, text="E6: Quantum RES PEN"),
    ],
    rotation=["skill", "skill", "ult", "memo_skill", "memo_skill", "memo_skill", "memo_skill", "memo_talent"],
    memo=Memo("Netherwing", atk_scale=1.0, def_scale=1.0, hp_flat=34000, spd_flat=165, summon=True),
    notes=["Cyrene's special effect and the buff-priority switch are not modelled.",
           "Netherwing's actions come with the combo, not from its own SPD."],
)
