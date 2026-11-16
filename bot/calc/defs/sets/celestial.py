# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/CelestialDifferentiator.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, StatAtLeast, Toggle

# Fribbels reads the CRIT DMG before combat buffs; we read it after them (see notes).
DEFINITION = SetDef(
    id="305", name="Celestial Differentiator",
    pieces={2: [Effect("cr", 0.60, when=On("enabled") & StatAtLeast("cd", 1.20), source="Celestial Differentiator")]},
    toggles=[Toggle("enabled", default=0, text="First attack of the battle")],
    source="src/lib/sets/ornaments/CelestialDifferentiator.ts",
    notes=["Celestial Differentiator's CRIT DMG threshold is checked on the CRIT DMG after combat buffs."],
)
