# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/SelfEnshroudedRecluse.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

# The Shield Effect bonuses (2pc +10%, 4pc +12%) are not ported: the engine has no Shield output. Fribbels does not
# mark the CRIT DMG as non-stackable.
DEFINITION = SetDef(
    id="128", name="Self-Enshrouded Recluse",
    pieces={4: [Effect("cd", 0.15, target="team", when=On("enabled"), source="Recluse 4pc")]},
    team=[Effect("cd", 0.15, target="team", when=On("enabled"), source="Recluse 4pc")],
    toggles=[Toggle("enabled", default=1, text="Allies hold the wearer's Shield")],
    source="src/lib/sets/relics/SelfEnshroudedRecluse.ts",
    notes=["Self-Enshrouded Recluse: the Shield Effect bonuses are not computed (no Shield output)."],
)
