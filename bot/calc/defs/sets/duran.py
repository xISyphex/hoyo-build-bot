# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/DuranDynastyOfRunningWolves.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tag, Tog, TogAtLeast, Toggle

DEFINITION = SetDef(
    id="315", name="Duran, Dynasty of Running Wolves",
    pieces={2: [Effect("dmg", 0.05 * Tog("value"), tags=Tag.FUA, source="Duran"),
                Effect("cd", 0.25, when=TogAtLeast("value", 5), source="Duran (5 Merit)")]},
    toggles=[Toggle("value", "slider", default=5, max=5, text="Merit stacks")],
    source="src/lib/sets/ornaments/DuranDynastyOfRunningWolves.ts",
)
