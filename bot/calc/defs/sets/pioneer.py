# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/PioneerDiverOfDeadWaters.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, Pick, SetDef, TogAtLeast, Toggle

# Select: -1 no debuff, 0: 1 debuff, 1: 2 debuffs, 2: 3+ debuffs, 3: 2 debuffs after the Ult, 4: 3+ after the Ult.
CD = {0: 0.0, 1: 0.08, 2: 0.12, 3: 0.16, 4: 0.24}
DEFINITION = SetDef(
    id="117", name="Pioneer Diver of Dead Waters",
    pieces={2: [Effect("dmg", 0.12, when=TogAtLeast("value", 0), source="Pioneer 2pc")],
            4: [Effect("cd_boost", Pick("value", CD), source="Pioneer 4pc"),
                Effect("cr", 0.04, when=TogAtLeast("value", 3), source="Pioneer 4pc (after the Ultimate)")]},
    toggles=[Toggle("value", "select", default=2, min=-1, max=4, text="Debuffs on the target",
                    options={-1: "none", 0: "1", 1: "2", 2: "3+", 3: "2, after the Ultimate", 4: "3+, after the Ultimate"})],
    source="src/lib/sets/relics/PioneerDiverOfDeadWaters.ts",
)
