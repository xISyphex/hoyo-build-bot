# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/BelobogOfTheArchitects.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="304", name="Belobog of the Architects",
    pieces={2: [Effect("def%", 0.15, when=StatAtLeast("ehr", 0.50), source="Belobog")]},
    source="src/lib/sets/ornaments/BelobogOfTheArchitects.ts",
)
