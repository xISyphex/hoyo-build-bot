# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/BandOfSizzlingThunder.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="109", name="Band of Sizzling Thunder",
    pieces={4: [Effect("atk%", 0.20, when=On("enabled"), source="Band 4pc")]},
    toggles=[Toggle("enabled", default=1, text="ATK after the Skill")],
    source="src/lib/sets/relics/BandOfSizzlingThunder.ts",
)
