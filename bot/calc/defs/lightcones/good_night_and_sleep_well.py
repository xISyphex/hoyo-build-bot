# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/4star/GoodNightAndSleepWell.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tog, Toggle

# Params: [DMG per debuff, max stacks]
DEFINITION = LightConeDef(
    id="21001",
    name="Good Night and Sleep Well",
    effects=[Effect("dmg", LC(0) * Tog("debuffStacksDmgIncrease"), source="Good Night and Sleep Well")],
    toggles=[Toggle("debuffStacksDmgIncrease", "slider", default=3, max=3, text="Debuffs on the target")],
    source="src/lib/conditionals/lightcone/4star/GoodNightAndSleepWell.ts",
)
