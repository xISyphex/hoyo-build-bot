# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/ReforgedRemembrance.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tag, Tog, Toggle

# Params: [EHR, ATK% per Prophet stack, DoT DEF ignore per stack, max stacks]
DEFINITION = LightConeDef(
    id="23022",
    name="Reforged Remembrance",
    effects=[
        Effect("atk%", LC(1) * Tog("prophetStacks"), source="Reforged Remembrance"),
        Effect("def_pen", LC(2) * Tog("prophetStacks"), tags=Tag.DOT, source="Reforged Remembrance"),
    ],
    toggles=[Toggle("prophetStacks", "slider", default=4, max=4, text="Prophet stacks")],
    source="src/lib/conditionals/lightcone/5star/ReforgedRemembrance.ts",
)
