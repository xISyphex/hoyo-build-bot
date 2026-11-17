"""The enemies of each Star Rail endgame node, with their level and HP, for the /hsr-moc, /hsr-pf, /hsr-apoc and
/hsr-aa cards.

They come from Hakushin's game data (the data behind hsr.nanoka.cc/maze). Each mode has a file per season:

    Memory of Chaos       hsr/<version>/en/maze/<schedule>.json    a list of floors (by maze id), Starward the last
    Pure Fiction          hsr/<version>/en/story/<schedule>.json   the same under "level"
    Apocalyptic Shadow    hsr/<version>/en/boss/<schedule>.json    a difficulty per entry under "level"
    Anomaly Arbitration   hsr/<version>/en/peak/<group>.json       "pre_level" (the knights), "boss_level" (the King)
                                                                   and "boss_config" (the King on Plight)

A floor's two halves are its "event_id_list1" / "event_id_list2" (the Starward floor has one "event_id_list"), each a
stage: its level, its HP growth curve ("hard_level_group"), an HP scale ("elite_group"; Pure Fiction and Anomaly
Arbitration put it on each wave under "infinite_list") and its waves of monster ids ("monster_list").

A node shows the enemies of its last wave (the boss wave), each kind once. An enemy's HP is worked out exactly as
hsr.nanoka.cc does it (its function in _app/immutable/chunks/BEQWqNLk.js, checked against its pages):

    HPBase × HPModifyRatio × EliteGroup.HPRatio × HardLevelGroup[stage group, stage level].HPRatio
           × (1 + the wave's param_list[1])          Pure Fiction / Anomaly Arbitration waves ("infinite_list")
    rounded to the nearest whole number

from monstervalue.json (HPBase, and the variant's HPModifyRatio: the stage names variants like 501402404, the
monster 5014024's; a variant not listed takes the first) and HardLevelGroup.json. The elite group is the stage's,
or for a wave-based stage the last wave's (EliteGroup.json, then InfiniteEliteGroup.json, which holds Anomaly
Arbitration's 345+); one in neither table falls back to the variant's own group, then to ×1. Pure Fiction's
param_list[1] is the HPAddedRatio its wave ability (FantasticStory_Wave_Ability_0001) gives every enemy of the wave.
A boss with several HP bars (MaxMonsterPhase) shows its HP per bar and the bar count, like the site ("HP 6,241,196
x 2"); bars of different size (PhaseList's PhaseMaxHPRatio) are each shown.

The data version is the site's default (the manifest's latest), then the live one.

A season's enemies never change, so each floor's are kept in hsr_enemies.json once found.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from .effective import HAKUSHIN

log = logging.getLogger(__name__)

PATHS = {"moc": "en/maze/{season}.json", "pf": "en/story/{season}.json", "apoc": "en/boss/{season}.json",
         "aa": "en/peak/{season}.json"}
INDEXES = {"moc": "maze.json", "pf": "maze_extra.json", "apoc": "maze_boss.json", "aa": "maze_peak.json"}  # seasons
MAX_SHOWN = 3  # enemies per node, at most
CACHE_VERSION = 6  # 6: with Voracity Corrosion


def base_id(monster_id) -> int:
    """The monster a stage's variant id belongs to: 501402404 -> 5014024 (ids of 7 digits are the monster itself)."""
    n = int(monster_id)
    return n // 100 if n >= 100_000_000 else n


def art_url(image_path: str | None) -> str | None:
    """The monster's full figure on Hakushin: SpriteOutput/MonsterFigure/Monster_5014020.png -> .../Monster_5014020.webp."""
    if not image_path:
        return None
    stem = image_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return f"{HAKUSHIN}/assets/hsr/monsterfigure/{stem}.webp"


def clean(name: str | None) -> str:
    return re.sub(r"<[^>]*>|\{RUBY_[BE]#[^}]*\}", "", name or "").strip()


