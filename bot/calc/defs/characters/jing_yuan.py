# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/character/1200/JingYuan.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.
"""Jing Yuan. The Lightning-Lord's hits are Follow-up ATKs scaling with his ATK."""

from ...model import (Ability, AshHit, CharacterDef, Effect, Eidolon, Hit, Min, On, P, T, Tag, Tog, TogAtLeast,
                      Toggle, Trace)

# Lightning-Lord hits that land on the target (Fribbels' talentAttacks, at most 10 = the Talent's max Hits Per Action)
LL_HITS = Min(Tog("talentAttacks"), P("talent", 5))

DEFINITION = CharacterDef(
    id="1204",
    name="Jing Yuan",
    source="src/lib/conditionals/character/1200/JingYuan.ts",
    abilities={
        "basic": Ability("basic", [Hit("crit", Tag.BASIC, atk=P("basic", 0), toughness=10)]),
        "skill": Ability("skill", [Hit("crit", Tag.SKILL, atk=P("skill", 0), toughness=10)]),
        "ult": Ability("ult", [Hit("crit", Tag.ULT, atk=P("ult", 0), toughness=20)]),
        # Lightning-Lord: 66% per hit on the main target, 5 Toughness per hit. Ashblazing order for 10 hits (Fribbels:
        # 1 / 2 stacks before the first hit, +1 / +3 per hit with 1 / 3+ enemies, which is a blast hit's count)
        "fua": Ability("fua", [Hit("crit", Tag.FUA, atk=P("talent", 1) * LL_HITS, toughness=5 * LL_HITS,
                                   label="Lightning-Lord")],
                       ashblazing=[AshHit("blast", 1.0)] * 10),
        "break": Ability("break", [Hit("break", Tag.BREAK)]),
    },
    effects=[
        # A6 "War Marshal": CRIT Rate after the Skill
        Effect("cr", T(3, 0), when=Trace(3) & On("skillCritBuff"), source="Trace A6"),
        # A2 "Battalia Crush": Lightning-Lord CRIT DMG at 6 (T(1, 0)) or more Hits Per Action
        Effect("cd", T(1, 1), tags=Tag.FUA,
               when=Trace(1) & (TogAtLeast("talentHitsPerAction", 6) | TogAtLeast("talentAttacks", 6)),
               source="Trace A2"),
        Effect("dmg", 0.20, tags=Tag.BASIC | Tag.SKILL | Tag.ULT, when=Eidolon(2) & On("e2DmgBuff"), source="E2"),
        Effect("vuln", 0.12 * Tog("e6FuaVulnerabilityStacks"), tags=Tag.FUA, when=Eidolon(6), source="E6"),
    ],
    toggles=[
        Toggle("skillCritBuff", default=1, text="A6: CRIT Rate after the Skill"),
        Toggle("talentHitsPerAction", "slider", default=10, min=3, max=10, text="Lightning-Lord Hits Per Action"),
        Toggle("talentAttacks", "slider", default=10, max=10, text="Lightning-Lord hits on the target"),
        Toggle("e2DmgBuff", default=1, text="E2: Basic ATK, Skill and Ultimate DMG"),
        Toggle("e6FuaVulnerabilityStacks", "slider", default=3, max=3, text="E6: Vulnerability stacks"),
    ],
    rotation=["ult", "skill", "skill", "fua", "skill", "ult", "skill", "fua", "skill", "skill", "fua"],
    notes=["Ashblazing Grand Duke stacks are counted for 10 Lightning-Lord hits whatever the hit sliders say."],
)
