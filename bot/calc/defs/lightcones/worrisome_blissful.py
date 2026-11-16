# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/WorrisomeBlissful.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tag, Tog, Toggle

# Params: [CRIT Rate, Follow-up DMG, CRIT DMG per Tame stack, max Tame stacks]
DEFINITION = LightConeDef(
    id="23016",
    name="Worrisome, Blissful",
    effects=[
        Effect("dmg", LC(1), tags=Tag.FUA, source="Worrisome, Blissful"),
        Effect("cd", LC(2) * Tog("targetTameStacks"), target="team", source="Worrisome, Blissful"),
    ],
    toggles=[Toggle("targetTameStacks", "slider", default=2, teammate_default=2, max=2, text="Tame stacks on the target")],
    source="src/lib/conditionals/lightcone/5star/WorrisomeBlissful.ts",
)
