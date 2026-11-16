# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/BoneCollectionsSereneDemesne.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="319", name="Bone Collection's Serene Demesne",
    pieces={2: [Effect("cd", 0.28, target="self+memo", when=StatAtLeast("hp", 5000), source="Bone Collection")]},
    source="src/lib/sets/ornaments/BoneCollectionsSereneDemesne.ts",
)
