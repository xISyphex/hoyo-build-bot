# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/LushakaTheSunkenSeas.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

# Only a teammate's copy helps the main character (the first in the lineup). Fribbels gives the ATK to the full
# team (memosprites included) and does not mark it non-stackable.
DEFINITION = SetDef(
    id="317", name="Lushaka, the Sunken Seas",
    team=[Effect("atk%", 0.12, target="team", when=On("enabled"), source="Lushaka")],
    toggles=[Toggle("enabled", default=1, text="Main character is first in the lineup")],
    source="src/lib/sets/ornaments/LushakaTheSunkenSeas.ts",
)
