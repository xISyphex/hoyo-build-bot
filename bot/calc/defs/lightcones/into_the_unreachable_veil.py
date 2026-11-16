# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/IntotheUnreachableVeil.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tag, Toggle

# Params: [CRIT Rate, duration, Energy for the Skill Point, Skill/Ultimate DMG, duration]
DEFINITION = LightConeDef(
    id="23037",
    name="Into the Unreachable Veil",
    effects=[Effect("dmg", LC(3), tags=Tag.SKILL | Tag.ULT, when=On("skillUltDmgBoost"), source="Into the Unreachable Veil")],
    toggles=[Toggle("skillUltDmgBoost", default=1, text="Skill/Ultimate DMG after the Ultimate")],
    source="src/lib/conditionals/lightcone/5star/IntotheUnreachableVeil.ts",
)
