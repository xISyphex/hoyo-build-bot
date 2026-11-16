# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/LifeShouldBeCastToFlames.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [..., DEF reduction, DMG to targets with an implanted Weakness, duration, energy]
DEFINITION = LightConeDef(
    id="23041",
    name="Life Should Be Cast to Flames",
    effects=[
        Effect("dmg", LC(2), when=On("dmgBoost"), source="Life Should Be Cast to Flames"),
        Effect("def_pen", LC(1), target="enemy", when=On("defPen"), source="Life Should Be Cast to Flames"),
    ],
    toggles=[Toggle("dmgBoost", default=1, text="DMG to targets with an implanted Weakness"),
             Toggle("defPen", default=1, teammate_default=1, text="DEF reduction")],
    source="src/lib/conditionals/lightcone/5star/LifeShouldBeCastToFlames.ts",
)
