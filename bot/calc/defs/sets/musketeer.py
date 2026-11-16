# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/MusketeerOfWildWheat.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tag

DEFINITION = SetDef(
    id="102", name="Musketeer of Wild Wheat",
    pieces={4: [Effect("dmg", 0.10, tags=Tag.BASIC, source="Musketeer 4pc")]},
    source="src/lib/sets/relics/MusketeerOfWildWheat.ts",
)
