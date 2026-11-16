# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/conditionals/lightcone/4star/PlanetaryRendezvous.ts, branch main as of 2026-11-16. Numbers re-pointed to game data params.

from ...model import LC, Effect, LightConeDef, On, SameElement, Toggle

# Params: [DMG for allies of the wearer's element]
DEFINITION = LightConeDef(
    id="21011",
    name="Planetary Rendezvous",
    effects=[Effect("dmg", LC(0), target="team", when=On("alliesSameElement") & SameElement(),
                    source="Planetary Rendezvous")],
    toggles=[Toggle("alliesSameElement", default=1, text="Allies of the same element")],
    source="src/lib/conditionals/lightcone/4star/PlanetaryRendezvous.ts",
)
