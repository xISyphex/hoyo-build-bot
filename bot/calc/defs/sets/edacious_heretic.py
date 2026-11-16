# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/TheEdaciousHeretic.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Tag, Toggle

DEFINITION = SetDef(
    id="134", name="The Edacious Heretic",
    pieces={4: [Effect("dmg", 0.36, tags=Tag.BASIC, source="Edacious Heretic 4pc"),
                Effect("atk%", 0.20, when=On("enabled"), source="Edacious Heretic 4pc (after Basic ATK)")]},
    toggles=[Toggle("enabled", default=1, text="ATK after Basic ATK")],
    source="src/lib/sets/relics/TheEdaciousHeretic.ts",
)