def _num(v, default: float = 0.0) -> float:
    """A number, written bare (Hakushin) or as {"Value": x} (the raw game files); default when it isn't one."""
    if isinstance(v, dict):
        v = v.get("Value")
    try:
        n = float(v)
    except (TypeError, ValueError):
        return default
    return n if n == n else default


class Tables:
    """Hakushin's HardLevelGroup.json, EliteGroup.json, InfiniteEliteGroup.json and monstervalue.json."""

    def __init__(self, hard_levels: list[dict], elite_groups: list[dict], infinite_groups: list[dict] = (),
                 values: dict | None = None):
        self.hard = {(int(r["HardLevelGroup"]), int(r["Level"])): r for r in hard_levels or ()
                     if isinstance(r, dict) and "HardLevelGroup" in r and "Level" in r}
        self.elite = {int(r["EliteGroup"]): r for r in elite_groups or () if isinstance(r, dict) and "EliteGroup" in r}
        self.infinite = {int(r["EliteGroup"]): r for r in infinite_groups or () if isinstance(r, dict) and "EliteGroup" in r}
        self.values = values or {}

    def _elite(self, group, variant: dict, waves: bool) -> dict:
        for g in (int(_num(group)), int(_num(variant.get("EliteGroup")))):  # the stage's / wave's, else the variant's
            row = self.elite.get(g) or (self.infinite.get(g) if waves else None)
            if row:
                return row
        return {}

    def hp(self, monster_id: int, stage: dict, wave: dict | None = None) -> dict | None:
        """{"hp": per bar, "bars": count, "phases": [ratio per bar]} for this enemy in this stage (and wave, for a
        wave-based stage); None when monstervalue.json doesn't have it."""
        value = self.values.get(str(base_id(monster_id))) or {}
        children = [c for c in value.get("child") or () if isinstance(c, dict)]
        variant = next((c for c in children if int(_num(c.get("Id"))) == monster_id), None) \
            or next((c for c in children if base_id(int(_num(c.get("Id")))) == base_id(monster_id)), None) \
            or (children[0] if children else None)
        if not value or variant is None:
            return None
        waves = wave is not None
        elite = self._elite((wave or {}).get("elite_group") if waves else stage.get("elite_group"), variant, waves)
        hard = self.hard.get((int(_num(stage.get("hard_level_group"))), int(_num(stage.get("level"))))) or {}
        hp = _num(value.get("HPBase")) * _num(variant.get("HPModifyRatio"), 1) * _num(elite.get("HPRatio"), 1) \
            * _num(hard.get("HPRatio"), 1)
        if waves and isinstance(wave.get("param_list"), list):
            params = wave["param_list"]
            hp *= 1 + _num(params[1] if len(params) > 1 else None)
        bars = int(_num(value.get("MaxMonsterPhase"), 1)) or 1
        phases = [_num(p.get("PhaseMaxHPRatio", p.get("phase_max_hp_ratio")), 1)  # Hakushin writes it both ways
                  for p in value.get("PhaseList") or () if isinstance(p, dict)]
        return {"hp": int(hp + 0.5) if hp > 0 else None, "bars": max(1, bars), "phases": phases or [1.0]}


# Finding a floor's stages ----------------------------------------------------------------------------------------


def _list(season) -> list[dict]:
    if isinstance(season, dict):
        season = season.get("level")
    return [f for f in season or () if isinstance(f, dict)]


def _first(events) -> dict | None:
    return next((e for e in events or () if isinstance(e, dict)), None)


def _waves(infinite) -> list[dict]:
    """Each wave of a Pure Fiction / Anomaly Arbitration "infinite_list", in order."""
    if not isinstance(infinite, dict):
        return []
    return [infinite[k] or {} for k in sorted(infinite, key=lambda k: int(k))]


def floor_number(name: str | None) -> int:
    """A floor's number from its name: 'Survival of the Fittest (XII)' -> 12, 'Pure Fiction (4)' / '04' -> 4."""
    if found := re.search(r"\(([IVXL]+)\)", name or ""):
        total, prev = 0, 0
        for ch in reversed(found[1]):
            v = {"I": 1, "V": 5, "X": 10, "L": 50}[ch]
            total, prev = total - v if v < prev else total + v, max(prev, v)
        return total
    digits = re.findall(r"\d+", name or "")
    return int(digits[-1]) if digits else 0


