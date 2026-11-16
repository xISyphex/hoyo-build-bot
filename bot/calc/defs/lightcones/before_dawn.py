# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/BeforeDawn.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tag, Toggle

# Params: [CRIT DMG, Skill/Ultimate DMG, Follow-up DMG (Somnus Corpus)]
DEFINITION = LightConeDef(
    id="23010",
    name="Before Dawn",
    effects=[
        Effect("dmg", LC(1), tags=Tag.SKILL | Tag.ULT, source="Before Dawn"),
        Effect("dmg", LC(2), tags=Tag.FUA, when=On("fuaDmgBoost"), source="Before Dawn"),
    ],
    toggles=[Toggle("fuaDmgBoost", default=1, text="Somnus Corpus (Follow-up DMG)")],
    source="src/lib/conditionals/lightcone/5star/BeforeDawn.ts",
)
