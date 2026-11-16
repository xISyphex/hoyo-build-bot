# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/ChampionOfStreetwiseBoxing.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tog, Toggle

DEFINITION = SetDef(
    id="105", name="Champion of Streetwise Boxing",
    pieces={4: [Effect("atk%", 0.05 * Tog("value"), source="Champion 4pc")]},
    toggles=[Toggle("value", "slider", default=5, max=5, text="ATK stacks")],
    source="src/lib/sets/relics/ChampionOfStreetwiseBoxing.ts",
)
