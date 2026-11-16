# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/PanCosmicCommercialEnterprise.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, Scale, SetDef

# ATK% equal to 25% of the Effect Hit Rate, at most 25%.
DEFINITION = SetDef(
    id="303", name="Pan-Cosmic Commercial Enterprise",
    pieces={2: [Effect("atk%", Scale("ehr", 0.25, cap=0.25), source="Pan-Cosmic")]},
    source="src/lib/sets/ornaments/PanCosmicCommercialEnterprise.ts",
)
