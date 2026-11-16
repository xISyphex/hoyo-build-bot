# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/FirmamentFrontlineGlamoth.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="311", name="Firmament Frontline: Glamoth",
    pieces={2: [Effect("dmg", 0.12, when=StatAtLeast("spd", 135), source="Glamoth"),
                Effect("dmg", 0.06, when=StatAtLeast("spd", 160), source="Glamoth (SPD 160)")]},
    source="src/lib/sets/ornaments/FirmamentFrontlineGlamoth.ts",
)
