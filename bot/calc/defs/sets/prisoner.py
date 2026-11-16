# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/PrisonerInDeepConfinement.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, Tog, Toggle

# Fribbels' generic default is 0 DoTs; its DoT character presets use 3. We default to 3 (the set is only worn by DoT
# characters).
DEFINITION = SetDef(
    id="116", name="Prisoner in Deep Confinement",
    pieces={4: [Effect("def_pen", 0.06 * Tog("value"), source="Prisoner 4pc")]},
    toggles=[Toggle("value", "slider", default=3, max=3, text="DoTs on the target")],
    source="src/lib/sets/relics/PrisonerInDeepConfinement.ts",
    notes=["Prisoner counts 3 DoTs on the target by default (Fribbels' DoT presets)."],
)
