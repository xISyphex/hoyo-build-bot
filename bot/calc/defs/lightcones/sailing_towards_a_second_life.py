# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/SailingTowardsASecondLife.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, StatAtLeast, Tag, Toggle

# Params: [Break Effect, BE threshold, Break DMG DEF ignore, SPD%]
# The threshold is LC(1) = 150% at every superimposition; StatAtLeast takes a plain number, so it is written here.
DEFINITION = LightConeDef(
    id="23027",
    name="Sailing Towards a Second Life",
    effects=[
        Effect("def_pen", LC(2), tags=Tag.BREAK, when=On("breakDmgDefShred"), source="Sailing Towards a Second Life"),
        Effect("spd%", LC(3), when=On("spdBuffConditional") & StatAtLeast("be", 1.50),
               source="Sailing Towards a Second Life"),
    ],
    toggles=[Toggle("breakDmgDefShred", default=1, text="Break DMG ignores DEF"),
             Toggle("spdBuffConditional", default=1, text="SPD at 150% Break Effect")],
    source="src/lib/conditionals/lightcone/5star/SailingTowardsASecondLife.ts",
)
