# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/LongRoadLeadsHome.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, Tag, Tog, Toggle

# Params: [Break Effect, Charring chance, Break DMG taken per stack, duration, max stacks]
DEFINITION = LightConeDef(
    id="23035",
    name="Long Road Leads Home",
    effects=[Effect("vuln", LC(2) * Tog("breakVulnerabilityStacks"), target="enemy", tags=Tag.BREAK,
                    source="Long Road Leads Home")],
    toggles=[Toggle("breakVulnerabilityStacks", "slider", default=2, teammate_default=2, max=2, text="Charring stacks")],
    source="src/lib/conditionals/lightcone/5star/LongRoadLeadsHome.ts",
)
