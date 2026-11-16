# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/ScentAloneStaysTrue.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, StatAtLeast, Toggle

# Params: [Break Effect, Woefree vulnerability, BE threshold, extra vulnerability, duration]
# Worn by the main character the extra vulnerability needs its own Break Effect at 150% (LC(2), the same at every
# superimposition; StatAtLeast takes a plain number) and counts on its own hits, as in Fribbels' finalizer. Worn by a
# teammate it is a switch.
DEFINITION = LightConeDef(
    id="23032",
    name="Scent Alone Stays True",
    effects=[
        Effect("vuln", LC(1), target="enemy", when=On("woefreeState"), source="Scent Alone Stays True"),
        Effect("vuln", LC(3), when=On("woefreeState") & StatAtLeast("be", 1.50), as_teammate="main_only",
               source="Scent Alone Stays True"),
        Effect("vuln", LC(3), target="enemy", when=On("woefreeState") & On("additionalVulnerability"),
               as_teammate="teammate_only", source="Scent Alone Stays True"),
    ],
    toggles=[Toggle("woefreeState", default=1, teammate_default=1, text="Woefree"),
             Toggle("additionalVulnerability", default=1, teammate_default=1,
                    text="Wearer's Break Effect at 150% (as a teammate)")],
    source="src/lib/conditionals/lightcone/5star/ScentAloneStaysTrue.ts",
)
