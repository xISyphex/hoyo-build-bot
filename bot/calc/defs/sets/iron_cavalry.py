# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/IronCavalryAgainstTheScourge.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast, Tag

DEFINITION = SetDef(
    id="119", name="Iron Cavalry Against the Scourge",
    pieces={4: [Effect("def_pen", 0.10, tags=Tag.BREAK, when=StatAtLeast("be", 1.5), source="Iron Cavalry 4pc"),
                Effect("def_pen", 0.15, tags=Tag.SUPER_BREAK, when=StatAtLeast("be", 2.5), source="Iron Cavalry 4pc")]},
    source="src/lib/sets/relics/IronCavalryAgainstTheScourge.ts",
)
