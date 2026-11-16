# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/MomentOfVictory.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [aggro, DEF%, extra DEF% when attacked, EHR]
DEFINITION = LightConeDef(
    id="23005",
    name="Moment of Victory",
    effects=[Effect("def%", LC(2), when=On("selfAttackedDefBuff"), source="Moment of Victory")],
    toggles=[Toggle("selfAttackedDefBuff", default=1, text="DEF after being attacked")],
    source="src/lib/conditionals/lightcone/5star/MomentOfVictory.ts",
)
