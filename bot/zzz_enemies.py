"""The bosses of Zenless Zone Zero's Shiyu Defense and Deadly Assault, with their level and HP, for the /zzz-sd and
/zzz-da cards.

They come from Hakushin's game data (the data behind zzz.nanoka.cc). Each mode has a season list and a file per
season:

    Shiyu Defense    zzz/<version>/shiyu.json   zzz/<version>/en/shiyu/<zone>.json   HoYoLAB's zone id (62061)
    Deadly Assault   zzz/<version>/boss.json    zzz/<version>/en/boss/<zone>.json    690501 (69041 and older: 5 digits)

A Shiyu Defense season's "zone" holds each frontier; the final one's three battles (HoYoLAB's layer ids, 62061051 to
62061053) are the zones scored by damage ("goal_type" 2), each with one room whose "monster_icon" names its boss. A
Deadly Assault season has two "modes": zone_type 1001, the three regular bosses (a zone each, "stage_num" 1 to 3),
and 1002, Adversity Mode's one boss.

Each room lists its monsters with their final stats for that room: Hakushin works the HP out as

    the variant's base HP (en/monster/<id>.json, monster_info[variant].stats.hp)
    × its HP growth at the room's level (curves.hp.curve[level - 1] / 100)
    × the room's own HP multiplier (not in Hakushin's files)

The last factor is a whole multiple of the same step in every season of both modes (×18 for Shiyu Defense's elites,
×22 to ×100 for the bosses), so the first two are taken as read and the room's value is used as is, rounded. A boss
has one HP bar in both modes.

Deadly Assault scores the damage dealt, but its bosses' HP is real: beating one ends the fight early for a time bonus.
It is fixed for the season (each boss at level 70).

A season's bosses never change, so each one's are kept in zzz_enemies.json once found.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from .effective import HAKUSHIN

log = logging.getLogger(__name__)

INDEXES = {"sd": "shiyu.json", "da": "boss.json"}  # each mode's season list
PATHS = {"sd": "en/shiyu/{season}.json", "da": "en/boss/{season}.json"}
REGULAR, ADVERSITY = 1001, 1002  # Deadly Assault's zone types
CACHE_VERSION = 2  # 2: the game version beside the day a boss last came

# The day each ZZZ version went live (global), to tell which one a season ran in: Hakushin's season lists have only
# dates. From the publisher's announcements as reported by Gematsu, RPGSite and others (1.0 to 1.3 from the same
# outlets at the time). A date after the last one counts as that version for VERSION_SPAN days at most.
VERSIONS = (("1.0", "2024-07-04"), ("1.1", "2024-08-14"), ("1.2", "2024-09-25"), ("1.3", "2024-11-06"),
            ("1.4", "2024-12-18"), ("1.5", "2025-01-22"), ("1.6", "2025-03-12"), ("1.7", "2025-04-23"),
            ("2.0", "2025-06-06"), ("2.1", "2025-07-16"), ("2.2", "2025-09-04"), ("2.3", "2025-10-15"),
            ("2.4", "2025-11-26"), ("2.5", "2025-12-30"), ("2.6", "2026-02-06"), ("2.7", "2026-03-24"),
            ("2.8", "2026-05-06"), ("3.0", "2026-06-17"), ("3.1", "2026-07-29"), ("3.2", "2026-09-09"),
            ("3.3", "2026-10-21"))
VERSION_SPAN = 56  # a version runs about six weeks


def clean(name: str | None) -> str:
    return re.sub(r"<[^>]*>", "", name or "").strip()


def _stem(path: str | None) -> str:
    """'.../IconMonster_Sentinel.png' -> 'Sentinel', '.../Monster_Girtablu_HC.png' -> 'Girtablu_HC'."""
    name = (path or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return re.sub(r"^(Icon)?Monster_", "", name)


def art_url(image_path: str | None) -> str | None:
    """The boss's card picture on Hakushin: UI/.../BossCardLv03/Monster_Sentinel.png -> .../assets/zzz/Monster_Sentinel.webp."""
    if not image_path:
        return None
    stem = image_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return f"{HAKUSHIN}/assets/zzz/{stem}.webp"


def _num(v, default: float = 0.0) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return default
    return n if n == n else default


