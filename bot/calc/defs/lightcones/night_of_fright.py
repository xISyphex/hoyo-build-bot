# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/NightOfFright.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tog, Toggle

# Params: [ERR, healing, ATK% per stack, max stacks, duration]
DEFINITION = LightConeDef(
    id="23017",
    name="Night of Fright",
    effects=[Effect("atk%", LC(2) * Tog("atkBuffStacks"), target="team", source="Night of Fright")],
    toggles=[Toggle("atkBuffStacks", "slider", default=5, teammate_default=5, max=5, text="ATK stacks")],
    source="src/lib/conditionals/lightcone/5star/NightOfFright.ts",
)
