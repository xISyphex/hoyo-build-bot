# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/BaptismOfPureThought.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Tag, Tog, Toggle

# Params: [CRIT DMG, CRIT DMG per debuff, max stacks, Disputation DMG, Disputation Follow-up DEF ignore, duration]
DEFINITION = LightConeDef(
    id="23020",
    name="Baptism of Pure Thought",
    effects=[
        Effect("cd", LC(1) * Tog("debuffCdStacks"), source="Baptism of Pure Thought"),
        Effect("dmg", LC(3), when=On("postUltBuff"), source="Baptism of Pure Thought"),
        Effect("def_pen", LC(4), tags=Tag.FUA, when=On("postUltBuff"), source="Baptism of Pure Thought"),
    ],
    toggles=[Toggle("debuffCdStacks", "slider", default=3, max=3, text="Debuffs on the target"),
             Toggle("postUltBuff", default=1, text="Disputation")],
    source="src/lib/conditionals/lightcone/5star/BaptismOfPureThought.ts",
)
