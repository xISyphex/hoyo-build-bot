# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/TheUnreachableSide.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [CRIT Rate, HP%, DMG after being attacked or consuming HP]
DEFINITION = LightConeDef(
    id="23009",
    name="The Unreachable Side",
    effects=[Effect("dmg", LC(2), when=On("dmgBuff"), source="The Unreachable Side")],
    toggles=[Toggle("dmgBuff", default=1, text="DMG after being attacked or consuming HP")],
    source="src/lib/conditionals/lightcone/5star/TheUnreachableSide.ts",
)
