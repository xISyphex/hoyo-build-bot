# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/WhereaboutsShouldDreamsRest.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [Break Effect, Routed vulnerability, SPD reduction, duration]
# Fribbels applies Routed as vulnerability to every hit of the wearer; the game text says Break DMG. Kept as in
# Fribbels (see notes).
DEFINITION = LightConeDef(
    id="23025",
    name="Whereabouts Should Dreams Rest",
    effects=[Effect("vuln", LC(1), when=On("routedVulnerability"), source="Whereabouts Should Dreams Rest")],
    toggles=[Toggle("routedVulnerability", default=1, text="Routed")],
    source="src/lib/conditionals/lightcone/5star/WhereaboutsShouldDreamsRest.ts",
    notes=["Routed counts on every hit of the wearer (Fribbels' choice); the game text limits it to Break DMG."],
)
