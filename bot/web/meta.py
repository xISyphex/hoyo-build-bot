"""What the optimizer page needs to draw its pickers, built from the bot's cached game data.

Every character, light cone, relic set and planar set, with icons on the image hosts the bot already uses (Enka and
StarRailRes; the beta's characters on Hakushin). Nothing is proxied: the page loads the pictures from there.
"""

from __future__ import annotations

import hashlib
import json
import re

from ..assets import Assets
from ..games import starrail as sr

ENKA_UI = "https://enka.network/ui/hsr/"
SRR = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
IMAGE_HOSTS = ("https://enka.network", "https://raw.githubusercontent.com", "https://static.nanoka.cc")
MAX_LEVEL = 80
MAX_RANK = 5  # superimposition
ABILITY_TYPES = {"Normal": "Basic ATK", "BPSkill": "Skill", "Ultra": "Ultimate", "Talent": "Talent",
                 "MemospriteSkill": "Memosprite Skill", "MemospriteTalent": "Memosprite Talent"}
# The game data keys a built meta depends on: it is built again when one of them is read again.
SOURCES = ("hsr_characters", "hsr_weapons", "hsr_skilltree", "srr_characters", "srr_skill_trees", "srr_character_skills",
           "srr_character_ranks", "srr_light_cones", "srr_relic_sets", "hsr_locs")


def short(point_id) -> str:
    """A trace id without the leading 1 that enhanced characters' ids carry (11310001 -> 1310001)."""
    return str(int(point_id) % 10_000_000)


def path_name(path_id: str) -> str:
    return sr.PATH_ICONS.get(path_id, path_id)


def character_name(assets: Assets, cid: str, info: dict) -> str | None:
    name = info.get("Name") or assets.hsr_text(info.get("AvatarName", {}).get("Hash"))
    if name and "{" in name:  # the Trailblazer's name is the player's nickname
        tag = assets.data.get("srr_characters", {}).get(cid, {}).get("tag", "")
        who = " (Stelle)" if tag.endswith("girl") else " (Caelus)" if tag.endswith("boy") else ""
        return f"Trailblazer{who} · {path_name(info.get('AvatarBaseType', ''))}"
    return name


def character_icon(cid: str, info: dict) -> str | None:
    if info.get("Icon"):  # the beta's characters (bot/unreleased.py)
        return info["Icon"]
    path = info.get("AvatarSideIconPath")
    return ENKA_UI + path if path else f"{SRR}icon/character/{cid}.png"


def abilities_and_traces(assets: Assets, cid: str) -> tuple[list[dict], list[dict]]:
    """The character's abilities that level up (Basic ATK, Skill, Ultimate, Talent, memosprite ones) and their traces
    (the three major ones and the stat nodes), by skill tree point id."""
    srr = assets.data.get("srr_characters", {}).get(cid) or {}
    points = assets.data.get("srr_skill_trees", {})
    skills = assets.data.get("srr_character_skills", {})
    abilities, traces = [], []
    for pid in srr.get("skill_trees", []):
        if not pid.startswith(cid) or len(pid) != len(cid) + 3:  # the enhanced copy of the tree has the same nodes
            continue
        point = points.get(pid) or {}
        ups = point.get("level_up_skills") or []
        if ups:
            first = skills.get(str(ups[0].get("id")), {})
            kind = first.get("type", "")
            if kind in ABILITY_TYPES and int(point.get("max_level") or 1) > 1:
                abilities.append({"id": pid, "name": first.get("name") or ABILITY_TYPES[kind], "type": ABILITY_TYPES[kind],
                                  "max_level": int(point["max_level"])})
            continue
        stat = None
        for level in point.get("levels") or []:
            for prop in level.get("properties") or []:
                stat = {"type": prop.get("type"), "name": sr.PROP_SHORT.get(prop.get("type"), prop.get("type")),
                        "value": prop.get("value")}
        traces.append({"id": pid, "name": point.get("name") or "Trace", "kind": "stat" if stat else "major",
                       **({"stat": stat} if stat else {"desc": _fill(point.get("desc", ""), point.get("params") or [])})})
    return abilities, traces


def _fill(desc: str, params: list) -> str:
    """An ability text with its numbered blanks (#1[i]%) filled in from its first level."""
    values = params[0] if params and isinstance(params[0], list) else params

    def put(match: re.Match) -> str:
        i, kind, pct = int(match.group(1)) - 1, match.group(2), match.group(3)
        if i >= len(values):
            return match.group(0)
        value = float(values[i]) * (100 if pct else 1)
        digits = int(kind[1:]) if kind.startswith("f") and kind[1:].isdigit() else 0
        return f"{value:.{digits}f}{pct}"

    return re.sub(r"#(\d+)\[(\w+)\](%?)", put, desc or "").replace("<br>", " ")