def stages(mode: str, season: Any, floor_id: str = "", floor_no: int = 0) -> dict[str, tuple[dict, list[dict]]]:
    """Node -> (its stage, each wave's elite group) for the floor HoYoLAB reported.

    Memory of Chaos / Pure Fiction / Apocalyptic Shadow: "1" and "2" for the floor's halves, "3" for Starward. The
    floor is found by its maze id, else by its number (the n-th floor that isn't Starward).
    Anomaly Arbitration: each knight's maze id and "K1".."K3" by order, the King's id and "KING", and
    "<King's id>:plight" and "PLIGHT" for the King on Plight."""
    out: dict[str, tuple[dict, list[dict]]] = {}
    if mode == "aa":
        if not isinstance(season, dict):
            return out
        for i, level in enumerate(x for x in season.get("pre_level") or () if isinstance(x, dict)):
            if stage := _first(level.get("event_id_list")):
                out[str(level.get("id"))] = out[f"K{i + 1}"] = (stage, _waves(level.get("infinite_list")))
        king = season.get("boss_level") or {}
        if stage := _first(king.get("event_id_list")):
            out[str(king.get("id"))] = out["KING"] = (stage, _waves(king.get("infinite_list")))
        plight = season.get("boss_config") or {}
        if stage := _first(plight.get("event_id_list")):
            out[f"{king.get('id')}:plight"] = out["PLIGHT"] = (stage, _waves(plight.get("infinite_list")))
        return out
    floors = _list(season)
    halves = [f for f in floors if f.get("event_id_list1") or f.get("event_id_list2")]
    floor = next((f for f in halves if floor_id and str(f.get("id")) == str(floor_id)), None)
    if floor is None and 0 < floor_no <= len(halves):
        floor = halves[floor_no - 1]
    if floor is not None:
        for node in ("1", "2"):
            if stage := _first(floor.get(f"event_id_list{node}")):
                out[node] = (stage, _waves(floor.get(f"infinite_list{node}")))
    starward = next((f for f in floors if f.get("event_id_list")), None)  # the one floor with a single stage
    if starward and (stage := _first(starward.get("event_id_list"))):
        out["3"] = (stage, _waves(starward.get("infinite_list")))
    return out


def shown_ids(stage: dict) -> list[int]:
    """The enemies a node shows: its last wave's, each kind once, in the order they stand."""
    waves = [w for w in stage.get("monster_list") or () if isinstance(w, dict) and w]
    if not waves:
        return []
    last = waves[-1]
    ids = [last[k] for k in sorted(last, key=lambda k: int(re.sub(r"\D", "", k) or 0)) if last[k]]
    return list(dict.fromkeys(int(i) for i in ids))[:MAX_SHOWN]


def enemy(monster_id: int, stage: dict, waves: list[dict], names: dict, tables: Tables) -> dict:
    """One enemy as the card shows it: {"id", "name", "level", "hp", "bars", "phases", "art"} (hp None when it can't
    be worked out). It stands in the stage's last wave, so for a wave-based stage that wave's elite group and HP
    bonus apply."""
    info = names.get(str(base_id(monster_id))) or {}
    count = len([w for w in stage.get("monster_list") or () if w])
    wave = waves[min(count, len(waves)) - 1] if waves else None
    worked = tables.hp(monster_id, stage, wave) or {}
    phases = worked.get("phases") or [1.0]
    out = {"id": monster_id, "name": clean(info.get("en")), "level": int(_num(stage.get("level"))),
           "hp": worked.get("hp"), "bars": worked.get("bars", 1),
           "phases": phases if len(phases) > 1 and len(set(phases)) > 1 else [], "art": art_url(info.get("icon"))}
    return out | voracity(monster_id, stage)