def name_key(name: str | None) -> str:
    """A name to match on: 'Notorious - Dead End Butcher' -> 'notoriousdeadendbutcher'."""
    return re.sub(r"[\W_]+", "", (name or "").casefold())


def enemy(variant: str, monster: dict, level) -> dict:
    """One boss as the card shows it: {"id" (the room's variant), "monster" (Hakushin's monster id), "name", "level",
    "hp", "art"}."""
    hp = _num((monster.get("stats") or {}).get("hp"))
    return {"id": int(_num(variant)), "monster": int(_num(monster.get("id"))), "name": clean(monster.get("name")),
            "level": int(_num(level)), "hp": int(hp + 0.5) if hp > 0 else None, "art": art_url(monster.get("image"))}


def room_boss(room: dict, level) -> dict | None:
    """The room's boss: the monster its icon names, else the one with the most HP."""
    monsters = [(k, m) for k, m in (room.get("monster_list") or {}).items() if isinstance(m, dict)]
    if not monsters:
        return None
    icon = _stem(room.get("monster_icon")).casefold()
    named = [(k, m) for k, m in monsters if icon and _stem(m.get("image")).casefold() == icon]
    key, monster = (named or sorted(monsters, key=lambda km: -_num((km[1].get("stats") or {}).get("hp"))))[0]
    return enemy(key, monster, level)


def _zones(season: Any) -> list[tuple[str, dict, int]]:
    """Every zone of a season file as (zone id, zone, zone type); Shiyu Defense's have no type (0)."""
    if not isinstance(season, dict):
        return []
    if isinstance(season.get("modes"), list):
        return [(str(k), z, int(_num(m.get("zone_type")))) for m in season["modes"] if isinstance(m, dict)
                for k, z in (m.get("zone") or {}).items() if isinstance(z, dict)]
    return [(str(k), z, 0) for k, z in (season.get("zone") or {}).items() if isinstance(z, dict)]


def _first_room(zone: dict) -> dict:
    return next((r for r in (zone.get("layer_room") or {}).values() if isinstance(r, dict)), {})


def season_bosses(mode: str, season: Any) -> dict[str, list[dict]]:
    """Battle -> its boss for one season, under every key a record can name it by:

    Shiyu Defense: each final-frontier battle's layer id (62061051).
    Deadly Assault: each regular boss's place ("1" to "3") and "adversity", and each one's name (the zone's and the
    monster's) as "name:<name_key>" ("adversity-name:..." for Adversity Mode's)."""
    out: dict[str, list[dict]] = {}
    for zone_id, zone, kind in _zones(season):
        if mode == "sd":
            if int(_num(zone.get("goal_type"))) != 2 or not zone.get("layer_room"):
                continue
            if boss := room_boss(_first_room(zone), zone.get("monster_level")):
                out[zone_id] = [boss]
        elif mode == "da" and kind in (REGULAR, ADVERSITY):
            boss = room_boss(_first_room(zone), zone.get("monster_level"))
            if not boss:
                continue
            prefix = "adversity-name" if kind == ADVERSITY else "name"
            out["adversity" if kind == ADVERSITY else str(int(_num(zone.get("stage_num"))))] = [boss]
            for name in (zone.get("name"), boss["name"]):
                if name_key(name):
                    out.setdefault(f"{prefix}:{name_key(name)}", [boss])
    return out


# The last time a boss appeared -----------------------------------------------------------------------------------
#
# "Last time" is the most recent earlier season of the same mode in which the same boss stood in the same place:
# Shiyu Defense's final frontier (any of its three battles), Deadly Assault's regular bosses (any of the three) or
# its Adversity Mode boss. The same variant is looked for first, then the same monster, then the same name.


def node_slot(mode: str, key: str) -> str:
    if mode == "sd":
        return "final"
    if mode == "da":
        return "adversity" if key == "adversity" else "boss" if key in ("1", "2", "3") else ""
    return ""


def season_slots(mode: str, season: Any) -> dict[str, list[dict]]:
    """Slot -> the bosses of one season (see node_slot)."""
    out: dict[str, list[dict]] = {}
    for key, bosses in season_bosses(mode, season).items():
        if slot := node_slot(mode, key):
            out.setdefault(slot, []).extend(bosses)
    return out


