"""The optimize request: its JSON schema and a strict check of it.

POST /api/hsr/optimize takes one JSON object (unknown keys anywhere are refused; ids are strings of digits as the
meta endpoint gives them, plain integers are accepted too):

    {
      "character": {                       # required
        "id": "1006",                       # required, a character from meta
        "level": 80,                        # 1..80, default 80
        "ascension": 6,                     # 0..6, must fit the level (Lv. 21-30 is ascension 1, ...), default from level
        "eidolon": 0,                       # 0..6, default: the owned character's, else 0
        "abilities": {"1006002": 10},       # ability id (meta abilities[].id) -> 1..its max_level
        "traces": ["1006101", "1006201"],   # trace ids (meta traces[].id) that are unlocked
        "light_cone": {"id": "23007", "level": 80, "rank": 1}   # or null; level 1..80, rank 1..5
      },
      "teammates": [                        # 0..3, all different and not the main character
        {"id": "1005", "eidolon": 0,
         "light_cone": {"id": "23006", "rank": 1},              # or null
         "relic_set": "117", "planar_set": "305"}               # or null
      ],
      "options": {
        "relic_set": "108",                 # a 4-piece relic set id (< 300), or null for the game's first recommendation
        "planar_set": "305",                # a planar set id (>= 300), or null likewise
        "speed": null,                      # true / false forces Speed into / out of the score, null: as the character builds
        "exclude": ["1005"]                 # owned characters whose relics stay on them
      }
    }

check() returns a clean copy with every default filled in, or raises Invalid with one message per bad field.
"""

from __future__ import annotations

MAX_LEVEL = 80


class Invalid(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))
        self.errors = errors


