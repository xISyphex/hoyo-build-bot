# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/AlongThePassingShore.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tag, Toggle

# Params: [CRIT DMG, DMG, Ultimate DMG]
DEFINITION = LightConeDef(
    id="23024",
    name="Along the Passing Shore",
    effects=[
        Effect("dmg", LC(1), when=On("emptyBubblesDebuff"), source="Along the Passing Shore"),
        Effect("dmg", LC(2), tags=Tag.ULT, when=On("emptyBubblesDebuff"), source="Along the Passing Shore"),
    ],
    toggles=[Toggle("emptyBubblesDebuff", default=1, text="Mirage Fizzle on the target")],
    source="src/lib/conditionals/lightcone/5star/AlongThePassingShore.ts",
)
