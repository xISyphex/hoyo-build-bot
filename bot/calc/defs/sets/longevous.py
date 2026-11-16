# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/LongevousDisciple.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tog, Toggle

DEFINITION = SetDef(
    id="113", name="Longevous Disciple",
    pieces={4: [Effect("cr", 0.08 * Tog("value"), source="Longevous 4pc")]},
    toggles=[Toggle("value", "slider", default=2, max=2, text="CRIT Rate stacks")],
    source="src/lib/sets/relics/LongevousDisciple.ts",
)
