"""Game data (names, base stats, stat curves) published by Enka.Network.

The Enka API returns only IDs and raw numbers; these files turn them into names
and let us compute final stats. They are downloaded once, cached on disk and
refreshed periodically so new characters work without a redeploy.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

STORE_URL = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/"

FILES = {
    "gi_avatars": "gi/avatars.json",
    "gi_locs": "gi/locs.json",
    "gi_weapons": "gi/weapons.json",
    "gi_relics": "gi/relics.json",
    "gi_loc_legacy": "loc.json",
    "hsr_characters": "hsr/honker_characters.json",
    "hsr_weapons": "hsr/honker_weps.json",
    "hsr_relics": "hsr/honker_relics.json",
    "hsr_meta": "hsr/honker_meta.json",
    "hsr_skilltree": "hsr/honker_skilltree.json",
    "hsr_ranks": "hsr/honker_ranks.json",
    "hsr_locs": "hsr/hsr.json",
    "hsr_lc_ranks": "hsr/light_cone_ranks.json",
    "srr_characters": "hsr/srr/characters.json",
    "srr_character_promotions": "hsr/srr/character_promotions.json",
    "srr_skill_trees": "hsr/srr/character_skill_trees.json",
    "srr_light_cones": "hsr/srr/light_cones.json",
    "srr_light_cone_promotions": "hsr/srr/light_cone_promotions.json",
    "srr_relic_sets": "hsr/srr/relic_sets.json",
    "srr_relics": "hsr/srr/relics.json",
    "zzz_avatars": "zzz/avatars.json",
    "zzz_weapons": "zzz/weapons.json",
    "zzz_equipments": "zzz/equipments.json",
    "zzz_locs": "zzz/locs.json",
}

# Files that don't come from Enka's store. Light cone passives (text plus the
# numbers per superimposition) are only published by StarRailRes. Enka's store
# also lags behind new Star Rail releases (no characters past 1415 as of 3.x), so
# StarRailRes fills in characters, light cones and relic sets the store lacks.
SRR_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/index_min/en/"
URLS = {
    "hsr_lc_ranks": SRR_URL + "light_cone_ranks.json",
    **{key: SRR_URL + rel.rsplit("/", 1)[1] for key, rel in FILES.items() if key.startswith("srr_")},
}

MAX_AGE = 12 * 3600

class Assets:
    def __init__(self, cache_dir: str | Path, lang: str = "en"):
        self.cache_dir = Path(cache_dir)
        self.lang = lang
        self.data: dict[str, dict] = {}
        self._hsr_names: dict[float, str] = {}
        self._gi_names: dict[str, str] = {}

    def _path(self, key: str) -> Path:
        return self.cache_dir / FILES[key]

    def is_stale(self) -> bool:
        paths = [self._path(k) for k in FILES]
        if not all(p.exists() for p in paths):
            return True
        return time.time() - min(p.stat().st_mtime for p in paths) > MAX_AGE

    async def refresh(self, session) -> None:
        """Download every store file; keep the cached copy if a download fails."""
        for key, rel in FILES.items():
            try:
                async with session.get(URLS.get(key, STORE_URL + rel)) as resp:
                    resp.raise_for_status()
                    body = await resp.read()
                json.loads(body)  # never cache a broken file
                path = self._path(key)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            except Exception:
                log.exception("Could not refresh %s, keeping cached copy", rel)
        self.load()

    def load(self) -> None:
        for key in FILES:
            path = self._path(key)
            if path.exists():
                self.data[key] = json.loads(path.read_text(encoding="utf-8"))
            else:
                self.data[key] = {}
        self._fill_hsr_gaps()
        self._build_indexes()

    def _fill_hsr_gaps(self) -> None:
        """Add what StarRailRes knows and Enka's store doesn't, in the store's own shapes.

        Entries the store already has are left alone. Names go in a plain "Name"
        field, since StarRailRes has the text rather than a text-map hash.
        """
        d = self.data
        meta = d["hsr_meta"]
        if not meta:
            return
        for cid, c in d["srr_characters"].items():
            if cid in d["hsr_characters"]:
                continue
            d["hsr_characters"][cid] = {
                "Name": c.get("name"),
                "Rarity": c.get("rarity", 0),
                "Element": c.get("element", ""),
                "AvatarBaseType": c.get("path", ""),
                "AvatarSideIconPath": f"SpriteOutput/AvatarRoundIcon/{cid}.png",
                "RankIDList": [int(r) for r in c.get("ranks", [])],
            }
        for cid, promo in d["srr_character_promotions"].items():
            if cid in meta["avatar"]:
                continue
            meta["avatar"][cid] = {
                str(i): {
                    "HPBase": v["hp"]["base"], "HPAdd": v["hp"]["step"],
                    "AttackBase": v["atk"]["base"], "AttackAdd": v["atk"]["step"],
                    "DefenceBase": v["def"]["base"], "DefenceAdd": v["def"]["step"],
                    "SpeedBase": v["spd"]["base"],
                    "CriticalChance": v["crit_rate"]["base"], "CriticalDamage": v["crit_dmg"]["base"],
                }
                for i, v in enumerate(promo.get("values", []))
            }
        for pid, point in d["srr_skill_trees"].items():
            if pid in meta["tree"]:
                continue
            levels = {
                str(i): {"props": {p["type"]: p["value"] for p in lv.get("properties", [])}}
                for i, lv in enumerate(point.get("levels", []), start=1)
            }
            if any(lv["props"] for lv in levels.values()):
                meta["tree"][pid] = levels
        for lid, lc in d["srr_light_cones"].items():
            d["hsr_weapons"].setdefault(lid, {
                "Name": lc.get("name"), "Rarity": lc.get("rarity", 0), "AvatarBaseType": lc.get("path", ""),
            })
        for lid, promo in d["srr_light_cone_promotions"].items():
            meta["equipment"].setdefault(lid, {
                str(i): {
                    "BaseHP": v["hp"]["base"], "HPAdd": v["hp"]["step"],
                    "BaseAttack": v["atk"]["base"], "AttackAdd": v["atk"]["step"],
                    "BaseDefence": v["def"]["base"], "DefenceAdd": v["def"]["step"],
                }
                for i, v in enumerate(promo.get("values", []))
            })
        for lid, ranks in d["hsr_lc_ranks"].items():
            if lid in meta["equipmentSkill"]:
                continue
            props = [{p["type"]: p["value"] for p in rank} for rank in ranks.get("properties", [])]
            if any(props):
                meta["equipmentSkill"][lid] = {str(i): {"props": p} for i, p in enumerate(props, start=1)}
        for sid, rset in d["srr_relic_sets"].items():
            if sid in meta["relic"]["setSkill"]:
                continue
            pieces = (2, 4) if int(sid) < 300 else (2,)  # planar sets only have a 2pc bonus
            meta["relic"]["setSkill"][sid] = {
                str(n): {"props": {p["type"]: p["value"] for p in props}}
                for n, props in zip(pieces, rset.get("properties", []))
            }
        for rid, relic in d["srr_relics"].items():
            d["hsr_relics"].setdefault(rid, {
                "Type": relic.get("type"), "SetID": int(relic.get("set_id", 0)), "Rarity": relic.get("rarity", 0),
            })

    def hsr_set_name(self, set_id) -> str | None:
        """Relic set name from StarRailRes, for sets newer than the text map."""
        return self.data.get("srr_relic_sets", {}).get(str(set_id), {}).get("name")

    def _build_indexes(self) -> None:
        legacy = self.data["gi_loc_legacy"].get(self.lang, {})
        current = self.data["gi_locs"].get(self.lang, {})
        self._gi_names = {**legacy, **current}

        # HSR name hashes are 64-bit, but the store's character/weapon files were
        # written by JavaScript and lost precision. Matching on the float value
        # of both sides lines them up again.
        self._hsr_names = {}
        for key, text in self.data["hsr_locs"].get(self.lang, {}).items():
            if key.isdigit():
                self._hsr_names[float(int(key))] = text

    # ---- name lookups -------------------------------------------------

    def gi_text(self, key) -> str | None:
        return self._gi_names.get(str(key))

    def hsr_text(self, key) -> str | None:
        if key is None:
            return None
        if isinstance(key, str) and not key.lstrip("-").isdigit():
            return self.data["hsr_locs"].get(self.lang, {}).get(key)
        return self._hsr_names.get(float(int(key)))

    def zzz_text(self, key) -> str | None:
        return self.data["zzz_locs"].get(self.lang, {}).get(key)

    # ---- character name lists (autocomplete / fuzzy matching) --------

    def character_names(self, game: str) -> list[str]:
        names: set[str] = set()
        if game == "genshin":
            for info in self.data["gi_avatars"].values():
                name = self.gi_text(info.get("NameTextMapHash"))
                if name:
                    names.add(name)
        elif game == "hsr":
            for info in self.data["hsr_characters"].values():
                name = info.get("Name") or self.hsr_text(info.get("AvatarName", {}).get("Hash"))
                if name:
                    names.add(name)
        elif game == "zzz":
            for info in self.data["zzz_avatars"].values():
                name = self.zzz_text(info.get("Name"))
                if name:
                    names.add(name)
        return sorted(names)
