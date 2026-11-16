# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/TheHellWhereIdealsBurn.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tog, Toggle

# Params: [CRIT Rate, Skill Point limit, ATK%, ATK% per Skill use, max stacks]
DEFINITION = LightConeDef(
    id="23046",
    name="The Hell Where Ideals Burn",
    effects=[
        Effect("atk%", LC(2), when=On("spAtkBuff"), source="The Hell Where Ideals Burn"),
        Effect("atk%", LC(3) * Tog("atkBuffStacks"), source="The Hell Where Ideals Burn"),
    ],
    toggles=[Toggle("spAtkBuff", default=1, text="Skill Point limit of 6 or more"),
             Toggle("atkBuffStacks", "slider", default=4, max=4, text="ATK stacks from the Skill")],
    source="src/lib/conditionals/lightcone/5star/TheHellWhereIdealsBurn.ts",
)
