# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/TimeWovenIntoGold.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tag, Tog, TogAtLeast, Toggle

# Params: [base SPD, max Brocade stacks, Basic ATK DMG per stack at max stacks, CRIT DMG per stack]
DEFINITION = LightConeDef(
    id="23036",
    name="Time Woven Into Gold",
    effects=[
        Effect("cd", LC(3) * Tog("brocadeStacks"), target="self+memo", source="Time Woven Into Gold"),
        Effect("dmg", LC(2) * Tog("brocadeStacks"), target="self+memo", tags=Tag.BASIC,
               when=TogAtLeast("brocadeStacks", 6) & On("maxStacksBasicDmgBoost"), source="Time Woven Into Gold"),
    ],
    toggles=[Toggle("brocadeStacks", "slider", default=6, max=6, text="Brocade stacks"),
             Toggle("maxStacksBasicDmgBoost", default=1, text="Basic ATK DMG at max stacks")],
    source="src/lib/conditionals/lightcone/5star/TimeWovenIntoGold.ts",
)
