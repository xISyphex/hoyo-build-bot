# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/ThusBurnsTheDawn.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [base SPD, DEF ignore, Blazing Sun DMG]
DEFINITION = LightConeDef(
    id="23044",
    name="Thus Burns the Dawn",
    effects=[
        Effect("def_pen", LC(1), when=On("defPen"), source="Thus Burns the Dawn"),
        Effect("dmg", LC(2), when=On("dmgBuff"), source="Thus Burns the Dawn"),
    ],
    toggles=[Toggle("defPen", default=1, text="DEF ignore"),
             Toggle("dmgBuff", default=1, text="Blazing Sun")],
    source="src/lib/conditionals/lightcone/5star/ThusBurnsTheDawn.ts",
)
