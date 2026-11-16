# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/SomethingIrreplaceable.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [ATK%, healing, DMG]
DEFINITION = LightConeDef(
    id="23002",
    name="Something Irreplaceable",
    effects=[Effect("dmg", LC(2), when=On("dmgBuff"), source="Something Irreplaceable")],
    toggles=[Toggle("dmgBuff", default=1, text="DMG after defeating an enemy or being hit")],
    source="src/lib/conditionals/lightcone/5star/SomethingIrreplaceable.ts",
)
