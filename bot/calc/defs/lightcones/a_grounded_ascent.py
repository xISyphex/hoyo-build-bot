# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/AGroundedAscent.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Not, OwnerIs, Tog, Toggle

SUNDAY = OwnerIs("1313")
# Params: [..., DMG per stack, max stacks, ...]. Given by Sunday it reaches the ally's memosprite too.
DEFINITION = LightConeDef(
    id="23034",
    name="A Grounded Ascent",
    effects=[
        Effect("dmg", LC(1) * Tog("dmgBuffStacks"), target="ally", when=Not(SUNDAY), source="A Grounded Ascent"),
        Effect("dmg", LC(1) * Tog("dmgBuffStacks"), target="ally+memo", when=SUNDAY, source="A Grounded Ascent"),
    ],
    toggles=[Toggle("dmgBuffStacks", "slider", default=3, max=3, text="Hymn stacks")],
    source="src/lib/conditionals/lightcone/5star/AGroundedAscent.ts",
)
