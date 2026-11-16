# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/PenaconyLandOfTheDreams.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SameElement, SetDef, Toggle

DEFINITION = SetDef(
    id="312", name="Penacony, Land of the Dreams",
    pieces={2: [Effect("dmg", 0.10, target="memo", when=On("enabled"), source="Penacony")]},
    team=[Effect("dmg", 0.10, target="team", when=SameElement(), source="Penacony")],
    toggles=[Toggle("enabled", default=1, text="Memosprite DMG")],
    source="src/lib/sets/ornaments/PenaconyLandOfTheDreams.ts",
)
