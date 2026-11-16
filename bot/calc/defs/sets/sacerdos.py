# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/SacerdosRelivedOrdeal.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, Not, OwnerIs, SetDef, Tog, Toggle

SUNDAY = OwnerIs("1313")
# Worn by a support: CRIT DMG per stack to the ally they target (and its memosprite when Sunday wears it). The
# wearer's own copy (Fribbels' default 0) is not counted.
DEFINITION = SetDef(
    id="121", name="Sacerdos' Relived Ordeal",
    team=[Effect("cd", 0.18 * Tog("stacks"), target="ally", when=Not(SUNDAY), source="Sacerdos 4pc"),
          Effect("cd", 0.18 * Tog("stacks"), target="ally+memo", when=SUNDAY, source="Sacerdos 4pc")],
    toggles=[Toggle("stacks", "slider", default=2, max=2, text="Stacks on the main character")],
    source="src/lib/sets/relics/SacerdosRelivedOrdeal.ts",
)
