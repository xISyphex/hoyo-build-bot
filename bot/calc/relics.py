"""The engine's relic model, and the parser for "Kelz v4" relic exports (Reliquary Archiver, HSR-Scanner).

A relic's stats are in the engine's stat keys (model.BASIC_STATS) as fractions: 0.324 is 32.4% CRIT Rate.

Kelz v4 files name the main stat but don't carry its value: it is computed from the main stat table
(``hsr_meta.relic.mainAffix["<rarity><slot>"]``: BaseValue + LevelAdd x level), as Fribbels does. Substats carry
their value in percent units; Reliquary Archiver also sends the roll count and step sum, from which the exact value is
recomputed (``hsr_meta.relic.subAffix[rarity]``: count x BaseValue + step x StepValue), which keeps Speed's hidden
decimals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .engine import CalcError
from .model import DEFAULT_LEVELS

SLOTS = ("Head", "Hands", "Body", "Feet", "Planar Sphere", "Link Rope")
# stat key -> game property, for the affix tables
PROP_OF = {
    "hp": "HPDelta", "atk": "AttackDelta", "def": "DefenceDelta", "spd": "SpeedDelta",
    "hp%": "HPAddedRatio", "atk%": "AttackAddedRatio", "def%": "DefenceAddedRatio",
    "cr": "CriticalChanceBase", "cd": "CriticalDamageBase", "ehr": "StatusProbabilityBase",
    "res": "StatusResistanceBase", "be": "BreakDamageAddedRatioBase", "err": "SPRatioBase", "ohb": "HealRatioBase",
    "dmg_physical": "PhysicalAddedRatio", "dmg_fire": "FireAddedRatio", "dmg_ice": "IceAddedRatio",
    "dmg_lightning": "ThunderAddedRatio", "dmg_wind": "WindAddedRatio", "dmg_quantum": "QuantumAddedRatio",
    "dmg_imaginary": "ImaginaryAddedRatio",
}
# Kelz main stat names (percent vs flat follows from the slot)
MAIN_NAMES = {
    "SPD": "spd", "CRIT Rate": "cr", "CRIT DMG": "cd", "Effect Hit Rate": "ehr", "Outgoing Healing Boost": "ohb",
    "Break Effect": "be", "Energy Regeneration Rate": "err", "Physical DMG Boost": "dmg_physical",
    "Fire DMG Boost": "dmg_fire", "Ice DMG Boost": "dmg_ice", "Lightning DMG Boost": "dmg_lightning",
    "Wind DMG Boost": "dmg_wind", "Quantum DMG Boost": "dmg_quantum", "Imaginary DMG Boost": "dmg_imaginary",
}
SUB_NAMES = {
    "HP": "hp", "ATK": "atk", "DEF": "def", "SPD": "spd", "HP_": "hp%", "ATK_": "atk%", "DEF_": "def%",
    "CRIT Rate_": "cr", "CRIT DMG_": "cd", "Effect Hit Rate_": "ehr", "Effect RES_": "res", "Break Effect_": "be",
}
ALLOWED_MAINS = {
    "Head": ("hp",), "Hands": ("atk",),
    "Body": ("hp%", "atk%", "def%", "cr", "cd", "ehr", "ohb"),
    "Feet": ("hp%", "atk%", "def%", "spd"),
    "Planar Sphere": ("hp%", "atk%", "def%", "dmg_physical", "dmg_fire", "dmg_ice", "dmg_lightning", "dmg_wind",
                      "dmg_quantum", "dmg_imaginary"),
    "Link Rope": ("hp%", "atk%", "def%", "be", "err"),
}
SUB_KEYS = ("hp", "atk", "def", "spd", "hp%", "atk%", "def%", "cr", "cd", "ehr", "res", "be")


@dataclass
class Relic:
    uid: str
    set_id: str
    slot: str
    rarity: int
    level: int
    main: str
    main_value: float
    subs: dict[str, float] = field(default_factory=dict)
    location: str = ""  # id of the character wearing it ("" = nobody)

    def stats(self) -> dict[str, float]:
        out = dict(self.subs)
        out[self.main] = out.get(self.main, 0.0) + self.main_value
        return out

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Relic":
        if not isinstance(d, dict):
            raise CalcError("a relic must be an object")
        unknown = set(d) - {"uid", "set_id", "slot", "rarity", "level", "main", "main_value", "subs", "location"}
        if unknown:
            raise CalcError(f"unknown relic fields: {', '.join(sorted(unknown))}")
        try:
            r = cls(uid=str(d["uid"]), set_id=str(d["set_id"]), slot=str(d["slot"]), rarity=int(d["rarity"]),
                    level=int(d["level"]), main=str(d["main"]), main_value=float(d["main_value"]),
                    subs={str(k): float(v) for k, v in (d.get("subs") or {}).items()}, location=str(d.get("location") or ""))
        except (KeyError, TypeError, ValueError) as e:
            raise CalcError(f"bad relic {d.get('uid', '?')}: {e}") from None
        r.validate()
        return r

    def validate(self) -> None:
        if self.slot not in SLOTS:
            raise CalcError(f"relic {self.uid}: unknown slot {self.slot}")
        if self.main not in ALLOWED_MAINS[self.slot]:
            raise CalcError(f"relic {self.uid}: {self.main} can't be the main stat of a {self.slot}")
        if (int(self.set_id) >= 300) != (self.slot in SLOTS[4:]):
            raise CalcError(f"relic {self.uid}: set {self.set_id} doesn't make {self.slot} pieces")
        if not 2 <= self.rarity <= 5 or not 0 <= self.level <= 15:
            raise CalcError(f"relic {self.uid}: bad rarity or level")
        for k in self.subs:
            if k not in SUB_KEYS:
                raise CalcError(f"relic {self.uid}: {k} can't be a substat")


def main_stat_key(slot: str, name: str) -> str:
    if slot == "Head" and name == "HP":
        return "hp"
    if slot == "Hands" and name == "ATK":
        return "atk"
    if name in ("HP", "ATK", "DEF"):
        return name.lower() + "%"
    key = MAIN_NAMES.get(name)
    if key is None:
        raise CalcError(f"unknown main stat {name}")
    return key


def main_value(meta: dict, rarity: int, slot: str, key: str, level: int) -> float:
    group = meta.get("relic", {}).get("mainAffix", {}).get(f"{rarity}{SLOTS.index(slot) + 1}", {})
    prop = PROP_OF[key]
    for entry in group.values():
        if entry.get("Property") == prop:
            return float(entry["BaseValue"]) + float(entry["LevelAdd"]) * level
    raise CalcError(f"no {rarity}-star {slot} main stat table for {key}")


def sub_value(meta: dict, rarity: int, key: str, count: int, step: int) -> float:
    group = meta.get("relic", {}).get("subAffix", {}).get(str(rarity), {})
    prop = PROP_OF[key]
    for entry in group.values():
        if entry.get("Property") == prop:
            return count * float(entry["BaseValue"]) + step * float(entry["StepValue"])
    raise CalcError(f"no {rarity}-star substat table for {key}")


@dataclass
class KelzExport:
    source: str
    relics: list[Relic]
    characters: list[dict]  # as in the file (see character_request)
    light_cones: list[dict]
    uid: int | None = None


def parse_kelz(data: dict, assets) -> KelzExport:
    """A Kelz v4 export (already JSON-decoded). Raises CalcError naming the first bad entry."""
    if not isinstance(data, dict):
        raise CalcError("the file isn't a relic export")
    if data.get("version") != 4:
        raise CalcError(f"unsupported export version {data.get('version')!r} (only version 4 is supported)")
    meta = assets.data.get("hsr_meta", {})
    known_sets = set(assets.data.get("srr_relic_sets", {})) | set(meta.get("relic", {}).get("setSkill", {}))
    relics = []
    for i, r in enumerate(data.get("relics") or []):
        try:
            slot = r["slot"]
            if slot not in SLOTS:
                raise CalcError(f"unknown slot {slot}")
            rarity, level = int(r["rarity"]), int(r["level"])
            set_id = str(r["set_id"])
            if set_id not in known_sets:
                raise CalcError(f"unknown set {set_id}")
            key = main_stat_key(slot, r["mainstat"])
            subs: dict[str, float] = {}
            for s in r.get("substats") or []:
                skey = SUB_NAMES.get(s["key"])
                if skey is None:
                    raise CalcError(f"unknown substat {s['key']}")
                if s.get("count") is not None and s.get("step") is not None:
                    value = sub_value(meta, rarity, skey, int(s["count"]), int(s["step"]))
                else:
                    value = float(s["value"]) / (100 if s["key"].endswith("_") else 1)
                subs[skey] = subs.get(skey, 0.0) + value
            relic = Relic(uid=str(r.get("_uid") or f"relic_{i}"), set_id=set_id, slot=slot, rarity=rarity, level=level,
                          main=key, main_value=main_value(meta, rarity, slot, key, level), subs=subs,
                          location=str(r.get("location") or ""))
            relic.validate()
        except CalcError as e:
            raise CalcError(f"relic #{i + 1}: {e}") from None
        except (KeyError, TypeError, ValueError) as e:
            raise CalcError(f"relic #{i + 1}: missing or bad field {e}") from None
        relics.append(relic)
    uid = (data.get("metadata") or {}).get("uid")
    return KelzExport(source=str(data.get("source", "")), relics=relics, characters=list(data.get("characters") or []),
                      light_cones=list(data.get("light_cones") or []), uid=uid)


def character_request(export: KelzExport, cid: str) -> dict:
    """The "character" part of an evaluate request for a character in the export (as a dict for api.CharacterRequest),
    with the light cone it wears."""
    ch = next((c for c in export.characters if str(c.get("id")) == str(cid)), None)
    if ch is None:
        raise CalcError(f"character {cid} isn't in the export")
    skills = ch.get("skills") or {}
    # Levels are clamped to the pre-eidolon caps: whether an export counts eidolon bonuses in or not, a maxed
    # ability then comes out right (the engine adds the eidolon bonus itself).
    abilities = {k: max(1, min(int(skills[k]), DEFAULT_LEVELS[k])) for k in ("basic", "skill", "ult", "talent") if k in skills}
    memo = ch.get("memosprite") or {}
    if memo.get("skill"):
        abilities["memo_skill"] = max(1, min(int(memo["skill"]), DEFAULT_LEVELS["memo_skill"]))
    if memo.get("talent"):
        abilities["memo_talent"] = max(1, min(int(memo["talent"]), DEFAULT_LEVELS["memo_talent"]))
    traces = {k: bool(v) for k, v in (ch.get("traces") or {}).items() if k.startswith(("ability_", "stat_"))}
    cone = next((c for c in export.light_cones if str(c.get("location")) == str(cid)), None)
    out = {"id": str(cid), "level": int(ch.get("level", 80)), "ascension": int(ch.get("ascension", 6)),
           "eidolon": int(ch.get("eidolon", 0)), "abilities": abilities, "traces": traces or None,
           "ability_version": int(ch["ability_version"]) if ch.get("ability_version") is not None else None}
    if cone:
        out["light_cone"] = {"id": str(cone["id"]), "level": int(cone.get("level", 80)),
                             "ascension": int(cone.get("ascension", 6)), "rank": int(cone.get("superimposition", 1))}
    return out
