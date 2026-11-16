# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/HunterOfGlacialForest.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="104", name="Hunter of Glacial Forest",
    pieces={4: [Effect("cd", 0.25, when=On("enabled"), source="Hunter 4pc")]},
    toggles=[Toggle("enabled", default=1, text="CRIT DMG after the Ultimate")],
    source="src/lib/sets/relics/HunterOfGlacialForest.ts",
)
