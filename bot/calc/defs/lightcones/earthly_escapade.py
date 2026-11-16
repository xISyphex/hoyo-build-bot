# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/EarthlyEscapade.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [CRIT DMG, teammates' CRIT DMG (Mask), Radiant Flame stacks, Mask duration, teammates' CRIT Rate, ...]
# Mask buffs the wearer's teammates only, so it counts when the wearer is a teammate (Fribbels: teammate effects).
DEFINITION = LightConeDef(
    id="23021",
    name="Earthly Escapade",
    effects=[
        Effect("cr", LC(4), target="team", when=On("maskActive"), as_teammate="teammate_only", source="Earthly Escapade"),
        Effect("cd", LC(1), target="team", when=On("maskActive"), as_teammate="teammate_only", source="Earthly Escapade"),
    ],
    toggles=[Toggle("maskActive", default=0, teammate_default=1, text="Mask")],
    source="src/lib/conditionals/lightcone/5star/EarthlyEscapade.ts",
)
