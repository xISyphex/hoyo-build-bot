# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/SigoniaTheUnclaimedDesolation.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tog, Toggle

DEFINITION = SetDef(
    id="313", name="Sigonia, the Unclaimed Desolation",
    pieces={2: [Effect("cd", 0.04 * Tog("value"), source="Sigonia")]},
    toggles=[Toggle("value", "slider", default=4, max=10, text="Enemies defeated (stacks)")],
    source="src/lib/sets/ornaments/SigoniaTheUnclaimedDesolation.ts",
)
