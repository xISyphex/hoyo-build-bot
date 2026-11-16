# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/SpaceSealingStation.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="301", name="Space Sealing Station",
    pieces={2: [Effect("atk%", 0.12, when=StatAtLeast("spd", 120), source="Space Sealing Station")]},
    source="src/lib/sets/ornaments/SpaceSealingStation.ts",
)