def voracity(monster_id: int, stage: dict) -> dict:
    """Voracity Corrosion on this enemy, as hsr.nanoka.cc finds it: the stage's "invasion" lists the corroded
    enemies by id, and its maze_buff_param[1] is their Voracity HP as a share of one bar's HP. {"voracity": share,
    "corrosion": level}, or {} when it isn't corroded."""
    inv = stage.get("invasion") if isinstance(stage.get("invasion"), dict) else {}
    level = int(_num(inv.get("level", inv.get("Level"))))
    params = inv.get("maze_buff_param", inv.get("MazeBuffParam")) or []
    share = _num(params[1]) if len(params) > 1 else 0
    listed = {int(_num(m.get("monster_id", m.get("MonsterID")))) for m in inv.get("monster_list", inv.get("MonsterList")) or ()
              if isinstance(m, dict)}
    return {"voracity": share, "corrosion": level} if level > 0 and share > 0 and monster_id in listed else {}


def floor_enemies(mode: str, season: Any, names: dict, tables: Tables, floor_id: str = "",
                  floor_no: int = 0) -> dict[str, list[dict]]:
    """Node -> its enemies (see stages for the node keys). names: Hakushin's monster.json (names and pictures)."""
    built: dict[int, list[dict]] = {}  # a stage named twice (Anomaly Arbitration: by maze id and by place) shares one list
    return {node: built.setdefault(id(stage), [enemy(i, stage, waves, names, tables) for i in shown_ids(stage)])
            for node, (stage, waves) in stages(mode, season, floor_id, floor_no).items()}


# The last time a boss appeared -----------------------------------------------------------------------------------
#
# "Last time" is the most recent earlier season of the same mode in which the same enemy stood in the same place: the
# same floor / difficulty number (Memory of Chaos XII, Pure Fiction / Apocalyptic Shadow's top one) or that season's
# Starward stage, and for Anomaly Arbitration the same slot (any knight, the King, the King on Plight). The same
# variant id is looked for first, then the same monster, then the same name. HP is compared per bar when both
# appearances have the same bars, else as the total of all bars.


def floor_position(mode: str, season: Any, floor_id: str = "", floor_no: int = 0) -> int:
    """Which floor (1 = the first that isn't Starward) the reported floor is in this season file; 0 if none."""
    if mode == "aa":
        return 0
    halves = [f for f in _list(season) if f.get("event_id_list1") or f.get("event_id_list2")]
    for i, f in enumerate(halves, 1):
        if floor_id and str(f.get("id")) == str(floor_id):
            return i
    return floor_no if 0 < floor_no <= len(halves) else 0


def node_slot(mode: str, node: str) -> str:
    """Where a node's enemies stand, for finding them in an earlier season: "floor", "starward", "knight", "king",
    "plight"."""
    if mode == "aa":  # by place only: the same stages under their maze ids share these lists
        return {"KING": "king", "PLIGHT": "plight", "K1": "knight", "K2": "knight", "K3": "knight"}.get(node, "")
    return "starward" if node == "3" else "floor"


def season_slots(mode: str, season: Any, names: dict, tables: Tables, position: int) -> dict[str, list[dict]]:
    """Slot -> the enemies shown there in one season (see node_slot), for the floor at this position."""
    out: dict[str, list[dict]] = {}
    for node, enemies in floor_enemies(mode, season, names, tables, "", position).items():
        if slot := node_slot(mode, node):
            out.setdefault(slot, []).extend(enemies)
    return out


def _total(e: dict) -> float:
    """All of an enemy's HP bars together."""
    phases = e.get("phases") or []
    return (e.get("hp") or 0) * (sum(phases) if phases else (e.get("bars") or 1))


def hp_change(now: dict, before: dict) -> float | None:
    """How much more HP (in %) the enemy has now than before: per bar when both have the same bars, else in all."""
    same = (now.get("bars") or 1) == (before.get("bars") or 1) and (now.get("phases") or []) == (before.get("phases") or [])
    a, b = (now.get("hp"), before.get("hp")) if same else (_total(now), _total(before))
    return (a / b - 1) * 100 if a and b else None


