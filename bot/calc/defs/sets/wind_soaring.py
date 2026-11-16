# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/TheWindSoaringValorous.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Tag, Toggle

DEFINITION = SetDef(
    id="120", name="The Wind-Soaring Valorous",
    pieces={4: [Effect("dmg", 0.36, tags=Tag.ULT, when=On("enabled"), source="Wind-Soaring 4pc")]},
    toggles=[Toggle("enabled", default=0, text="Ultimate DMG after a Follow-Up ATK")],
    source="src/lib/sets/relics/TheWindSoaringValorous.ts",
)
