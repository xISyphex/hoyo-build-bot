# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/BrokenKeel.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="310", name="Broken Keel",
    pieces={2: [Effect("cd", 0.10, target="team", when=StatAtLeast("res", 0.30), source="Broken Keel")]},
    team=[Effect("cd", 0.10, target="team", source="Broken Keel")],
    nonstackable=True,
    source="src/lib/sets/ornaments/BrokenKeel.ts",
)