def last_seen(enemy_: dict, slot: str, history: list[tuple[str, str, dict[str, list[dict]]]]) -> tuple[str, str, dict] | None:
    """The latest earlier appearance of this enemy in this slot: (season id, season name, that enemy). history:
    (season id, name, its slots) newest first."""
    tests = (lambda e: e.get("id") == enemy_.get("id"),
             lambda e: base_id(e.get("id") or 0) == base_id(enemy_.get("id") or 0),
             lambda e: e.get("name") and e.get("name") == enemy_.get("name"))
    for season_id, name, slots in history:
        candidates = slots.get(slot) or []
        for test in tests:
            if match := next((e for e in candidates if test(e) and e.get("hp")), None):
                return season_id, name, match
    return None


def add_changes(mode: str, found: dict[str, list[dict]], history: list[tuple[str, str, dict[str, list[dict]]]]) -> None:
    """Notes on each enemy its HP change since it last appeared ("change", %, and "prev_season", that season's name)."""
    for node, enemies in found.items():
        slot = node_slot(mode, node)
        for e in enemies if slot else ():
            if seen := last_seen(e, slot, history):
                change = hp_change(e, seen[2])
                if change is not None:
                    e["change"], e["prev_season"], e["prev_season_id"] = round(change, 4), seen[1], seen[0]


def earlier_seasons(index: dict, season, more_names: tuple[dict, ...] = ()) -> list[tuple[str, str]]:
    """The seasons before this one in a Hakushin season list (maze.json etc.), newest first, as (id, English name).
    A name missing there is taken from more_names (the same list of other versions), else left empty. For 4-digit
    ids only ids of 4 digits count (Memory of Chaos's old 3-digit ids were another mode)."""
    try:
        now = int(season)
    except (TypeError, ValueError):
        return []

    def english(entry) -> str:
        return clean(entry.get("en")) if isinstance(entry, dict) and entry.get("en") else ""

    out = []
    for key, entry in (index or {}).items():
        key = str(key)
        if not key.isdigit() or (len(str(now)) >= 4 and len(key) != len(str(now))) or int(key) >= now:
            continue
        name = english(entry) or next(filter(None, (english((m or {}).get(key)) for m in more_names)), "")
        out.append((int(key), str(key), re.sub(r"\s*\(\s*\d+(\.\d+)?\s*\)\s*$", "", name)))
    return [(k, n) for _, k, n in sorted(out, reverse=True)]


