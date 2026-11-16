# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/HeroOfTriumphantSong.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

DEFINITION = SetDef(
    id="123", name="Hero of Triumphant Song",
    pieces={4: [Effect("spd%", 0.06, when=On("enabled"), source="Hero 4pc"),
                Effect("cd", 0.30, target="self+memo", when=On("enabled"), source="Hero 4pc")]},
    toggles=[Toggle("enabled", default=0, text="Memosprite on the field and attacked")],
    source="src/lib/sets/relics/HeroOfTriumphantSong.ts",
)