def eidolon_names(assets: Assets, cid: str) -> list[str]:
    ranks = assets.data.get("srr_character_ranks", {})
    srr = assets.data.get("srr_characters", {}).get(cid) or {}
    names = [ranks.get(str(r), {}).get("name") for r in srr.get("ranks", [])[:6]]
    return [n or f"Eidolon {i}" for i, n in enumerate(names + [None] * (6 - len(names)), start=1)]


def build(assets: Assets, recommended=None) -> dict:
    """The meta; recommended(character_id, planar) gives the ids of the sets the game recommends (EffectiveStats)."""
    data = assets.data
    characters = []
    for cid, info in data.get("hsr_characters", {}).items():
        name = character_name(assets, cid, info)
        if not name or not cid.isdigit():
            continue
        abilities, traces = abilities_and_traces(assets, cid)
        element = info.get("Element", "")
        characters.append({
            "id": cid, "name": name, "rarity": int(info.get("Rarity") or 0), "path": path_name(info.get("AvatarBaseType", "")),
            "element": sr.ELEMENTS.get(element, element), "icon": character_icon(cid, info), "max_level": MAX_LEVEL,
            "abilities": abilities, "traces": traces, "eidolons": eidolon_names(assets, cid),
            "unreleased": bool(info.get("Unreleased")),
            "recommended": {"relic": [str(i) for i in recommended(cid, False)] if recommended else [],
                            "planar": [str(i) for i in recommended(cid, True)] if recommended else []},
        })
    characters.sort(key=lambda c: c["name"])

    srr_cones = data.get("srr_light_cones", {})
    light_cones = []
    for lid, info in data.get("hsr_weapons", {}).items():
        name = info.get("Name") or assets.hsr_text(info.get("EquipmentName", {}).get("Hash"))
        if not name or not lid.isdigit():
            continue
        icon = srr_cones.get(lid, {}).get("icon")
        light_cones.append({"id": lid, "name": name, "rarity": int(info.get("Rarity") or 0),
                            "path": path_name(info.get("AvatarBaseType", "")),
                            "icon": SRR + icon if icon else f"{SRR}icon/light_cone/{lid}.png", "max_rank": MAX_RANK})
    light_cones.sort(key=lambda c: (-c["rarity"], c["name"]))

    relic_sets, planar_sets = [], []
    for sid, info in sorted(data.get("srr_relic_sets", {}).items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        if not sid.isdigit() or not info.get("name"):
            continue
        desc = list(info.get("desc") or [])
        planar = int(sid) >= 300
        entry = {"id": sid, "name": info["name"], "icon": SRR + info["icon"] if info.get("icon") else None,
                 "bonus_2pc": desc[0] if desc else None}
        if not planar:
            entry["bonus_4pc"] = desc[1] if len(desc) > 1 else None
        (planar_sets if planar else relic_sets).append(entry)
    return {"version": 1, "characters": characters, "light_cones": light_cones, "relic_sets": relic_sets,
            "planar_sets": planar_sets, "slots": sr.SLOT_ORDER, "max_level": MAX_LEVEL}


class MetaCache:
    """The built meta and its ETag, built again when the game data is read again."""

    def __init__(self, assets: Assets, effective=None):
        self.assets = assets
        self.effective = effective
        self._key: tuple | None = None
        self.meta: dict = {}
        self.body = b""
        self.etag = ""
        self._characters: dict[str, dict] = {}

    def get(self) -> tuple[dict, bytes, str]:
        key = (*(id(self.assets.data.get(k)) for k in SOURCES), getattr(self.effective, "updated", None))
        if key != self._key:
            self.meta = build(self.assets, self.effective.recommended_sets if self.effective else None)
            self.body = json.dumps(self.meta, separators=(",", ":"), ensure_ascii=False).encode()
            self.etag = '"' + hashlib.sha256(self.body).hexdigest()[:32] + '"'
            self._characters = {c["id"]: c for c in self.meta["characters"]}
            self._key = key
        return self.meta, self.body, self.etag

    def character(self, cid: str) -> dict | None:
        self.get()
        return self._characters.get(cid)

    def light_cone(self, lid: str) -> dict | None:
        return next((c for c in self.get()[0]["light_cones"] if c["id"] == lid), None)
