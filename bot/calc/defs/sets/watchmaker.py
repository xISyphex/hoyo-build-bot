# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/WatchmakerMasterOfDreamMachinations.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="118", name="Watchmaker, Master of Dream Machinations",
    pieces={4: [Effect("be", 0.30, target="team", when=On("enabled"), source="Watchmaker 4pc")]},
    team=[Effect("be", 0.30, target="team", when=On("enabled"), source="Watchmaker 4pc")],
    toggles=[Toggle("enabled", default=0, teammate_default=1, text="Ultimate on an ally")],
    nonstackable=True,
    source="src/lib/sets/relics/WatchmakerMasterOfDreamMachinations.ts",
)
