# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/PatienceIsAllYouNeed.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tog, Toggle

# Params: [..., DMG, SPD% per stack, max stacks, ...]. Erode (Additional DMG) is not modelled, as in Fribbels.
DEFINITION = LightConeDef(
    id="23006",
    name="Patience Is All You Need",
    effects=[Effect("spd%", LC(2) * Tog("spdStacks"), source="Patience Is All You Need")],
    toggles=[Toggle("spdStacks", "slider", default=3, max=3, text="SPD stacks")],
    source="src/lib/conditionals/lightcone/5star/PatienceIsAllYouNeed.ts",
    notes=["Erode's Additional DMG is not counted (as in Fribbels)."],
)
