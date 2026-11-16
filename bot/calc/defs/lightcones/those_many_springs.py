# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/ThoseManySprings.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [EHR, Unarmored chance, Unarmored vulnerability, duration, Cornered chance, Cornered extra vulnerability]
DEFINITION = LightConeDef(
    id="23029",
    name="Those Many Springs",
    effects=[
        Effect("vuln", LC(2), target="enemy", when=On("unarmoredVulnerability") | On("corneredVulnerability"),
               source="Those Many Springs"),
        Effect("vuln", LC(5), target="enemy", when=On("corneredVulnerability"), source="Those Many Springs"),
    ],
    toggles=[Toggle("unarmoredVulnerability", default=1, teammate_default=1, text="Unarmored"),
             Toggle("corneredVulnerability", default=1, teammate_default=1, text="Cornered")],
    source="src/lib/conditionals/lightcone/5star/ThoseManySprings.ts",
)
