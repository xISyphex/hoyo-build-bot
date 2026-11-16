# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/IShallBeMyOwnSword.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tog, TogAtLeast, Toggle

# Params: [CRIT DMG, max stacks, DMG per stack, DEF ignore at max stacks]
DEFINITION = LightConeDef(
    id="23014",
    name="I Shall Be My Own Sword",
    effects=[
        Effect("dmg", LC(2) * Tog("eclipseStacks"), source="I Shall Be My Own Sword"),
        Effect("def_pen", LC(3), when=On("maxStackDefPen") & TogAtLeast("eclipseStacks", 3),
               source="I Shall Be My Own Sword"),
    ],
    toggles=[Toggle("eclipseStacks", "slider", default=3, max=3, text="Eclipse stacks"),
             Toggle("maxStackDefPen", default=1, text="DEF ignore at 3 stacks")],
    source="src/lib/conditionals/lightcone/5star/IShallBeMyOwnSword.ts",
)
