# Ported from fribbels/hsr-optimizer (MIT, Copyright (c) 2024 Fribbels; see THIRD_PARTY_NOTICES.md)
# src/lib/sets/ornaments/CosmicLifeSciencesInstitute.ts, branch main as of 2026-11-16. The plain stats come from the game data.

from ...model import Call, Effect, SetDef


def _boost(ctx) -> float:
    # 0.2% DMG per point of Max Energy above 200, at most 32% (the set text).
    energy = float(ctx.gd.character(str(ctx.owner["id"])).get("max_sp") or 0)
    return min(0.32, max(0.0, energy - 200) * 0.002)


DEFINITION = SetDef(
    id="328", name="Cosmic Life Sciences Institute",
    pieces={2: [Effect("dmg", Call(_boost, "0.2% per Max Energy above 200, max 32%"), source="Cosmic Life Sciences")]},
    source="src/lib/sets/ornaments/CosmicLifeSciencesInstitute.ts",
)
