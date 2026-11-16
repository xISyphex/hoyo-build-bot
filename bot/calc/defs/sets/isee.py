# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/AsNavigatorIseeSeesIt.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tag, Tog, Toggle

DEFINITION = SetDef(
    id="131", name="As Navigator Isee Sees It",
    pieces={4: [Effect("dmg", 0.18 * Tog("value"), tags=Tag.SKILL | Tag.ULT, source="Isee 4pc")]},
    toggles=[Toggle("value", "slider", default=1, max=3, text="Skill and Ultimate DMG stacks")],
    source="src/lib/sets/relics/AsNavigatorIseeSeesIt.ts",
)
