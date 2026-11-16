# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/WavestriderCaptain.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="126", name="Wavestrider Captain",
    pieces={4: [Effect("atk%", 0.48, when=On("enabled"), source="Wavestrider 4pc")]},
    toggles=[Toggle("enabled", default=1, text="ATK after the Ultimate (2 Help)")],
    source="src/lib/sets/relics/WavestriderCaptain.ts",
)
