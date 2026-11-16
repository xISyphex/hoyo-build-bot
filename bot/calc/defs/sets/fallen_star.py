# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/FallenStarAnchorage.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="327", name="Fallen Star Anchorage",
    pieces={2: [Effect("cd", 0.32, when=On("enabled"), source="Fallen Star Anchorage")]},
    toggles=[Toggle("enabled", default=1, text="Wearer and a teammate are Trailblaze Companions")],
    source="src/lib/sets/ornaments/FallenStarAnchorage.ts",
)
