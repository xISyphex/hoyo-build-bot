# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/LiesAflutterInTheWind.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, StatAtLeast, Toggle

# Params: [SPD%, Bamboozle chance, Bamboozle DEF reduction, duration, Theft chance, Theft DEF reduction, SPD threshold]
# Theft needs the wearer's SPD at 170 (LC(6), the same at every superimposition; StatAtLeast takes a plain number).
# Worn by the main character it counts on its own hits once its SPD qualifies, as in Fribbels' finalizer; worn by a
# teammate it is a switch.
DEFINITION = LightConeDef(
    id="23043",
    name="Lies Dance on the Breeze",
    effects=[
        Effect("def_pen", LC(2), target="enemy", when=On("defPen"), source="Lies Dance on the Breeze"),
        Effect("def_pen", LC(5), when=On("defPen") & StatAtLeast("spd", 170), as_teammate="main_only",
               source="Lies Dance on the Breeze"),
        Effect("def_pen", LC(5), target="enemy", when=On("defPen") & On("additionalDefPen"), as_teammate="teammate_only",
               source="Lies Dance on the Breeze"),
    ],
    toggles=[Toggle("defPen", default=1, teammate_default=1, text="Bamboozle"),
             Toggle("additionalDefPen", default=1, teammate_default=1, text="Theft (wearer at 170 SPD, as a teammate)")],
    source="src/lib/conditionals/lightcone/5star/LiesAflutterInTheWind.ts",
)
