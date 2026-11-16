# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/FleetOfTheAgeless.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

# Worn by a teammate, Fribbels counts the team buff without checking the wearer's SPD.
DEFINITION = SetDef(
    id="302", name="Fleet of the Ageless",
    pieces={2: [Effect("atk%", 0.08, target="self+memo", when=StatAtLeast("spd", 120), source="Fleet 2pc")]},
    team=[Effect("atk%", 0.08, target="team", source="Fleet 2pc")],
    nonstackable=True,
    source="src/lib/sets/ornaments/FleetOfTheAgeless.ts",
)
