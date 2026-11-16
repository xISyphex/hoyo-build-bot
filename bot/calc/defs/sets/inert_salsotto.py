# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/InertSalsotto.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast, Tag

DEFINITION = SetDef(
    id="306", name="Inert Salsotto",
    pieces={2: [Effect("dmg", 0.15, tags=Tag.ULT | Tag.FUA, when=StatAtLeast("cr", 0.50), source="Inert Salsotto")]},
    source="src/lib/sets/ornaments/InertSalsotto.ts",
)
