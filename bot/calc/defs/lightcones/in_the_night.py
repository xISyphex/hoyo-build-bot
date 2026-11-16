# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/InTheNight.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Scale, Tag, Toggle

# Params: [CRIT Rate, SPD per stack, Basic/Skill DMG per stack, Ult CRIT DMG per stack, max stacks]
# One stack per full 10 SPD above 100 (Fribbels reads the full combat SPD), at most 6.
DEFINITION = LightConeDef(
    id="23001",
    name="In the Night",
    effects=[
        Effect("dmg", Scale("spd", LC(2), above=100, step=LC(1), cap=LC(2) * LC(4), convertible=False),
               tags=Tag.BASIC | Tag.SKILL, when=On("spdScalingBuffs"), source="In the Night"),
        Effect("cd", Scale("spd", LC(3), above=100, step=LC(1), cap=LC(3) * LC(4), convertible=False),
               tags=Tag.ULT, when=On("spdScalingBuffs"), source="In the Night"),
    ],
    toggles=[Toggle("spdScalingBuffs", default=1, text="SPD-scaling buffs")],
    source="src/lib/conditionals/lightcone/5star/InTheNight.ts",
)
