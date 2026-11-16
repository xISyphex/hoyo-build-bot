# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/GuardOfWutheringSnow.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef

# 2pc: 8% DMG reduction (Fribbels multiplies DMG reductions; the engine adds them). The 4pc (healing and Energy) has
# no effect on damage.
DEFINITION = SetDef(
    id="106", name="Guard of Wuthering Snow",
    pieces={2: [Effect("dmg_red", 0.08, source="Guard 2pc")]},
    source="src/lib/sets/relics/GuardOfWutheringSnow.ts",
)
