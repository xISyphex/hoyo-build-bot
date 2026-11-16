# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/ButTheBattleIsntOver.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [ERR, DMG to the next ally, ...]
DEFINITION = LightConeDef(
    id="23003",
    name="But the Battle Isn't Over",
    effects=[Effect("dmg", LC(1), target="ally", when=On("postSkillDmgBuff"), source="But the Battle Isn't Over")],
    toggles=[Toggle("postSkillDmgBuff", default=1, text="DMG buff after the Skill")],
    source="src/lib/conditionals/lightcone/5star/ButTheBattleIsntOver.ts",
)
