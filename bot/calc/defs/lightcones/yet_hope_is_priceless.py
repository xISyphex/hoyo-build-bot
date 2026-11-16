# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/YetHopeIsPriceless.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Scale, Tag, Toggle

# Params: [CRIT Rate, CRIT DMG threshold, CRIT DMG step, Follow-up DMG per step, max steps, Ult/FUA DEF ignore, duration]
# Follow-up DMG per full 20% CRIT DMG above 120% (Fribbels reads the final CRIT DMG), at most 4 steps.
DEFINITION = LightConeDef(
    id="23028",
    name="Yet Hope Is Priceless",
    effects=[
        Effect("dmg", Scale("cd", LC(3), above=LC(1), step=LC(2), cap=LC(3) * LC(4), convertible=False),
               tags=Tag.FUA, when=On("fuaDmgBoost"), source="Yet Hope Is Priceless"),
        Effect("def_pen", LC(5), tags=Tag.ULT | Tag.FUA, when=On("ultFuaDefShred"), source="Yet Hope Is Priceless"),
    ],
    toggles=[Toggle("fuaDmgBoost", default=1, text="Follow-up DMG from CRIT DMG"),
             Toggle("ultFuaDefShred", default=1, text="Ultimate/Follow-up DEF ignore")],
    source="src/lib/conditionals/lightcone/5star/YetHopeIsPriceless.ts",
)
