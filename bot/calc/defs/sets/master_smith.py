# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/DivineQueryingMasterSmith.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, TogAtLeast, Toggle

# "Comburent" (DMG for all allies) cannot stack. A teammate's copy counts it like Fribbels' teammate set.
DEFINITION = SetDef(
    id="132", name="Divine-Querying Master Smith",
    pieces={4: [Effect("cd_boost", 0.28, when=TogAtLeast("value", 1), source="Master Smith 4pc (DEF reduced)"),
                Effect("dmg", 0.15, target="team", when=TogAtLeast("value", 2), source="Master Smith 4pc (Comburent)")]},
    team=[Effect("dmg", 0.15, target="team", when=TogAtLeast("value", 2), source="Master Smith 4pc (Comburent)")],
    toggles=[Toggle("value", "select", default=0, teammate_default=2, max=2, text="Enemy DEF reduced",
                    options={0: "off", 1: "CRIT DMG", 2: "CRIT DMG and Comburent"})],
    nonstackable=True,
    source="src/lib/sets/relics/DivineQueryingMasterSmith.ts",
)
