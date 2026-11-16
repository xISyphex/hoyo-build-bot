# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/DivinerOfDistantReach.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, StatAtLeast, Toggle

# Fribbels reads the SPD before combat buffs; we read the main character's SPD after them (see notes).
DEFINITION = SetDef(
    id="130", name="Diviner of Distant Reach",
    pieces={4: [Effect("cr", 0.10, when=StatAtLeast("spd", 120), source="Diviner 4pc (SPD 120)"),
                Effect("cr", 0.08, when=StatAtLeast("spd", 160), source="Diviner 4pc (SPD 160)"),
                Effect("elation", 0.10, target="team", when=On("enabled"), source="Diviner 4pc")]},
    team=[Effect("elation", 0.10, target="team", when=On("enabled"), source="Diviner 4pc")],
    toggles=[Toggle("enabled", default=1, text="Elation after the first Elation Skill")],
    nonstackable=True,
    source="src/lib/sets/relics/DivinerOfDistantReach.ts",
    notes=["Diviner's SPD thresholds are checked on the SPD after combat buffs."],
)
