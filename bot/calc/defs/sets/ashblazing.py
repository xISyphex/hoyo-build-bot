# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/TheAshblazingGrandDuke.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tag

# The 4pc ATK% stacks are computed by the engine from each ability's hit order (Fribbels' ashblazingCompute).
DEFINITION = SetDef(
    id="115", name="The Ashblazing Grand Duke",
    pieces={2: [Effect("dmg", 0.20, tags=Tag.FUA, source="Ashblazing 2pc")]},
    source="src/lib/sets/relics/TheAshblazingGrandDuke.ts",
)
