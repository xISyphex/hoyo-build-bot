# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/AmphoreusTheEternalLand.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, MainHasMemo, On, SetDef, Toggle

# All allies' SPD while the wearer's memosprite is on the field; cannot stack. Fribbels checks for a memosprite on
# the wearer; MainHasMemo also counts summons that are not memosprites (see notes).
DEFINITION = SetDef(
    id="323", name="Amphoreus, The Eternal Land",
    pieces={2: [Effect("spd%", 0.08, target="team", when=On("enabled") & MainHasMemo(), source="Amphoreus")]},
    team=[Effect("spd%", 0.08, target="team", when=On("enabled"), source="Amphoreus")],
    toggles=[Toggle("enabled", default=0, teammate_default=1, text="Wearer's memosprite on the field")],
    nonstackable=True,
    source="src/lib/sets/ornaments/AmphoreusTheEternalLand.ts",
)
