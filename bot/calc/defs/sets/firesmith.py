# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/FiresmithOfLavaForging.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Tag, Toggle

DEFINITION = SetDef(
    id="107", name="Firesmith of Lava-Forging",
    pieces={4: [Effect("dmg", 0.12, tags=Tag.SKILL, source="Firesmith 4pc"),
                Effect("dmg_fire", 0.12, when=On("enabled"), source="Firesmith 4pc (after the Ultimate)")]},
    toggles=[Toggle("enabled", default=1, text="Fire DMG after the Ultimate")],
    source="src/lib/sets/relics/FiresmithOfLavaForging.ts",
)
