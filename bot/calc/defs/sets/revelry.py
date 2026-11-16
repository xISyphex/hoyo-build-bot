# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/RevelryByTheSea.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast, Tag

DEFINITION = SetDef(
    id="322", name="Revelry by the Sea",
    pieces={2: [Effect("dmg", 0.12, tags=Tag.DOT, when=StatAtLeast("atk", 2400), source="Revelry (ATK 2400)"),
                Effect("dmg", 0.12, tags=Tag.DOT, when=StatAtLeast("atk", 3600), source="Revelry (ATK 3600)")]},
    source="src/lib/sets/ornaments/RevelryByTheSea.ts",
)
