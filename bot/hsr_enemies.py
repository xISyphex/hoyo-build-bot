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

A node shows the enemies of its last wave (the boss wave), each kind once. An enemy's HP is

    hp_base × hp_modify_ratio × HardLevelGroup[stage group, stage level].HPRatio × EliteGroup[elite group].HPRatio
           × (1 + the wave's param_list[1], Pure Fiction only)

with hp_base from the monster's own file (hsr/<version>/en/monster/<id>.json), hp_modify_ratio from its variant (the
stage names variants like 501402404, the monster 5014024's fourth), and the tables from Hakushin's
HardLevelGroup.json, EliteGroup.json and InfiniteEliteGroup.json (Anomaly Arbitration's wave groups). Pure Fiction's
waves carry FantasticStory_Wave_Ability_0001, which raises every enemy's HP by param_list[1] (see wave_hp_ratio). A
ratio that isn't in the tables leaves the HP unknown (not shown) rather than guessed.

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
MAX_SHOWN = 3  # enemies per node, at most
CACHE_VERSION = 2  # 2: InfiniteEliteGroup and Pure Fiction's wave HP bonus counted


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


class Tables:
    """Hakushin's HardLevelGroup.json, EliteGroup.json and InfiniteEliteGroup.json, as the HP ratio of a (group,
    level) and of an elite group. Waves of Pure Fiction / Anomaly Arbitration name groups from either elite table
    (Anomaly Arbitration's knights use InfiniteEliteGroup's 345+; the two tables share no ids)."""

    def __init__(self, hard_levels: list[dict], elite_groups: list[dict], infinite_groups: list[dict] = ()):
        self.hard = {(int(r["HardLevelGroup"]), int(r["Level"])): _value(r.get("HPRatio")) for r in hard_levels or ()
                     if isinstance(r, dict) and "HardLevelGroup" in r and "Level" in r}
        self.elite = {int(r["EliteGroup"]): _value(r.get("HPRatio")) for rows in (infinite_groups, elite_groups)
                      for r in rows or () if isinstance(r, dict) and "EliteGroup" in r}

    def hp(self, hp_base: float, modify: float, group: int, level: int, elite: int | None,
           wave_ratio: float = 1) -> int | None:
        """The enemy's HP; None when a ratio it needs isn't in the tables (never guessed)."""
        growth = self.hard.get((int(group or 1), int(level)))
        scale = self.elite.get(int(elite)) if elite else 1.0  # no elite group named: unscaled
        if growth is None or scale is None or not hp_base or wave_ratio is None:
            return None
        return int(hp_base * (modify or 1) * growth * scale * wave_ratio + 0.5)


def _value(v) -> float | None:
    """A ratio, written bare (Hakushin) or as {"Value": x} (the raw game files)."""
    if isinstance(v, dict):
        v = v.get("Value")
    return float(v) if isinstance(v, (int, float)) else None


# Finding a floor's stages ----------------------------------------------------------------------------------------


def _list(season) -> list[dict]:
    if isinstance(season, dict):
        season = season.get("level")
    return [f for f in season or () if isinstance(f, dict)]


def _first(events) -> dict | None:
    return next((e for e in events or () if isinstance(e, dict)), None)


PF_WAVE_ABILITY = "FantasticStory_Wave_Ability_0001"


def wave_hp_ratio(wave: dict) -> float | None:
    """How much a Pure Fiction wave multiplies its enemies' HP: its ability FantasticStory_Wave_Ability_0001 gives
    every enemy of the wave AttackAddedRatio = param_list[0] and HPAddedRatio = param_list[1] (the game's
    Config/ConfigAbility/BattleEvent/FantasticStory_Wave_Ability.json), so HP x (1 + param_list[1]). No ability: 1.
    An ability or parameters this doesn't know: None (HP unknown rather than wrong)."""
    ability, params = wave.get("ability") or "", wave.get("param_list") or []
    if not ability:
        return None if params else 1.0
    if ability != PF_WAVE_ABILITY or len(params) != 2 or not isinstance(params[1], (int, float)) or params[1] < 0:
        return None
    return 1.0 + params[1]


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


def enemy(monster_id: int, stage: dict, waves: list[dict], detail: dict | None, tables: Tables) -> dict:
    """One enemy as the card shows it: {"id", "name", "level", "hp", "art"} (hp None when it can't be worked out).
    It stands in the stage's last wave, so that wave's elite group and HP bonus apply."""
    detail = detail or {}
    variant = next((c for c in detail.get("child") or () if isinstance(c, dict) and int(c.get("id") or 0) == monster_id), {})
    level = int(stage.get("level") or 0)
    count = len([w for w in stage.get("monster_list") or () if w])
    wave = waves[min(count, len(waves)) - 1] if waves else {}
    elite = stage.get("elite_group") or wave.get("elite_group") or 0
    hp = tables.hp(float(detail.get("hp_base") or 0), float(variant.get("hp_modify_ratio") or 1),
                   int(stage.get("hard_level_group") or 1), level, elite, wave_hp_ratio(wave))
    return {"id": monster_id, "name": clean(detail.get("name")), "level": level, "hp": hp,
            "art": art_url(detail.get("image_path"))}


def floor_enemies(mode: str, season: Any, details: dict[int, dict], tables: Tables, floor_id: str = "",
                  floor_no: int = 0) -> dict[str, list[dict]]:
    """Node -> its enemies (see stages for the node keys). details: monster id -> its Hakushin monster file."""
    return {node: [enemy(i, stage, waves, details.get(base_id(i)), tables) for i in shown_ids(stage)]
            for node, (stage, waves) in stages(mode, season, floor_id, floor_no).items()}


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
        self.tables: dict[str, Tables] = {}  # version -> its HP tables

    async def _find(self, session, mode: str, season: str, floor: str, floor_no: int) -> dict[str, list[dict]]:
        async def get(path: str):
            async with session.get(f"{HAKUSHIN}/{path}") as resp:
                return await resp.json(content_type=None) if resp.status == 200 else None

        manifest = await get("manifest.json") or {}
        hsr = manifest.get("hsr") or {}
        for version in dict.fromkeys(filter(None, (hsr.get("live"), hsr.get("latest")))):  # live stats first
            data = await get(f"hsr/{version}/" + PATHS[mode].format(season=season))
            if not data:
                continue
            found = stages(mode, data, floor, floor_no)
            if not found:
                continue
            if version not in self.tables:
                hard, elite, infinite = await asyncio.gather(*(get(f"hsr/{version}/{name}.json") for name in
                                                              ("HardLevelGroup", "EliteGroup", "InfiniteEliteGroup")))
                self.tables[version] = Tables(hard or [], elite or [], infinite or [])
            ids = sorted({base_id(i) for stage, _ in found.values() for i in shown_ids(stage)})
            files = await asyncio.gather(*(get(f"hsr/{version}/en/monster/{i}.json") for i in ids))
            details = {i: f for i, f in zip(ids, files) if isinstance(f, dict)}
            return floor_enemies(mode, data, details, self.tables[version], floor, floor_no)
        return {}

    async def enemies(self, session, mode: str, season, floor="", floor_no: int = 0) -> dict[str, list[dict]]:
        """Node -> its enemies for this floor (empty when Hakushin doesn't know it)."""
        if mode not in PATHS or not season or (mode != "aa" and not (floor or floor_no)):
            return {}
        key = f"{mode}/{season}/{floor or floor_no}" if mode != "aa" else f"aa/{season}"
        if key not in self.known and (key not in self.missed or time.monotonic() - self.missed[key] >= 3600):
            try:
                found = await asyncio.wait_for(self._find(session, mode, str(season), str(floor or ""), floor_no), 12)
            except Exception as exc:
                log.info("No %s enemies for %s: %s", mode, key, exc)
                found = {}
            if found and all(e.get("hp") for es in found.values() for e in es):
                self.known[key] = found
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_text(json.dumps({"version": CACHE_VERSION, "floors": self.known}), encoding="utf-8")
                except OSError:
                    log.exception("Could not save %s", self.path)
            else:  # nothing, or some HP missing (a monster file wasn't there yet): ask again in an hour
                self.missed[key] = time.monotonic()
                if found:
                    self.partial[key] = found
        return self.known.get(key) or self.partial.get(key, {})
