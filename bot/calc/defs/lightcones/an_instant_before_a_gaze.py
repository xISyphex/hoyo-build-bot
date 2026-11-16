# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/AnInstantBeforeAGaze.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import Call, Effect, LightConeDef, On, Tag, Toggle

# Params: [CRIT DMG, Ultimate DMG per point of Max Energy, Max Energy counted]


def _max_energy_dmg(ctx) -> float:
    """Fribbels: min(180, baseEnergy) x LC(1); the wearer's Max Energy comes from the game data."""
    energy = float(ctx.gd.d.get("srr_characters", {}).get(str(ctx.owner["id"]), {}).get("max_sp", 0) or 0)
    return min(ctx.cone_param(2), energy) * ctx.cone_param(1)


DEFINITION = LightConeDef(
    id="23018",
    name="An Instant Before A Gaze",
    effects=[Effect("dmg", Call(_max_energy_dmg, "Max Energy x LC(1)"), tags=Tag.ULT, when=On("maxEnergyDmgBoost"),
                    source="An Instant Before A Gaze")],
    toggles=[Toggle("maxEnergyDmgBoost", default=1, text="Ultimate DMG from Max Energy")],
    source="src/lib/conditionals/lightcone/5star/AnInstantBeforeAGaze.ts",
)
