# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/RutilantArena.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast, Tag

DEFINITION = SetDef(
    id="309", name="Rutilant Arena",
    pieces={2: [Effect("dmg", 0.20, tags=Tag.BASIC | Tag.SKILL, when=StatAtLeast("cr", 0.70), source="Rutilant Arena")]},
    source="src/lib/sets/ornaments/RutilantArena.ts",
)
