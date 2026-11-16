# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/4star/DanceDanceDance.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LightConeDef

# Action advance only; Fribbels counts no stat effect.
DEFINITION = LightConeDef(
    id="21018",
    name="Dance! Dance! Dance!",
    effects=[],
    source="src/lib/conditionals/lightcone/4star/DanceDanceDance.ts",
    notes=["The team action advance is not counted (as in Fribbels)."],
)
