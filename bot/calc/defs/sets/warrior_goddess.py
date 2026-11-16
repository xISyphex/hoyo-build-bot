# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/relics/WarriorGoddessOfSunAndThunder.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Effect, On, SetDef, Toggle

# "Gentle Rain": SPD for the wearer, CRIT DMG for all allies; the team part cannot stack.
DEFINITION = SetDef(
    id="125", name="Warrior Goddess of Sun and Thunder",
    pieces={4: [Effect("spd%", 0.06, when=On("enabled"), source="Warrior Goddess 4pc"),
                Effect("cd", 0.15, target="team", when=On("enabled"), source="Warrior Goddess 4pc")]},
    team=[Effect("cd", 0.15, target="team", when=On("enabled"), source="Warrior Goddess 4pc")],
    toggles=[Toggle("enabled", default=0, teammate_default=1, text="Gentle Rain (healed an ally)")],
    nonstackable=True,
    source="src/lib/sets/relics/WarriorGoddessOfSunAndThunder.ts",
)
