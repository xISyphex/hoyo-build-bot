# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/PoetOfMourningCollapse.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatBelow

# Fribbels reads the SPD before combat buffs; we read the main character's SPD after them (see notes).
DEFINITION = SetDef(
    id="124", name="Poet of Mourning Collapse",
    pieces={4: [Effect("cr", 0.20, target="self+memo", when=StatBelow("spd", 110), source="Poet 4pc"),
                Effect("cr", 0.12, target="self+memo", when=StatBelow("spd", 95), source="Poet 4pc")]},
    source="src/lib/sets/relics/PoetOfMourningCollapse.ts",
    notes=["Poet's SPD thresholds are checked on the SPD after combat buffs."],
)
