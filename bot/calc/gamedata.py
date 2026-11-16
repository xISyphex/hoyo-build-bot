"""Reads the game data the engine needs out of the bot's cached files (bot/assets.py).

Where the numbers come from:

* Ability multipliers per level: StarRailRes ``character_skills.json`` (asset key ``srr_character_skills``),
  ``params[level - 1]`` of each skill. Reworked kits (Fribbels' "b1" ids) use the skill ids with a leading 1
  (1110202 is reworked Seele's Skill). Memosprite skills are ``1<id>NN`` as well; definitions name them explicitly.
* Eidolon level bumps: StarRailRes ``character_ranks.json`` (``srr_character_ranks``), each rank's ``level_up_skills``.
* Major traces (A2/A4/A6) and stat nodes: StarRailRes ``character_skill_trees.json`` (``srr_skill_trees``); the
  anchors Point06-08 are the major traces, Point09-18 the stat nodes.
* Base stats: Enka's ``honker_meta.json`` (``hsr_meta``: ``avatar`` and ``equipment`` per ascension, filled in from
  StarRailRes for newer entries by Assets), the same numbers bot/games/starrail.py uses.
* Light cone passives: ``light_cone_ranks.json`` (``hsr_lc_ranks``, StarRailRes) params per superimposition; the
  passive's always-on stats from ``hsr_meta.equipmentSkill``.
* Set bonuses' plain stats: ``hsr_meta.relic.setSkill``; relic main and sub stat tables: ``hsr_meta.relic``.

No other download is needed. Eidolon numbers are not in this data (only text), so definitions write them as plain
numbers; ``python -m bot.calc.check`` checks them against the eidolon text where it can.
"""

from __future__ import annotations

from functools import cached_property

from .model import GAME_ELEMENTS, PATHS, PROPS

ASCENSION_CAPS = (20, 30, 40, 50, 60, 70)
TRACE_ANCHORS = {"Point06": 1, "Point07": 2, "Point08": 3}
STAT_ANCHORS = {f"Point{n:02d}": n - 8 for n in range(9, 19)}  # Point09 -> stat_1 ... Point18 -> stat_10
SKILL_KINDS = {"Normal": "basic", "BPSkill": "skill", "Ultra": "ult", "Talent": "talent",
               "MemospriteSkill": "memo_skill", "MemospriteTalent": "memo_talent"}


def ascension_for(level: int) -> int:
    """The ascension a character or light cone of this level normally has (ascended at a cap: Lv. 20 counts as A1)."""
    return sum(level >= cap for cap in ASCENSION_CAPS)


