# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/GiantTreeOfRaptBrooding.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="320", name="Giant Tree of Rapt Brooding",
    pieces={2: [Effect("ohb", 0.12, target="self+memo", when=StatAtLeast("spd", 135), source="Giant Tree (SPD 135)"),
                Effect("ohb", 0.08, target="self+memo", when=StatAtLeast("spd", 180), source="Giant Tree (SPD 180)")]},
    source="src/lib/sets/ornaments/GiantTreeOfRaptBrooding.ts",
)
