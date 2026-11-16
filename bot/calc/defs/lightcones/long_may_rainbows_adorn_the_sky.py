# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/MayRainbowsRemainInTheSky.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [SPD%, HP consumed, ..., vulnerability, duration, Additional DMG ratio]
# The memosprite's Additional DMG from consumed HP is not counted, as in Fribbels.
DEFINITION = LightConeDef(
    id="23042",
    name="Long May Rainbows Adorn the Sky",
    effects=[Effect("vuln", LC(3), target="enemy", when=On("vulnerability"), source="Long May Rainbows Adorn the Sky")],
    toggles=[Toggle("vulnerability", default=1, teammate_default=1, text="DMG taken after the Memosprite Skill")],
    source="src/lib/conditionals/lightcone/5star/MayRainbowsRemainInTheSky.ts",
    notes=["The memosprite's Additional DMG from consumed HP is not counted (as in Fribbels)."],
)
