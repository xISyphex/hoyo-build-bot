# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/CityOfConvergingStars.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, Pick, SetDef, Toggle

# Select: 0 off, 1 ATK after a Follow-Up ATK, 2 CRIT DMG after an enemy is defeated, 3 both. The CRIT DMG is for all
# allies and cannot stack (Fribbels gives the wearer's own copy to the wearer only).
ATK = {1: 0.24, 3: 0.24}
CD = {2: 0.12, 3: 0.12}
DEFINITION = SetDef(
    id="326", name="City of Converging Stars",
    pieces={2: [Effect("atk%", Pick("value", ATK), source="City of Converging Stars (Follow-Up ATK)"),
                Effect("cd", Pick("value", CD), target="team", source="City of Converging Stars (enemy defeated)")]},
    team=[Effect("cd", Pick("value", CD), target="team", source="City of Converging Stars (enemy defeated)")],
    toggles=[Toggle("value", "select", default=3, max=3, text="Active buffs",
                    options={0: "off", 1: "ATK", 2: "CRIT DMG", 3: "ATK and CRIT DMG"})],
    nonstackable=True,
    source="src/lib/sets/ornaments/CityOfConvergingStars.ts",
)
