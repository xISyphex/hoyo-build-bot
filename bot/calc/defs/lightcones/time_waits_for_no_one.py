# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/TimeWaitsForNoOne.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LightConeDef

# Params: [HP%, Outgoing Healing, Additional DMG from recorded healing]
# Fribbels has a switch for the healing-based Additional DMG but computes nothing for it; the plain stats come from
# the game data. Nothing conditional is counted.
DEFINITION = LightConeDef(
    id="23013",
    name="Time Waits for No One",
    effects=[],
    source="src/lib/conditionals/lightcone/5star/TimeWaitsForNoOne.ts",
    notes=["The Additional DMG from recorded healing is not counted (as in Fribbels)."],
)
