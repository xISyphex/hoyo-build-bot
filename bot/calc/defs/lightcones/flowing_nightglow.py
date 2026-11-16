# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/FlowingNightglow.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tog, Toggle

# Params: [ERR per stack, max stacks, team DMG, ATK%, ...]
DEFINITION = LightConeDef(
    id="23026",
    name="Flowing Nightglow",
    effects=[
        Effect("err", LC(0) * Tog("cantillationStacks"), as_teammate="main_only", source="Flowing Nightglow"),
        Effect("atk%", LC(3), when=On("cadenzaActive"), as_teammate="main_only", source="Flowing Nightglow"),
        Effect("dmg", LC(2), target="team", when=On("cadenzaActive"), source="Flowing Nightglow"),
    ],
    toggles=[Toggle("cantillationStacks", "slider", default=5, max=5, text="Cantillation stacks"),
             Toggle("cadenzaActive", default=1, text="Cadenza")],
    source="src/lib/conditionals/lightcone/5star/FlowingNightglow.ts",
)
