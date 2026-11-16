# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/5star/NinjutsuInscriptionDazzlingEvilbreaker.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LightConeDef

# Params: [Break Effect, energy on entering battle, action advance]
# Fribbels has no conditional effects for it; the Break Effect comes from the game data.
DEFINITION = LightConeDef(
    id="23033",
    name="Ninjutsu Inscription: Dazzling Evilbreaker",
    effects=[],
    source="src/lib/conditionals/lightcone/5star/NinjutsuInscriptionDazzlingEvilbreaker.ts",
    notes=["The energy and the action advance are not counted (as in Fribbels)."],
)
