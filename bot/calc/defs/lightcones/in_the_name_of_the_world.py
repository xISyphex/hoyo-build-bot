# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/InTheNameOfTheWorld.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [DMG to debuffed enemies, Skill EHR, Skill ATK%]
DEFINITION = LightConeDef(
    id="23004",
    name="In the Name of the World",
    effects=[
        Effect("dmg", LC(0), when=On("enemyDebuffedDmgBoost"), source="In the Name of the World"),
        Effect("atk%", LC(2), actions=("skill",), when=On("skillAtkBoost"), source="In the Name of the World"),
        Effect("ehr", LC(1), actions=("skill",), when=On("skillEhrBoost"), source="In the Name of the World"),
    ],
    toggles=[Toggle("enemyDebuffedDmgBoost", default=1, text="DMG to debuffed enemies"),
             Toggle("skillAtkBoost", default=1, text="Skill ATK boost"),
             Toggle("skillEhrBoost", default=1, text="Skill EHR boost")],
    source="src/lib/conditionals/lightcone/5star/InTheNameOfTheWorld.ts",
)
