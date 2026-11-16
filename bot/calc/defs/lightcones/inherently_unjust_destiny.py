# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/InherentlyUnjustDestiny.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [DEF%, CRIT DMG after shielding, duration, vulnerability chance, vulnerability, duration]
DEFINITION = LightConeDef(
    id="23023",
    name="Inherently Unjust Destiny",
    effects=[
        Effect("cd", LC(1), when=On("shieldCdBuff"), source="Inherently Unjust Destiny"),
        Effect("vuln", LC(4), target="enemy", when=On("targetVulnerability"), source="Inherently Unjust Destiny"),
    ],
    toggles=[Toggle("shieldCdBuff", default=1, text="CRIT DMG after shielding"),
             Toggle("targetVulnerability", default=1, teammate_default=1, text="DMG taken on the target")],
    source="src/lib/conditionals/lightcone/5star/InherentlyUnjustDestiny.ts",
)
