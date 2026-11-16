# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/DanceAtSunset.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tag, Tog, Toggle

# Params: [CRIT DMG, max Firedance stacks, Follow-up DMG per stack, ...]
DEFINITION = LightConeDef(
    id="23030",
    name="Dance at Sunset",
    effects=[Effect("dmg", LC(2) * Tog("fuaDmgStacks"), tags=Tag.FUA, source="Dance at Sunset")],
    toggles=[Toggle("fuaDmgStacks", "slider", default=2, max=2, text="Firedance stacks")],
    source="src/lib/conditionals/lightcone/5star/DanceAtSunset.ts",
)
