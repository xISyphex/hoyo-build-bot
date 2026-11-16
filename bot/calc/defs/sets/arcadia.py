# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/ArcadiaOfWovenDreams.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, Pick, SetDef, Toggle

# Fribbels' table: 12% per ally missing below 4 (at most 3), 9% per ally above 4 (at most 4).
DMG = {1: 0.36, 2: 0.24, 3: 0.12, 4: 0.0, 5: 0.09, 6: 0.18, 7: 0.27, 8: 0.36}
DEFINITION = SetDef(
    id="321", name="Arcadia of Woven Dreams",
    pieces={2: [Effect("dmg", Pick("value", DMG), target="self+memo", source="Arcadia")]},
    toggles=[Toggle("value", "select", default=4, min=1, max=8, text="Ally targets on the field",
                    options={n: str(n) for n in range(1, 9)})],
    source="src/lib/sets/ornaments/ArcadiaOfWovenDreams.ts",
)
