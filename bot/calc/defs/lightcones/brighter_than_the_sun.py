# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/BrighterThanTheSun.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tog, Toggle

# Params: [CRIT Rate, duration, max stacks, ATK% per stack, ERR per stack]
DEFINITION = LightConeDef(
    id="23015",
    name="Brighter Than the Sun",
    effects=[
        Effect("atk%", LC(3) * Tog("dragonsCallStacks"), source="Brighter Than the Sun"),
        Effect("err", LC(4) * Tog("dragonsCallStacks"), source="Brighter Than the Sun"),
    ],
    toggles=[Toggle("dragonsCallStacks", "slider", default=2, max=2, text="Dragon's Call stacks")],
    source="src/lib/conditionals/lightcone/5star/BrighterThanTheSun.ts",
)
