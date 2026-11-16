# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/SheAlreadyShutHerEyes.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [HP%, team DMG when the wearer loses HP, healing, ERR, duration]
DEFINITION = LightConeDef(
    id="23011",
    name="She Already Shut Her Eyes",
    effects=[Effect("dmg", LC(1), target="team", when=On("hpLostDmgBuff"), source="She Already Shut Her Eyes")],
    toggles=[Toggle("hpLostDmgBuff", default=1, teammate_default=1, text="Team DMG after the wearer loses HP")],
    source="src/lib/conditionals/lightcone/5star/SheAlreadyShutHerEyes.ts",
)
