# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/FlameOfBloodBlazeMyPath.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Scale, Tag, Toggle

# Params: [HP%, HP consumed, Skill/Ultimate DMG, HP threshold, extra DMG, Incoming Healing]
# The extra DMG counts when LC(1) x Max HP is above LC(3) (Fribbels reads the final HP), i.e. Max HP above
# LC(3) / LC(1). The threshold depends on the superimposition, so it is written as a Scale whose tiny step makes it
# a step to LC(4) just above the threshold.
DEFINITION = LightConeDef(
    id="23039",
    name="Flame of Blood, Blaze My Path",
    effects=[
        Effect("dmg", LC(2), tags=Tag.SKILL | Tag.ULT, when=On("skillUltDmgBoost"), source="Flame of Blood, Blaze My Path"),
        Effect("dmg", Scale("hp", LC(4), above=LC(3) / LC(1), step=1e-6, cap=LC(4), convertible=False),
               tags=Tag.SKILL | Tag.ULT, when=On("skillUltDmgBoost"), source="Flame of Blood, Blaze My Path"),
    ],
    toggles=[Toggle("skillUltDmgBoost", default=1, text="Skill/Ultimate DMG from consumed HP")],
    source="src/lib/conditionals/lightcone/5star/FlameOfBloodBlazeMyPath.ts",
)
