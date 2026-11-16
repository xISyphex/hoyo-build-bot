# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/ScholarLostInErudition.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Tag, Toggle

DEFINITION = SetDef(
    id="122", name="Scholar Lost in Erudition",
    pieces={4: [Effect("dmg", 0.20, tags=Tag.SKILL | Tag.ULT, source="Scholar 4pc"),
                Effect("dmg", 0.25, tags=Tag.SKILL, when=On("enabled"), source="Scholar 4pc (after the Ultimate)")]},
    toggles=[Toggle("enabled", default=1, text="Skill buff after the Ultimate")],
    source="src/lib/sets/relics/ScholarLostInErudition.ts",
)
