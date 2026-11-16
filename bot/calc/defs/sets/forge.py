# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/ForgeOfTheKalpagniLantern.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="316", name="Forge of the Kalpagni Lantern",
    pieces={2: [Effect("be", 0.40, when=On("enabled"), source="Forge")]},
    toggles=[Toggle("enabled", default=0, text="Hit a Fire-weak enemy")],
    source="src/lib/sets/ornaments/ForgeOfTheKalpagniLantern.ts",
)
