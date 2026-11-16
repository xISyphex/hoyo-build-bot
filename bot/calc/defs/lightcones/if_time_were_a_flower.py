# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/IfTimeWereAFlower.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [CRIT DMG, energy, ..., team CRIT DMG (Presage), ...]
DEFINITION = LightConeDef(
    id="23038",
    name="If Time Were a Flower",
    effects=[Effect("cd", LC(3), target="team", when=On("presage"), source="If Time Were a Flower")],
    toggles=[Toggle("presage", default=1, text="Presage")],
    source="src/lib/conditionals/lightcone/5star/IfTimeWereAFlower.ts",
)