def hp_change(now: dict, before: dict) -> float | None:
    """How much more HP (in %) the boss has now than before."""
    a, b = now.get("hp"), before.get("hp")
    return (a / b - 1) * 100 if a and b else None


def last_seen(boss: dict, slot: str, history: list[tuple[str, str, dict[str, list[dict]]]]) -> tuple[str, str, dict] | None:
    """The latest earlier appearance of this boss in this slot: (season id, season name, that boss). history: (season
    id, name, its slots) newest first."""
    tests = (lambda e: e.get("id") == boss.get("id"),
             lambda e: boss.get("monster") and e.get("monster") == boss.get("monster"),
             lambda e: name_key(e.get("name")) and name_key(e.get("name")) == name_key(boss.get("name")))
    for season_id, name, slots in history:
        candidates = slots.get(slot) or []
        for test in tests:
            if match := next((e for e in candidates if test(e) and e.get("hp")), None):
                return season_id, name, match
    return None


def add_changes(mode: str, found: dict[str, list[dict]], history: list[tuple[str, str, dict[str, list[dict]]]]) -> None:
    """Notes on each boss its HP change since it last appeared ("change", %, and "prev_season", when that was:
    "9 Oct · v3.2"). A boss
    listed under several keys is one dict, so it's noted once."""
    for key, bosses in found.items():
        slot = node_slot(mode, key)
        for e in bosses if slot else ():
            if "change" not in e and (seen := last_seen(e, slot, history)):
                change = hp_change(e, seen[2])
                if change is not None:
                    e["change"], e["prev_season"], e["prev_season_id"] = round(change, 4), seen[1], seen[0]


def order(season_id) -> int:
    """A season's place in time: Deadly Assault's ids went from 69041 to 690421, so a 5-digit id counts as id × 10 + 1
    (Shiyu Defense's 62061 likewise sits before the 620631 a beta lists)."""
    n = int(_num(season_id, -1))
    return n * 10 + 1 if 0 <= n < 100_000 else n


def season_date(entry) -> str:
    """When a season started, from its season list entry: '2026-11-20' (its live start, else its start)."""
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("live_begin") or entry.get("begin") or "")[:10]


def game_version(day: str) -> str:
    """The version live on this day ('2026-10-09' -> '3.2'); empty when it's unknown (before 1.0, or past the last
    listed version's span)."""
    try:
        d = dt.date.fromisoformat(day[:10])
    except ValueError:
        return ""
    starts = [(v, dt.date.fromisoformat(s)) for v, s in VERSIONS]
    live = [(v, s) for v, s in starts if s <= d]
    if not live or (live[-1] == starts[-1] and (d - live[-1][1]).days >= VERSION_SPAN):
        return ""
    return live[-1][0]


def season_label(day: str) -> str:
    """How the card names a past season: '30 Oct · v3.3', or just '30 Oct' when the version isn't known."""
    version = game_version(day)
    return " · ".join(filter(None, (short_date(day), f"v{version}" if version else "")))


def short_date(day: str) -> str:
    """'2026-10-30' -> '30 Oct' (the HP change's "vs" season: every Shiyu season has the same name)."""
    try:
        d = dt.date.fromisoformat(day)
    except ValueError:
        return ""
    return f"{d.day} {d:%b}"


def find_season(index: dict, season_id="", starts: str = "") -> str:
    """The season list's id for HoYoLAB's: the same id, the id × 10 + 1 (Deadly Assault), else the one that started on
    the same day."""
    index = index if isinstance(index, dict) else {}
    sid = str(season_id or "")
    if sid and sid in index:
        return sid
    if sid.isdigit() and str(order(sid)) in index:
        return str(order(sid))
    if starts:
        same = [k for k, e in index.items() if season_date(e) == starts[:10]]
        if same:
            return min(same, key=order)
    return ""


def earlier_seasons(index: dict, season: str) -> list[tuple[str, str]]:
    """The seasons before this one, newest first, as (id, when it started: "30 Oct · v3.3", see season_label)."""
    now = order(season)
    past = [(order(k), str(k), season_label(season_date(e))) for k, e in (index or {}).items()
            if str(k).isdigit() and 0 <= order(k) < now]
    return [(k, d) for _, k, d in sorted(past, reverse=True)]


