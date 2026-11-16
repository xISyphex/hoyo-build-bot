# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/EverGloriousMagicalGirl.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tag, Tog, Toggle

DEFINITION = SetDef(
    id="129", name="Ever-Glorious Magical Girl",
    pieces={4: [Effect("def_pen", 0.10 + 0.01 * Tog("value"), target="self+memo", tags=Tag.ELATION,
                       source="Magical Girl 4pc")]},
    toggles=[Toggle("value", "slider", default=10, max=10, text="Stacks (5 Punchline each)")],
    source="src/lib/sets/relics/EverGloriousMagicalGirl.ts",
)