class HsrEnemies:
    def __init__(self, cache_dir: str | Path):
        self.path = Path(cache_dir) / "hsr_enemies.json"
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        # floors found by an older way of working HP out are found again
        self.known: dict[str, dict[str, list[dict]]] = saved.get("floors", {}) if saved.get("version") == CACHE_VERSION else {}
        self.missed: dict[str, float] = {}  # floor -> when Hakushin last didn't know it (asked again after an hour)
        self.partial: dict[str, dict[str, list[dict]]] = {}  # floors found with an HP missing, until asked again
        self.tables: dict[str, tuple[Tables, dict]] = {}  # version -> its HP tables and monster.json (the last one read)
        # past seasons' enemies by slot, "mode/season/floor" -> {slot: [enemy]} ({} when that season had no such floor)
        self.seasons_path = Path(cache_dir) / "hsr_seasons.json"
        try:
            saved = json.loads(self.seasons_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        self.seasons: dict[str, dict[str, list[dict]]] = saved.get("seasons", {}) if saved.get("version") == CACHE_VERSION else {}

    async def _find(self, session, mode: str, season: str, floor: str, floor_no: int) -> dict[str, list[dict]]:
        async def get(path: str):
            async with session.get(f"{HAKUSHIN}/{path}") as resp:
                return await resp.json(content_type=None) if resp.status == 200 else None

        manifest = await get("manifest.json") or {}
        hsr = manifest.get("hsr") or {}
        versions = list(dict.fromkeys(filter(None, (hsr.get("latest"), hsr.get("live")))))
        for version in versions:  # the site's default first
            data = await get(f"hsr/{version}/" + PATHS[mode].format(season=season))
            if not data:
                continue
            found = stages(mode, data, floor, floor_no)
            if not found:
                continue
            if version not in self.tables:
                files = ("HardLevelGroup", "EliteGroup", "InfiniteEliteGroup", "monstervalue", "monster")
                hard, elite, infinite, values, names = await asyncio.gather(*(get(f"hsr/{version}/{n}.json") for n in files))
                self.tables = {version: (Tables(hard or [], elite or [], infinite or [], values or {}), names or {})}
            tables, names = self.tables[version]
            out = floor_enemies(mode, data, names, tables, floor, floor_no)
            try:
                others = [v for v in versions if v != version]
                await asyncio.wait_for(self._history(get, [version, *others], mode, season, data, floor, floor_no, out), 45)
                out["_history"] = []  # looked back all the way (kept, so it isn't done again)
            except Exception as exc:
                log.info("No full %s history for %s: %s", mode, season, exc)
            return out
        return {}

    async def _history(self, get, versions: list[str], mode: str, season: str, data, floor: str, floor_no: int,
                       found: dict[str, list[dict]]) -> None:
        """Looks back through the mode's earlier seasons, newest first, until every shown enemy's last appearance
        is found (or there are none left), and notes each one's HP change (see add_changes)."""
        version = versions[0]  # the one the floor was found in; the others only for season names
        tables, names = self.tables[version]
        position = floor_position(mode, data, floor, floor_no)
        wanted = {e.get("id") for n, es in found.items() if node_slot(mode, n) for e in es}
        history: list[tuple[str, str, dict[str, list[dict]]]] = []
        indexes = [await get(f"hsr/{v}/{INDEXES[mode]}") or {} for v in versions]
        for past, name in earlier_seasons(indexes[0], season, tuple(indexes[1:])):
            key = f"{mode}/{past}/{position}"
            if key not in self.seasons:
                past_data = await get(f"hsr/{version}/" + PATHS[mode].format(season=past))
                self.seasons[key] = season_slots(mode, past_data, names, tables, position) if past_data else {}
                self._save_seasons()
            history.append((past, name, self.seasons[key]))
            add_changes(mode, found, history)
            if all(any(e.get("id") == i and "change" in e for es in found.values() for e in es) for i in wanted):
                return

    def _save_seasons(self) -> None:
        try:
            self.seasons_path.parent.mkdir(parents=True, exist_ok=True)
            self.seasons_path.write_text(json.dumps({"version": CACHE_VERSION, "seasons": self.seasons}), encoding="utf-8")
        except OSError:
            log.exception("Could not save %s", self.seasons_path)

    async def enemies(self, session, mode: str, season, floor="", floor_no: int = 0) -> dict[str, list[dict]]:
        """Node -> its enemies for this floor (empty when Hakushin doesn't know it)."""
        if mode not in PATHS or not season or (mode != "aa" and not (floor or floor_no)):
            return {}
        key = f"{mode}/{season}/{floor or floor_no}" if mode != "aa" else f"aa/{season}"
        if key not in self.known and (key not in self.missed or time.monotonic() - self.missed[key] >= 3600):
            try:
                found = await asyncio.wait_for(self._find(session, mode, str(season), str(floor or ""), floor_no), 60)
            except Exception as exc:
                log.info("No %s enemies for %s: %s", mode, key, exc)
                found = {}
            looked_back = found.pop("_history", None) is not None
            if found and looked_back and all(e.get("hp") for es in found.values() for e in es):
                self.known[key] = found
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text(json.dumps({"version": CACHE_VERSION, "floors": self.known}), encoding="utf-8")
                except OSError:
                    log.exception("Could not save %s", self.path)
            else:  # nothing, an HP missing (a monster file wasn't there yet) or no full history: ask again in an hour
                self.missed[key] = time.monotonic()
                if found:
                    self.partial[key] = found
        return self.known.get(key) or self.partial.get(key, {})