class ZzzEnemies:
    def __init__(self, cache_dir: str | Path):
        self.path = Path(cache_dir) / "zzz_enemies.json"
        self.seasons_path = Path(cache_dir) / "zzz_seasons.json"

        def load(path: Path, key: str) -> dict:
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}
            return saved.get(key, {}) if saved.get("version") == CACHE_VERSION else {}

        self.known: dict[str, dict[str, list[dict]]] = load(self.path, "found")  # "mode/season" -> its bosses
        self.seasons: dict[str, dict[str, list[dict]]] = load(self.seasons_path, "seasons")  # "mode/season" -> slots
        self.missed: dict[str, float] = {}  # when Hakushin last didn't know it (asked again after an hour)
        self.partial: dict[str, dict[str, list[dict]]] = {}  # found without a full look back, until asked again

    def _save(self, path: Path, key: str, value: dict) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"version": CACHE_VERSION, key: value}), encoding="utf-8")
        except OSError:
            log.exception("Could not save %s", path)

    async def _find(self, session, mode: str, season_id: str, starts: str) -> dict[str, list[dict]]:
        async def get(path: str):
            async with session.get(f"{HAKUSHIN}/{path}") as resp:
                return await resp.json(content_type=None) if resp.status == 200 else None

        manifest = await get("manifest.json") or {}
        zzz = manifest.get("zzz") or {}
        # the live data first: the beta's names can still be untranslated
        for version in dict.fromkeys(filter(None, (zzz.get("live"), zzz.get("latest")))):
            index = await get(f"zzz/{version}/{INDEXES[mode]}") or {}
            season = find_season(index, season_id, starts)
            data = await get(f"zzz/{version}/" + PATHS[mode].format(season=season)) if season else None
            found = season_bosses(mode, data)
            if not found:
                continue
            try:
                await asyncio.wait_for(self._history(get, version, mode, season, index, found), 45)
                found["_history"] = []  # looked back all the way
            except Exception as exc:
                log.info("No full %s history for %s: %s", mode, season, exc)
            return found
        return {}

    async def _history(self, get, version: str, mode: str, season: str, index: dict, found: dict[str, list[dict]]) -> None:
        """Looks back through the mode's earlier seasons, newest first, until every boss's last appearance is found
        (or there are none left), and notes each one's HP change (see add_changes)."""
        wanted = [e for k, es in found.items() if node_slot(mode, k) for e in es]
        history: list[tuple[str, str, dict[str, list[dict]]]] = []
        for past, name in earlier_seasons(index, season):
            key = f"{mode}/{past}"
            if key not in self.seasons:
                past_data = await get(f"zzz/{version}/" + PATHS[mode].format(season=past))
                self.seasons[key] = season_slots(mode, past_data) if past_data else {}
                self._save(self.seasons_path, "seasons", self.seasons)
            history.append((past, name, self.seasons[key]))
            add_changes(mode, found, history)
            if all("change" in e for e in wanted):
                return

    async def enemies(self, session, mode: str, season_id="", starts: str = "") -> dict[str, list[dict]]:
        """Battle -> its boss for this season (see season_bosses; empty when Hakushin doesn't know it). starts: the
        day the season started ('2026-11-20'), to find a season by when HoYoLAB's id isn't Hakushin's."""
        if mode not in PATHS or not (season_id or starts):
            return {}
        key = f"{mode}/{season_id or starts}"
        if key not in self.known and (key not in self.missed or time.monotonic() - self.missed[key] >= 3600):
            try:
                found = await asyncio.wait_for(self._find(session, mode, str(season_id or ""), starts), 60)
            except Exception as exc:
                log.info("No %s bosses for %s: %s", mode, key, exc)
                found = {}
            looked_back = found.pop("_history", None) is not None
            if found and looked_back and all(e.get("hp") for es in found.values() for e in es):
                self.known[key] = found
                self._save(self.path, "found", self.known)
            else:  # nothing, an HP missing or no full history: ask again in an hour
                self.missed[key] = time.monotonic()
                if found:
                    self.partial[key] = found
        return self.known.get(key) or self.partial.get(key, {})
