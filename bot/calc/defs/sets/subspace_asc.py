# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/SubspaceASCCenter.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

# All allies' Break Effect when the wearer has 145 SPD; cannot stack. Worn by a teammate, Fribbels counts it without
# checking the wearer's SPD.
DEFINITION = SetDef(
    id="330", name="Subspace ASC Center",
    pieces={2: [Effect("be", 0.18, target="team", when=StatAtLeast("spd", 145), source="Subspace ASC Center")]},
    team=[Effect("be", 0.18, target="team", source="Subspace ASC Center")],
    nonstackable=True,
    source="src/lib/sets/ornaments/SubspaceASCCenter.ts",
)
