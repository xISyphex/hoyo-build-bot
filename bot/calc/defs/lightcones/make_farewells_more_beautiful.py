# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/MakeFarewellsMoreBeautiful.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [HP%, DEF ignore, duration, ...]
DEFINITION = LightConeDef(
    id="23040",
    name="Make Farewells More Beautiful",
    effects=[Effect("def_pen", LC(1), target="self+memo", when=On("deathFlower"), source="Make Farewells More Beautiful")],
    toggles=[Toggle("deathFlower", default=1, text="Death Flower")],
    source="src/lib/conditionals/lightcone/5star/MakeFarewellsMoreBeautiful.ts",
)
