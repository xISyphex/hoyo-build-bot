# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/TaliaKingdomOfBanditry.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="307", name="Talia: Kingdom of Banditry",
    pieces={2: [Effect("be", 0.20, when=StatAtLeast("spd", 145), source="Talia")]},
    source="src/lib/sets/ornaments/TaliaKingdomOfBanditry.ts",
)
