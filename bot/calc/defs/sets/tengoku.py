# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/TengokuLivestream.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="324", name="Tengoku@Livestream",
    pieces={2: [Effect("cd", 0.32, when=On("enabled"), source="Tengoku")]},
    toggles=[Toggle("enabled", default=0, text="3+ Skill Points consumed in a turn")],
    source="src/lib/sets/ornaments/TengokuLivestream.ts",
)
