# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/IVentureForthToHunt.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tag, Tog, Toggle

# Params: [CRIT Rate, Ultimate DEF ignore per Luminflux stack, max stacks]
DEFINITION = LightConeDef(
    id="23031",
    name="I Venture Forth to Hunt",
    effects=[Effect("def_pen", LC(1) * Tog("luminfluxUltStacks"), tags=Tag.ULT, source="I Venture Forth to Hunt")],
    toggles=[Toggle("luminfluxUltStacks", "slider", default=2, max=2, text="Luminflux stacks")],
    source="src/lib/conditionals/lightcone/5star/IVentureForthToHunt.ts",
)
