# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/IzumoGenseiAndTakamaDivineRealm.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SamePath, SetDef, Toggle

DEFINITION = SetDef(
    id="314", name="Izumo Gensei and Takama Divine Realm",
    pieces={2: [Effect("cr", 0.12, when=On("enabled") & SamePath(2), source="Izumo")]},
    toggles=[Toggle("enabled", default=1, text="Ally of the same Path")],
    source="src/lib/sets/ornaments/IzumoGenseiAndTakamaDivineRealm.ts",
)
