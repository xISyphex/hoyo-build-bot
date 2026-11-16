# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/PastSelfInTheMirror.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [Break Effect, team DMG, duration, energy, ...]
DEFINITION = LightConeDef(
    id="23019",
    name="Past Self in Mirror",
    effects=[Effect("dmg", LC(1), target="team", when=On("postUltDmgBuff"), source="Past Self in Mirror")],
    toggles=[Toggle("postUltDmgBuff", default=1, text="DMG buff after the Ultimate")],
    source="src/lib/conditionals/lightcone/5star/PastSelfInTheMirror.ts",
)
