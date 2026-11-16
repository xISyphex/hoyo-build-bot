# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/AThanklessCoronation.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Call, Effect, LightConeDef, On, Toggle

# Params: [CRIT DMG, extra ATK% at high Max Energy, Max Energy threshold, duration, energy, ATK% on the Ultimate]


def _energy_atk(ctx) -> float:
    """Fribbels: LC(1) when baseEnergy >= LC(2); the wearer's Max Energy comes from the game data."""
    energy = float(ctx.gd.d.get("srr_characters", {}).get(str(ctx.owner["id"]), {}).get("max_sp", 0) or 0)
    return ctx.cone_param(1) if energy >= ctx.cone_param(2) else 0.0


DEFINITION = LightConeDef(
    id="23045",
    name="A Thankless Coronation",
    effects=[
        Effect("atk%", LC(5), when=On("ultAtkBoost"), source="A Thankless Coronation"),
        Effect("atk%", Call(_energy_atk, "LC(1) if Max Energy >= LC(2)"), when=On("energyAtkBuff"),
               source="A Thankless Coronation"),
    ],
    toggles=[Toggle("ultAtkBoost", default=1, text="ATK after the Ultimate"),
             Toggle("energyAtkBuff", default=1, text="Extra ATK at 300 Max Energy")],
    source="src/lib/conditionals/lightcone/5star/AThanklessCoronation.ts",
)
