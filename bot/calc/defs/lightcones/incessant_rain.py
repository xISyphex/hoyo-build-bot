# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/IncessantRain.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [EHR, Aether Code chance, Aether Code vulnerability, debuff count, CRIT Rate]
DEFINITION = LightConeDef(
    id="23007",
    name="Incessant Rain",
    effects=[
        Effect("cr", LC(4), when=On("enemy3DebuffsCrBoost"), source="Incessant Rain"),
        Effect("vuln", LC(2), target="enemy", when=On("targetCodeDebuff"), source="Incessant Rain"),
    ],
    toggles=[Toggle("enemy3DebuffsCrBoost", default=1, text="Enemy has 3+ debuffs"),
             Toggle("targetCodeDebuff", default=1, teammate_default=1, text="Aether Code on the target")],
    source="src/lib/conditionals/lightcone/5star/IncessantRain.ts",
)
