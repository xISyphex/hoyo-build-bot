# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/KnightOfPurityPalace.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import SetDef

# Fribbels' 4pc +20% Shield is not ported: the engine has no Shield output.
DEFINITION = SetDef(
    id="103", name="Knight of Purity Palace",
    source="src/lib/sets/relics/KnightOfPurityPalace.ts",
    notes=["Knight of Purity Palace: the 4pc Shield bonus is not computed (no Shield output)."],
)
