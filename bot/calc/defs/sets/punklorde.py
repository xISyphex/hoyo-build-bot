# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/PunklordeStageZero.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, StatAtLeast

DEFINITION = SetDef(
    id="325", name="Punklorde Stage Zero",
    pieces={2: [Effect("cd", 0.20, when=StatAtLeast("elation", 0.40), source="Punklorde (Elation 40%)"),
                Effect("cd", 0.12, when=StatAtLeast("elation", 0.80), source="Punklorde (Elation 80%)")]},
    source="src/lib/sets/ornaments/PunklordeStageZero.ts",
)
