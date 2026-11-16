# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/WastelanderOfBanditryDesert.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, TogAtLeast, Toggle

DEFINITION = SetDef(
    id="112", name="Wastelander of Banditry Desert",
    pieces={4: [Effect("cr_boost", 0.10, when=TogAtLeast("value", 1), source="Wastelander 4pc (debuffed)"),
                Effect("cd_boost", 0.20, when=TogAtLeast("value", 2), source="Wastelander 4pc (Imprisoned)")]},
    toggles=[Toggle("value", "select", default=1, max=2, text="Enemy state",
                    options={0: "none", 1: "debuffed", 2: "Imprisoned"})],
    source="src/lib/sets/relics/WastelanderOfBanditryDesert.ts",
)