class GameData:
    def __init__(self, assets):
        self.assets = assets
        self.d = assets.data

    # ---- characters -----------------------------------------------------------------------------------------

    def character(self, cid: str) -> dict:
        return self.d.get("srr_characters", {}).get(str(cid), {})

    def exists(self, cid: str) -> bool:
        return bool(self.character(cid))

    def name(self, cid: str) -> str:
        return self.character(cid).get("name") or f"Character {cid}"

    def element(self, cid: str) -> str:
        return GAME_ELEMENTS.get(self.character(cid).get("element", ""), "Physical")

    def path(self, cid: str) -> str:
        """The path's player-facing name (Nihility, Harmony, ...)."""
        raw = self.character(cid).get("path", "")
        return PATHS.get(raw, raw)

    def has_variant(self, cid: str) -> bool:
        """The game data has a reworked ("1"-prefixed) kit for the character (not just memosprite skills)."""
        ch = self.character(cid)
        skills = self.d.get("srr_character_skills", {})
        return any(s.startswith("1" + cid) and skills.get(s, {}).get("type") in ("Normal", "BPSkill", "Ultra", "Talent")
                   for s in ch.get("skills", []))

    def skill(self, sid: str) -> dict:
        return self.d.get("srr_character_skills", {}).get(str(sid), {})

    def skill_params(self, sid: str, level: int) -> list[float]:
        rows = self.skill(sid).get("params") or []
        if not rows:
            return []
        return [float(x) for x in rows[max(1, min(level, len(rows))) - 1]]

    def skills_of(self, cid: str, variant: int) -> dict[str, dict]:
        """The character's skills of one kit version, by id."""
        prefix = ("1" if variant else "") + cid
        out = {}
        for sid in self.character(cid).get("skills", []):
            entry = self.skill(sid)
            if not entry:
                continue
            memo = entry.get("type", "").startswith("Memosprite")
            if sid.startswith(prefix) and len(sid) == len(prefix) + 2 or memo:
                out[sid] = entry
        return out

    def eidolon_bumps(self, cid: str, eidolon: int) -> dict[str, int]:
        """skill id -> levels added by the eidolons up to `eidolon` (E3 and E5 "Lv. +2" ranks)."""
        ranks = self.d.get("srr_character_ranks", {})
        bumps: dict[str, int] = {}
        for rid in self.character(cid).get("ranks", [])[:max(0, eidolon)]:
            for up in ranks.get(str(rid), {}).get("level_up_skills", []) or []:
                bumps[str(up["id"])] = bumps.get(str(up["id"]), 0) + int(up.get("num", 0))
        return bumps

    def eidolon_text(self, cid: str, n: int) -> str:
        ranks = self.d.get("srr_character_ranks", {})
        ids = self.character(cid).get("ranks", [])
        return ranks.get(str(ids[n - 1]), {}).get("desc", "") if 0 < n <= len(ids) else ""

    def tree(self, cid: str, variant: int) -> dict[str, dict]:
        """The character's trace nodes of one kit version, by id (falls back to the base kit's nodes)."""
        trees = self.d.get("srr_skill_trees", {})
        ids = self.character(cid).get("skill_trees", [])
        prefix = ("1" if variant else "") + cid
        nodes = {p: trees[p] for p in ids if p in trees and p.startswith(prefix) and len(p) == len(prefix) + 3}
        if variant and not nodes:
            return self.tree(cid, 0)
        return nodes

    def major_traces(self, cid: str, variant: int) -> dict[int, dict]:
        """1/2/3 (A2/A4/A6) -> the trace node."""
        return {TRACE_ANCHORS[n["anchor"]]: n for n in self.tree(cid, variant).values() if n.get("anchor") in TRACE_ANCHORS}

    def stat_nodes(self, cid: str, variant: int) -> dict[int, dict[str, float]]:
        """1..10 (stat_1..stat_10) -> {stat: value} of the minor stat traces."""
        out: dict[int, dict[str, float]] = {}
        for node in self.tree(cid, variant).values():
            n = STAT_ANCHORS.get(node.get("anchor"))
            if n is None:
                continue
            props: dict[str, float] = {}
            for level in node.get("levels", [])[:1]:
                for p in level.get("properties", []):
                    key = PROPS.get(p.get("type"))
                    if key:
                        props[key] = props.get(key, 0.0) + float(p["value"])
            if props:
                out[n] = props
        return out

    def base_stats(self, cid: str, level: int, ascension: int) -> dict[str, float]:
        """hp/atk/def/spd/cr/cd of the character at a level and ascension (bot/games/starrail.py's formula)."""
        base = self.d.get("hsr_meta", {}).get("avatar", {}).get(cid, {}).get(str(ascension), {})
        if not base:
            raise KeyError(f"no base stats for character {cid} at ascension {ascension}")
        return {
            "hp": base.get("HPBase", 0) + base.get("HPAdd", 0) * (level - 1),
            "atk": base.get("AttackBase", 0) + base.get("AttackAdd", 0) * (level - 1),
            "def": base.get("DefenceBase", 0) + base.get("DefenceAdd", 0) * (level - 1),
            "spd": base.get("SpeedBase", 0),
            "cr": base.get("CriticalChance", 0.05),
            "cd": base.get("CriticalDamage", 0.5),
        }

    # ---- light cones ----------------------------------------------------------------------------------------

    def cone(self, lid: str) -> dict:
        return self.d.get("hsr_lc_ranks", {}).get(str(lid), {})

    def cone_exists(self, lid: str) -> bool:
        return str(lid) in self.d.get("hsr_meta", {}).get("equipment", {}) or bool(self.cone(lid))

    def cone_name(self, lid: str) -> str:
        return (self.d.get("srr_light_cones", {}).get(str(lid), {}).get("name")
                or self.d.get("hsr_weapons", {}).get(str(lid), {}).get("Name") or f"Light Cone {lid}")

    def cone_path(self, lid: str) -> str:
        raw = (self.d.get("srr_light_cones", {}).get(str(lid), {}).get("path")
               or self.d.get("hsr_weapons", {}).get(str(lid), {}).get("AvatarBaseType", ""))
        return PATHS.get(raw, raw)

    def cone_params(self, lid: str, rank: int) -> list[float]:
        rows = self.cone(lid).get("params") or []
        if not rows:
            return []
        return [float(x) for x in rows[max(1, min(rank, len(rows))) - 1]]

    def cone_base(self, lid: str, level: int, ascension: int) -> dict[str, float]:
        lc = self.d.get("hsr_meta", {}).get("equipment", {}).get(str(lid), {}).get(str(ascension), {})
        return {
            "hp": lc.get("BaseHP", 0) + lc.get("HPAdd", 0) * (level - 1),
            "atk": lc.get("BaseAttack", 0) + lc.get("AttackAdd", 0) * (level - 1),
            "def": lc.get("BaseDefence", 0) + lc.get("DefenceAdd", 0) * (level - 1),
        }

    def cone_props(self, lid: str, rank: int) -> dict[str, float]:
        """The passive's always-on stats (In the Night's CRIT Rate)."""
        props = (self.d.get("hsr_meta", {}).get("equipmentSkill", {}).get(str(lid), {}).get(str(rank), {}) or {}).get("props") or {}
        out: dict[str, float] = {}
        for k, v in props.items():
            key = PROPS.get(k)
            if key:
                out[key] = out.get(key, 0.0) + float(v)
        return out

    # ---- relic sets -----------------------------------------------------------------------------------------

    def set_name(self, sid: str) -> str:
        return self.d.get("srr_relic_sets", {}).get(str(sid), {}).get("name") or f"Set {sid}"

    def set_exists(self, sid: str) -> bool:
        return str(sid) in self.d.get("srr_relic_sets", {}) or str(sid) in self.d.get("hsr_meta", {}).get("relic", {}).get("setSkill", {})

    def set_props(self, sid: str, pieces: int) -> dict[str, float]:
        """The plain stats of a set bonus (2 or 4 pieces)."""
        skill = self.d.get("hsr_meta", {}).get("relic", {}).get("setSkill", {}).get(str(sid), {})
        out: dict[str, float] = {}
        for k, v in ((skill.get(str(pieces)) or {}).get("props") or {}).items():
            key = PROPS.get(k)
            if key:
                out[key] = out.get(key, 0.0) + float(v)
        return out

    def set_text(self, sid: str, pieces: int) -> str:
        desc = self.d.get("srr_relic_sets", {}).get(str(sid), {}).get("desc") or []
        i = 0 if pieces == 2 else 1
        return desc[i] if i < len(desc) else ""

    @cached_property
    def set_ids(self) -> list[str]:
        return sorted(self.d.get("srr_relic_sets", {}), key=int)
