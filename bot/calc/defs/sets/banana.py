# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/TheWondrousBananAmusementPark.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, MainHasMemo, On, SetDef, Toggle

DEFINITION = SetDef(
    id="318", name="The Wondrous BananAmusement Park",
    pieces={2: [Effect("cd", 0.32, when=On("enabled") & MainHasMemo(), source="BananAmusement Park")]},
    toggles=[Toggle("enabled", default=0, text="Summon on the field")],
    source="src/lib/sets/ornaments/TheWondrousBananAmusementPark.ts",
)
