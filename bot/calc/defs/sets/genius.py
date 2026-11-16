# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/GeniusOfBrilliantStars.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="108", name="Genius of Brilliant Stars",
    pieces={4: [Effect("def_pen", 0.10, source="Genius 4pc"),
                Effect("def_pen", 0.10, when=On("enabled"), source="Genius 4pc (Quantum Weakness)")]},
    toggles=[Toggle("enabled", default=1, text="Enemy has Quantum Weakness")],
    source="src/lib/sets/relics/GeniusOfBrilliantStars.ts",
)
