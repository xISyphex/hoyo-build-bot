# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/SleepLikeTheDead.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [CRIT DMG, CRIT Rate after a non-CRIT Basic ATK/Skill, duration, cooldown]
DEFINITION = LightConeDef(
    id="23012",
    name="Sleep Like the Dead",
    effects=[Effect("cr", LC(1), when=On("missedCritCrBuff"), source="Sleep Like the Dead")],
    toggles=[Toggle("missedCritCrBuff", default=0, text="CRIT Rate after a non-CRIT hit")],
    source="src/lib/conditionals/lightcone/5star/SleepLikeTheDead.ts",
)
