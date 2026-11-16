# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/EchoesOfTheCoffin.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [ATK%, team SPD after the Ultimate, energy per enemy hit, max triggers]
DEFINITION = LightConeDef(
    id="23008",
    name="Echoes of the Coffin",
    effects=[Effect("spd", LC(1), target="team", when=On("postUltSpdBuff"), source="Echoes of the Coffin")],
    toggles=[Toggle("postUltSpdBuff", default=0, teammate_default=0, text="Team SPD after the Ultimate")],
    source="src/lib/conditionals/lightcone/5star/EchoesOfTheCoffin.ts",
)