def ascension_for(level: int) -> int:
    """The lowest ascension a level needs (Lv. 21 needs 1, Lv. 71 needs 6)."""
    return max(0, min(6, -(-(level - 20) // 10)))


def ascension_fits(level: int, ascension: int) -> bool:
    """Ascension a allows levels up to 20 + 10a, and needs the level of the ascension before it reached."""
    return level <= 20 + 10 * ascension and (ascension == 0 or level >= 10 + 10 * ascension)


class _Checker:
    def __init__(self, meta: dict):
        self.errors: list[dict] = []
        self.characters = {c["id"]: c for c in meta["characters"]}
        self.cones = {c["id"]: c for c in meta["light_cones"]}
        self.relic_sets = {s["id"] for s in meta["relic_sets"]}
        self.planar_sets = {s["id"] for s in meta["planar_sets"]}

    def fail(self, field: str, message: str) -> None:
        self.errors.append({"field": field, "message": message})

    def obj(self, value, field: str, allowed: set[str], required: set[str] = frozenset()) -> dict | None:
        if not isinstance(value, dict):
            self.fail(field or "body", "must be a JSON object")
            return None
        for key in value:
            if key not in allowed:
                self.fail(f"{field}.{key}" if field else str(key), "unknown field")
        for key in required:
            if key not in value:
                self.fail(f"{field}.{key}" if field else key, "is required")
        return value

    def integer(self, value, field: str, low: int, high: int) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int):
            self.fail(field, "must be a whole number")
            return None
        if not low <= value <= high:
            self.fail(field, f"must be from {low} to {high}")
            return None
        return value

    def ident(self, value, field: str) -> str | None:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            value = str(value)
        if not isinstance(value, str) or not value.isdigit() or len(value) > 12:
            self.fail(field, "must be an id (digits)")
            return None
        return value

    def character_id(self, value, field: str) -> str | None:
        cid = self.ident(value, field)
        if cid is not None and cid not in self.characters:
            self.fail(field, "unknown character")
            return None
        return cid

    def set_id(self, value, field: str, planar: bool) -> str | None:
        if value is None:
            return None
        sid = self.ident(value, field)
        if sid is None:
            return None
        if sid not in (self.planar_sets if planar else self.relic_sets):
            other = sid in (self.relic_sets if planar else self.planar_sets)
            self.fail(field, f"is a {'relic' if planar else 'planar'} set, not a {'planar' if planar else 'relic'} set"
                      if other else f"unknown {'planar' if planar else 'relic'} set")
            return None
        return sid

    def light_cone(self, value, field: str, with_level: bool) -> dict | None:
        if value is None:
            return None
        keys = {"id", "rank"} | ({"level"} if with_level else set())
        if self.obj(value, field, keys, {"id"}) is None:
            return None
        out = {"id": self.ident(value.get("id"), f"{field}.id"), "rank": 1}
        if out["id"] is not None and out["id"] not in self.cones:
            self.fail(f"{field}.id", "unknown light cone")
        if "rank" in value:
            out["rank"] = self.integer(value["rank"], f"{field}.rank", 1, 5)
        if with_level:
            out["level"] = self.integer(value["level"], f"{field}.level", 1, MAX_LEVEL) if "level" in value else MAX_LEVEL
        return out

    def main(self, value) -> dict | None:
        keys = {"id", "level", "ascension", "eidolon", "abilities", "traces", "light_cone"}
        if self.obj(value, "character", keys, {"id"}) is None:
            return None
        cid = self.character_id(value.get("id"), "character.id")
        out: dict = {"id": cid, "given": sorted(k for k in value if k != "id")}
        level = self.integer(value.get("level", MAX_LEVEL), "character.level", 1, MAX_LEVEL)
        out["level"] = level
        if "ascension" in value:
            asc = self.integer(value["ascension"], "character.ascension", 0, 6)
            if asc is not None and level is not None and not ascension_fits(level, asc):
                self.fail("character.ascension", f"ascension {asc} doesn't fit level {level}")
            out["ascension"] = asc
        else:
            out["ascension"] = ascension_for(level or MAX_LEVEL)
        out["eidolon"] = self.integer(value["eidolon"], "character.eidolon", 0, 6) if "eidolon" in value else None
        known = self.characters.get(cid) if cid else None
        abilities = {a["id"]: a for a in (known or {}).get("abilities", [])}
        out["abilities"] = {}
        given = value.get("abilities", {})
        if not isinstance(given, dict):
            self.fail("character.abilities", "must be an object of ability id -> level")
        else:
            for aid, lvl in given.items():
                field = f"character.abilities.{aid}"
                if known is not None and aid not in abilities:
                    self.fail(field, "unknown ability for this character")
                    continue
                cap = abilities[aid]["max_level"] if aid in abilities else 15
                out["abilities"][aid] = self.integer(lvl, field, 1, cap)
        traces = {t["id"] for t in (known or {}).get("traces", [])}
        out["traces"] = []
        given = value.get("traces", [])
        if not isinstance(given, list) or len(given) > 64:
            self.fail("character.traces", "must be a list of trace ids")
        else:
            for i, tid in enumerate(given):
                tid = self.ident(tid, f"character.traces[{i}]")
                if tid is None:
                    continue
                if known is not None and tid not in traces:
                    self.fail(f"character.traces[{i}]", "unknown trace for this character")
                elif tid in out["traces"]:
                    self.fail(f"character.traces[{i}]", "listed twice")
                else:
                    out["traces"].append(tid)
        out["light_cone"] = self.light_cone(value.get("light_cone"), "character.light_cone", True)
        return out

    def teammates(self, value, main_id: str | None) -> list[dict]:
        if not isinstance(value, list):
            self.fail("teammates", "must be a list")
            return []
        if len(value) > 3:
            self.fail("teammates", "at most 3 teammates")
            return []
        out, seen = [], {main_id}
        for i, mate in enumerate(value):
            field = f"teammates[{i}]"
            if self.obj(mate, field, {"id", "eidolon", "light_cone", "relic_set", "planar_set"}, {"id"}) is None:
                continue
            cid = self.character_id(mate.get("id"), f"{field}.id")
            if cid is not None and cid in seen:
                self.fail(f"{field}.id", "is already in the team")
            seen.add(cid)
            out.append({
                "id": cid,
                "eidolon": self.integer(mate["eidolon"], f"{field}.eidolon", 0, 6) if "eidolon" in mate else 0,
                "light_cone": self.light_cone(mate.get("light_cone"), f"{field}.light_cone", False),
                "relic_set": self.set_id(mate.get("relic_set"), f"{field}.relic_set", False),
                "planar_set": self.set_id(mate.get("planar_set"), f"{field}.planar_set", True),
            })
        return out

    def options(self, value) -> dict:
        out = {"relic_set": None, "planar_set": None, "speed": None, "exclude": []}
        if self.obj(value, "options", {"relic_set", "planar_set", "speed", "exclude"}) is None:
            return out
        out["relic_set"] = self.set_id(value.get("relic_set"), "options.relic_set", False)
        out["planar_set"] = self.set_id(value.get("planar_set"), "options.planar_set", True)
        speed = value.get("speed")
        if speed is not None and not isinstance(speed, bool):
            self.fail("options.speed", "must be true, false or null")
        else:
            out["speed"] = speed
        exclude = value.get("exclude", [])
        if not isinstance(exclude, list) or len(exclude) > 64:
            self.fail("options.exclude", "must be a list of character ids")
        else:
            for i, cid in enumerate(exclude):
                cid = self.ident(cid, f"options.exclude[{i}]")
                if cid is not None and cid not in out["exclude"]:
                    out["exclude"].append(cid)
        return out


def check(body, meta: dict) -> dict:
    c = _Checker(meta)
    if c.obj(body, "", {"character", "teammates", "options"}, {"character"}) is None:
        raise Invalid(c.errors)
    main = c.main(body.get("character")) if "character" in body else None
    result = {"character": main, "teammates": c.teammates(body.get("teammates", []), (main or {}).get("id")),
              "options": c.options(body.get("options", {}))}
    if c.errors:
        raise Invalid(c.errors)
    return result
