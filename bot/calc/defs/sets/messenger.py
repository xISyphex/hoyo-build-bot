# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/MessengerTraversingHackerspace.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="114", name="Messenger Traversing Hackerspace",
    pieces={4: [Effect("spd%", 0.12, target="team", when=On("enabled"), source="Messenger 4pc")]},
    team=[Effect("spd%", 0.12, target="team", when=On("enabled"), source="Messenger 4pc")],
    toggles=[Toggle("enabled", default=0, teammate_default=1, text="Ultimate on an ally")],
    nonstackable=True,
    source="src/lib/sets/relics/MessengerTraversingHackerspace.ts",
)
