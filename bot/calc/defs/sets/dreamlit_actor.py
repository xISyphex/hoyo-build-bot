# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/DreamlitActor.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, SetDef, TogAtLeast, Toggle

# The Elation buff goes to one other ally (never the wearer); the Certified Banger CRIT DMG to all allies. Fribbels
# does not mark it non-stackable.
DEFINITION = SetDef(
    id="133", name="Dreamlit Actor",
    pieces={4: [Effect("cd", 0.12, target="team", when=TogAtLeast("value", 2), source="Dreamlit Actor 4pc")]},
    team=[Effect("elation", 0.16, target="ally", when=TogAtLeast("value", 1), source="Dreamlit Actor 4pc"),
          Effect("cd", 0.12, target="team", when=TogAtLeast("value", 2), source="Dreamlit Actor 4pc")],
    toggles=[Toggle("value", "select", default=2, max=2, text="Buffs given",
                    options={0: "off", 1: "Elation to an ally", 2: "Elation and CRIT DMG (10+ Certified Banger)"})],
    source="src/lib/sets/relics/DreamlitActor.ts",
)
