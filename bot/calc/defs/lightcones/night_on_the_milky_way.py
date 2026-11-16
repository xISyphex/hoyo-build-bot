# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/NightOnTheMilkyWay.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, Toggle

# Params: [DMG after a Weakness Break, ATK% per enemy on the field]
# The ATK% per enemy (Fribbels: enemyCount x LC(1)) needs the enemy count, which definitions cannot read yet: left out.
DEFINITION = LightConeDef(
    id="23000",
    name="Night on the Milky Way",
    effects=[Effect("dmg", LC(0), when=On("enemyWeaknessBreakDmgBuff"), source="Night on the Milky Way")],
    toggles=[Toggle("enemyWeaknessBreakDmgBuff", default=1, text="DMG after a Weakness Break")],
    source="src/lib/conditionals/lightcone/5star/NightOnTheMilkyWay.ts",
    notes=["The ATK% per enemy on the field is not counted (the definition cannot read the enemy count yet)."],
)
