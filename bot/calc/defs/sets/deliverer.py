# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/WorldRemakingDeliverer.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

# Fribbels does not check for the memosprite; the switch stands for it. It counts a teammate's copy on top of the
# main character's own (not marked non-stackable).
DEFINITION = SetDef(
    id="127", name="World-Remaking Deliverer",
    pieces={4: [Effect("hp%", 0.24, target="self+memo", when=On("enabled"), source="Deliverer 4pc"),
                Effect("dmg", 0.15, target="team", when=On("enabled"), source="Deliverer 4pc")]},
    team=[Effect("dmg", 0.15, target="team", when=On("enabled"), source="Deliverer 4pc")],
    toggles=[Toggle("enabled", default=1, text="After Basic ATK or Skill, memosprite on the field")],
    source="src/lib/sets/relics/WorldRemakingDeliverer.ts",
)
