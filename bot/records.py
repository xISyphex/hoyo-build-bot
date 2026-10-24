"""Battle records: a player's endgame runs from HoYoLAB's Battle Chronicle, for /hsr-records, /zzz-records and
/genshin-records.

Each mode is read with genshin.py and boiled down to a Record: a few headline numbers and the teams that were used,
each character with their copies (eidolons / constellations / mindscapes) and their weapon's copies. HoYoLAB's
records only carry the character's own copies, so the weapon's come from the player's character list (the same one
the build cards use), when HoYoLAB shares it.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import genshin

from .models import CharacterBuild

log = logging.getLogger(__name__)


@dataclass
class Member:
    id: str
    icon_url: str | None
    level: int = 0
    rarity: int = 0  # 4 / 5 (ZZZ: A = 4, S = 5)
    copies: int | None = None  # eidolon / constellation / mindscape
    weapon_copies: int | None = None  # superimposition / refinement / phase
    weapon_rarity: int | None = None  # 3 / 4 / 5 (ZZZ: B = 3, A = 4, S = 5)


@dataclass
class Team:
    label: str  # e.g. "Node 1", "Wolf Knight", "12-3 · First half"
    # This node's own results, each drawn with its icon: ("stars", "3/3"), ("cycles", "2"), ("score", "40,000"),
    # ("rating", "S"), ("time", "1:44"), ("text", "boss not defeated")
    chips: list[tuple[str, str]] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)
    stage: str = ""  # set for a stage shown in its own row under the others, with this header (e.g. "King")
    art: str | None = None  # the boss's picture from HoYoLAB, faded into the panel
    left: list[tuple[str, str]] = field(default_factory=list)  # headline-style tiles beside a stage's box
    right: list[tuple[str, str]] = field(default_factory=list)
    plight: bool = False  # the King beaten on Plight (hard) mode: a red shimmer around the box
    bangboo: Member | None = None  # ZZZ: the Bangboo that came along
    key: str = ""  # ZZZ Shiyu Defense: the battle's layer id; Star Rail: the node ("3" Starward), to look its boss up by


@dataclass
class Record:
    mode: str  # the trigger, e.g. "moc"
    title: str  # e.g. "Memory of Chaos"
    season: str = ""  # e.g. "Floor 12 · Lupine Moon"
    headline: list[tuple[str, str]] = field(default_factory=list)  # e.g. [("Stars", "36 / 36"), ("Cycles", "8")]
    teams: list[Team] = field(default_factory=list)
    empty: str | None = None  # why there's nothing to show, e.g. "No runs this season yet."
    medal: str | None = None  # Anomaly Arbitration's medal picture from HoYoLAB
    season_id: str = ""  # ZZZ Shiyu Defense: HoYoLAB's zone id for the season; Star Rail: the season's schedule id
    floor_id: str = ""  # Star Rail Memory of Chaos / Pure Fiction: the shown floor's maze id


@dataclass(frozen=True)
class Mode:
    key: str
    title: str
    aliases: tuple[str, ...] = ()


MODES: dict[str, tuple[Mode, ...]] = {
    "hsr": (
        Mode("moc", "Memory of Chaos", ("memory", "chaos")),
        Mode("pf", "Pure Fiction", ("fiction",)),
        Mode("apoc", "Apocalyptic Shadow", ("as", "shadow")),
        Mode("aa", "Anomaly Arbitration", ("anomaly", "arbitration")),
    ),
    "zzz": (
        Mode("sd", "Shiyu Defense", ("shiyu",)),
        Mode("da", "Deadly Assault", ("assault",)),
    ),
    "genshin": (
        Mode("abyss", "Spiral Abyss", ("sa", "spiral")),
        Mode("theater", "Imaginarium Theater", ("it", "imaginarium", "theatre")),
        Mode("stygian", "Stygian Onslaught", ("so", "onslaught")),
    ),
}
COPY_LETTERS = {"hsr": ("E", "S"), "genshin": ("C", "R"), "zzz": ("M", "W")}  # ZZZ: Mindscape, W-Engine


def parse_modes(game: str, text: str | None) -> tuple[list[str], list[str]]:
    """The modes asked for, in the order typed (all of them when nothing is typed), and any words not understood."""
    known = {}
    for mode in MODES[game]:
        for name in (mode.key, *mode.aliases):
            known[name] = mode.key
    picked, unknown = [], []
    for word in re.split(r"[\s,+/]+", (text or "").lower()):
        if not word:
            continue
        if word in ("all", "every"):
            picked += [m.key for m in MODES[game]]
        elif word in known:
            picked.append(known[word])
        else:
            unknown.append(word)
    if not picked and not unknown:
        picked = [m.key for m in MODES[game]]
    return list(dict.fromkeys(picked)), unknown


def copies_label(game: str, member: Member) -> str:
    """'E2S1', 'C0R5', 'M6P1'; just 'E2' when the weapon isn't known."""
    char, weapon = COPY_LETTERS[game]
    text = f"{char}{member.copies}" if member.copies is not None else ""
    if member.weapon_copies is not None:
        text += f"{weapon}{member.weapon_copies}"
    return text


def fill_copies(records: list[Record], builds: list[CharacterBuild]) -> None:
    """Fills in each character's weapon copies (copies, where the record left them out, and the outfit they wear)
    from their builds."""
    by_id = {b.character_id.split("-")[0]: b for b in builds}
    for record in records:
        for team in record.teams:
            for m in team.members:
                build = by_id.get(m.id)
                if build is None:
                    continue
                if m.copies is None:
                    m.copies = build.constellation
                if build.weapon and m.weapon_copies is None:
                    m.weapon_copies = build.weapon.refinement
                if build.weapon and m.weapon_rarity is None and build.weapon.rarity:
                    # ZZZ's game data counts S as 4 and A as 3; the others count stars
                    m.weapon_rarity = build.weapon.rarity + (1 if build.game == "zzz" else 0)
                if build.outfit_icon:  # HoYoLAB's record shows the default look; the build knows the outfit
                    m.icon_url = build.outfit_icon


def _num(value) -> str:
    return f"{int(value):,}"


def _stars(n: int, of: int | None = None) -> str:
    return f"{n} / {of}" if of else str(n)


def _hsr_member(c) -> Member:
    return Member(str(c.id), c.icon, c.level, c.rarity, c.rank)


def _zzz_member(c) -> Member:
    return Member(str(c.id), c.icon, c.level, 5 if c.rarity == "S" else 4, c.mindscape)


def _bangboo(run) -> Member | None:
    b = getattr(run, "bangboo", None)
    return Member(str(b.id), b.icon, b.level, 5 if b.rarity == "S" else 4) if b else None


def _gi_member(c, copies: int | None = None) -> Member:
    return Member(str(c.id), c.icon, getattr(c, "level", 0), c.rarity, copies)


def _node_label(i: int) -> str:
    return "Starward" if i == 3 else f"Node {i}"  # the third node is Starward mode, when it was played


def _nodes(floor, count: int = 3) -> list:
    return [n for n in (getattr(floor, f"node_{i}", None) for i in range(1, count + 1)) if n is not None]


def _top_floor(floors):
    """The deepest floor that was played (HoYoLAB lists the deepest first)."""
    played = [f for f in floors if _nodes(f)]
    return played[0] if played else None


def _floor_no(name: str) -> str:
    """'Memory of Chaos (12)' -> '12'."""
    found = re.findall(r"\d+", name or "")
    return found[-1] if found else name


def _season(seasons, fallback: str = "") -> str:
    for s in seasons or ():
        if getattr(s, "name", ""):
            return s.name
    return fallback


def _day(when) -> dt.date | None:
    """A season's start or end as the date it shows in game. HoYoLAB's calendar-style times (Star Rail, ZZZ) are
    already the server's own clock; Unix times are moved 8 hours on, which lands every server's 4:00 reset on its
    own date."""
    if when is None:
        return None
    if isinstance(when, (int, float, str)):
        when = dt.datetime.fromtimestamp(int(when), tz=dt.timezone.utc)
    if not isinstance(when, dt.datetime):  # Star Rail's PartialTime
        return dt.date(when.year, when.month, when.day)
    if when.utcoffset() == dt.timedelta(0):
        when = when + dt.timedelta(hours=8)
    return when.date()


def _dates(start, end) -> str:
    """'6 Oct – 17 Nov', the season's rotation; empty when HoYoLAB leaves it out."""
    try:
        a, b = _day(start), _day(end)
    except Exception:  # an odd shape; better no dates than no record
        log.exception("couldn't read season dates %r - %r", start, end)
        return ""
    if not (a and b) or a.year < 2000:
        return ""
    return f"{a.day} {a:%b} – {b.day} {b:%b}"


def _with_dates(rec: Record, start, end) -> Record:
    """Puts the rotation's dates in the season line, after its name."""
    if dates := _dates(start, end):
        rec.season = f"{rec.season} · {dates}" if rec.season else dates
    return rec


def _dated(span: Callable[[Any], tuple[Any, Any]]):
    """A reader whose record gets its rotation's dates, from span(data) -> (start, end)."""
    def wrap(read: Callable[[Any], Record]) -> Callable[[Any], Record]:
        def reader(data) -> Record:
            rec = read(data)
            try:
                start, end = span(data)
            except Exception:  # missing in this answer
                return rec
            return _with_dates(rec, start, end)
        reader.__name__ = read.__name__
        return reader
    return wrap


def _first_season(data):
    season = next(iter(data.seasons or ()), None)
    return (season.begin_time, season.end_time) if season else (None, None)


def _starward(rec: Record, data, floor=None) -> None:
    """Starward Mode's stars: the shown floor's own count, else the season's; shown as 0 when Starward was played
    without earning any."""
    floor_stars, total = getattr(floor, "starward_stars", 0) or 0, getattr(data, "starward_stars", 0) or 0
    log.info("%s starward stars: floor %s, season %s", rec.mode, floor_stars, total)
    played = getattr(floor, "has_starward_mode", False) or len(_nodes(floor)) > 2 if floor is not None else False
    if (stars := max(floor_stars, total)) or played:
        rec.headline.insert(1, ("Starward", str(stars)))


# Star Rail -----------------------------------------------------------------------------------------------------


@_dated(_first_season)
def hsr_moc(data) -> Record:
    rec = Record("moc", "Memory of Chaos", _season(data.seasons, data.name))
    if not data.has_data or not (floor := _top_floor(data.floors)):
        rec.empty = "No Memory of Chaos runs this season yet."
        return rec
    rec.headline = [("Stars", _stars(data.total_stars, 36)), ("Cycles", str(floor.round_num))]
    _starward(rec, data, floor)
    for i, node in enumerate(_nodes(floor), 1):
        rec.teams.append(Team(_node_label(i), [], [_hsr_member(c) for c in node.avatars], key=_node_key(floor, node)))
    _boss_lookup(rec, getattr(data, "season", None), floor)
    return rec


@_dated(_first_season)
def hsr_pf(data) -> Record:
    rec = Record("pf", "Pure Fiction", _season(data.seasons))
    if not data.has_data or not (floor := _top_floor(data.floors)):
        rec.empty = "No Pure Fiction runs this season yet."
        return rec
    nodes = _nodes(floor)
    total = sum(n.score for n in nodes)
    rec.headline = [("Stars", _stars(data.total_stars, 12)), ("Score", _num(total))]
    _starward(rec, data, floor)
    for i, node in enumerate(nodes, 1):
        rec.teams.append(Team(_node_label(i), [("score", _num(node.score))], [_hsr_member(c) for c in node.avatars],
                              key=_node_key(floor, node)))
    season = next(iter(data.seasons or ()), None)
    _boss_lookup(rec, getattr(season, "id", None) or getattr(data, "season_id", None), floor)
    return rec


@_dated(_first_season)
def hsr_apoc(data) -> Record:
    rec = Record("apoc", "Apocalyptic Shadow", _season(data.seasons))
    if not data.has_data or not (floor := _top_floor(data.floors)):
        rec.empty = "No Apocalyptic Shadow runs this season yet."
        return rec
    nodes = _nodes(floor)
    total = sum(n.score for n in nodes)
    rec.headline = [("Stars", _stars(data.total_stars, 12)), ("Score", _num(total))]
    _starward(rec, data, floor)
    for i, node in enumerate(nodes, 1):
        chips = [("score", _num(node.score))] + ([] if node.boss_defeated else [("text", "boss not defeated")])
        rec.teams.append(Team(_node_label(i), chips, [_hsr_member(c) for c in node.avatars], key=_node_key(floor, node)))
    season = next(iter(data.seasons or ()), None)  # HoYoLAB sends this season's bosses with it
    bosses = {"1": "upper_boss", "2": "lower_boss", "3": "starward_boss"}
    set_bosses(rec, {k: {"art": getattr(b, "icon", None), "name": getattr(b, "name", "")}
                     for k, attr in bosses.items() if (b := getattr(season, attr, None))})
    return rec


@_dated(lambda d: (lambda r: (r.season.begin_time, r.season.end_time))(next(r for r in d.records if r.has_data)))
def hsr_aa(data) -> Record:
    rec = Record("aa", "Anomaly Arbitration")
    record = next((r for r in data.records if r.has_data), None)
    if record is None:
        rec.empty = "No Anomaly Arbitration runs yet."
        return rec
    rec.season = record.season.name
    mobs = {m.id: m for m in record.mini_bosses}
    knights = [m for m in record.mini_boss_records if m.has_data]  # the header has the knights only; the King's
    rec.headline = [("Stars", str(record.mini_boss_stars)),       # numbers sit beside its own box
                    ("Cycles", str(sum(m.cycles_used for m in knights)))]
    for mob in record.mini_boss_records:
        if mob.has_data:
            info = mobs.get(mob.id)
            rec.teams.append(Team(info.name if info else "Knight", [("stars", f"{mob.stars}/3"), ("cycles", str(mob.cycles_used))],
                                  [_hsr_member(c) for c in mob.characters], art=getattr(info, "icon", None)))
    boss = record.boss_record
    if boss and boss.has_data:
        king = Team(f"{record.boss.name}{' · Plight' if boss.is_hard_mode else ''}", [("stars", f"{boss.stars}/3")],
                    [_hsr_member(c) for c in boss.characters], stage="King", art=getattr(record.boss, "icon", None),
                    left=[("Cycles", str(boss.cycles_used))], plight=bool(boss.is_hard_mode))
        medal_type = getattr(boss, "medal_type", "") or (data.summary.medal_type if data.summary else "")
        if medal_type:
            king.right = [("Rank", medal_type.replace("_", " ").title())]
            rec.medal = getattr(boss, "medal_icon", None) or getattr(data.summary, "medal_icon", None) or None
        rec.teams.append(king)
    return rec


# Zenless Zone Zero ---------------------------------------------------------------------------------------------


def _clock(seconds: int | None) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}" if seconds else ""


@_dated(lambda d: (d.begin_time, d.end_time))
def zzz_sd(data) -> Record:
    rec = Record("sd", "Shiyu Defense")
    brief = getattr(data, "brief_info", None)
    if brief is not None:  # the current Shiyu Defense (v2): a score and a ranking
        fifth = data.fifth_frontier
        if not (fifth and fifth.layers):
            rec.empty = "No Shiyu Defense runs this season yet."
            return rec
        rec.headline = [("Score", _num(brief.score)), ("Rating", brief.rating or "-"), ("Top", brief.rank_percent)]
        if brief.total_clear_time:
            rec.headline.append(("Time", _clock(brief.total_clear_time)))
        for i, layer in enumerate(fifth.layers, 1):
            chips = [("rating", layer.rating), ("score", _num(layer.score))]
            if layer.clear_time:
                chips.append(("time", _clock(layer.clear_time)))
            rec.teams.append(Team(f"Battle {i}", chips, [_zzz_member(c) for c in layer.characters],
                                  art=getattr(layer, "boss_icon", None), bangboo=_bangboo(layer),
                                  key=str(getattr(layer, "id", ""))))
        rec.season_id = str(getattr(data, "schedule_id", "") or "")
        return rec
    # The older Shiyu Defense (v1): floors with a rating each
    if not data.has_data or not data.floors:
        rec.empty = "No Shiyu Defense runs this season yet."
        return rec
    floor = data.floors[0]
    rec.headline = [("Deepest", str(data.max_floor)), ("S ratings", str(data.ratings.get("S", 0)))]
    rec.season = f"{floor.name} · {floor.rating}"
    for i, node in enumerate((floor.node_1, floor.node_2), 1):
        seconds = getattr(node, "battle_time", None) and int(node.battle_time.total_seconds())
        rec.teams.append(Team(_node_label(i), [("time", _clock(seconds))] if seconds else [],
                              [_zzz_member(c) for c in node.characters]))
    return rec


def _node_key(floor, node) -> str:
    """Which of the floor's nodes this is: "1", "2", or "3" for Starward."""
    return next((str(i) for i in (1, 2, 3) if getattr(floor, f"node_{i}", None) is node), "")


def _boss_lookup(rec: Record, season, floor) -> None:
    """Notes the season and floor, so the bosses can be looked up (see hsr_bosses)."""
    rec.season_id = str(season or "")
    rec.floor_id = str(getattr(floor, "id", "") or "")


def set_bosses(record: Record, bosses: dict[str, dict[str, str]]) -> None:
    """Gives each Star Rail node its boss: the picture faded into its box, the name in its label ("Node 1 · Name")."""
    for team in record.teams:
        boss = bosses.get(team.key) or {}
        if boss.get("art") and not team.art:
            team.art = boss["art"]
        if boss.get("name") and " · " not in team.label:
            team.label = f"{team.label} · {boss['name']}"


def name_bosses(record: Record, names: dict[str, str]) -> None:
    """Puts each Shiyu Defense battle's boss in its label: "Battle 1 · Miasmic - Thracian"."""
    for team in record.teams:
        if team.key in names:
            team.label = f"{team.label} · {names[team.key]}"


def _da_team(c, stage: str = "") -> Team:
    return Team(c.boss.name, [("stars", f"{c.star}/3"), ("score", _num(c.score))], [_zzz_member(a) for a in c.agents],
                stage=stage, art=getattr(c.boss, "icon", None), bangboo=_bangboo(c))


@_dated(lambda d: (d.start_time, d.end_time))
def zzz_da(data) -> Record:
    rec = Record("da", "Deadly Assault")
    if not data.has_data or not data.challenges:
        rec.empty = "No Deadly Assault runs this season yet."
        return rec
    # The header has the three regular bosses only; Adversity Mode's numbers sit beside its own box
    rec.headline = [("Score", _num(sum(c.score for c in data.challenges))), ("Stars", str(sum(c.star for c in data.challenges))),
                    ("Top", data.rank_percent)]
    for c in data.challenges:
        rec.teams.append(_da_team(c))
    for c in getattr(data, "hard_challenges", None) or ():  # Adversity Mode, the extra boss
        team = _da_team(c, "Adversity Mode")
        team.chips = [("score", _num(c.score))]
        team.left = [("Stars", f"{c.star}/3")]
        if getattr(data, "hard_rank_percent", None):
            team.right = [("Top", data.hard_rank_percent)]
        rec.teams.append(team)
    return rec


# Genshin Impact ------------------------------------------------------------------------------------------------


@_dated(lambda d: (d.start_time, d.end_time))
def gi_abyss(data) -> Record:
    rec = Record("abyss", "Spiral Abyss")
    floors = [f for f in data.floors if f.chambers]
    if not data.unlocked or not floors:
        rec.empty = "No Spiral Abyss runs this season yet."
        return rec
    floor = floors[-1]  # the deepest
    rec.headline = [("Stars", _stars(data.total_stars, 36)), ("Deepest", data.max_floor), ("Battles", str(data.total_battles))]
    rec.season = f"Floor {floor.floor} · {floor.stars} / {floor.max_stars}★"
    for chamber in floor.chambers:
        for battle in chamber.battles:
            half = "First half" if battle.half == 1 else "Second half"
            rec.teams.append(Team(f"{floor.floor}-{chamber.chamber} · {half}", [("stars", f"{chamber.stars}/3")],
                                  [_gi_member(c) for c in battle.characters]))
    return rec


THEATER_MODES = {1: "Easy", 2: "Normal", 3: "Hard", 4: "Visionary", 5: "Lunar"}


@_dated(lambda d: (lambda r: (r.schedule.start_time, r.schedule.end_time))(next(x for x in d.datas if x.has_data)))
def gi_theater(data) -> Record:
    rec = Record("theater", "Imaginarium Theater")
    run = next((d for d in data.datas if d.has_data), None)
    if not data.unlocked or run is None:
        rec.empty = "No Imaginarium Theater runs this season yet."
        return rec
    stats = run.stats
    rec.headline = [("Act", str(stats.best_record)), ("Medals", str(stats.medal_num)),
                    ("Mode", THEATER_MODES.get(int(stats.difficulty), str(stats.difficulty)))]
    for act in list(run.acts)[-2:]:  # the last two acts reached
        rec.teams.append(Team(f"Act {act.round_id}", [("stars", "1/1" if act.medal_obtained else "0/1")],
                              [_gi_member(c) for c in act.characters]))
    return rec


@_dated(lambda d: (lambda s: (s.season.start_at, s.season.end_at))(next(x for x in d if x.single_player.has_data)))
def gi_stygian(data) -> Record:
    rec = Record("stygian", "Stygian Onslaught")
    season = next((s for s in data if s.single_player.has_data), None)
    if season is None:
        rec.empty = "No Stygian Onslaught runs this season yet."
        return rec
    run = season.single_player
    rec.season = season.season.name
    if run.best_record:
        rec.headline = [("Difficulty", str(run.best_record.difficulty)), ("Time", f"{run.best_record.time_used}s")]
    for c in run.challenges:
        rec.teams.append(Team(c.name or c.enemy.name, [("time", f"{c.time_used}s")],
                              [_gi_member(m, m.constellation) for m in c.team]))
    return rec


# Reading them --------------------------------------------------------------------------------------------------

READERS: dict[str, tuple[Callable[[genshin.Client, int], Awaitable[Any]], Callable[[Any], Record]]] = {
    "moc": (lambda c, uid: c.get_starrail_challenge(uid), hsr_moc),
    "pf": (lambda c, uid: c.get_starrail_pure_fiction(uid), hsr_pf),
    "apoc": (lambda c, uid: c.get_starrail_apc_shadow(uid), hsr_apoc),
    "aa": (lambda c, uid: c.get_anomaly_arbitration(uid, schedule_type=1), hsr_aa),
    "sd": (lambda c, uid: c.get_shiyu_defense(uid), zzz_sd),
    "da": (lambda c, uid: c.get_deadly_assault(uid), zzz_da),
    "abyss": (lambda c, uid: c.get_spiral_abyss(uid), gi_abyss),
    "theater": (lambda c, uid: c.get_imaginarium_theater(uid), gi_theater),
    "stygian": (lambda c, uid: c.get_stygian_onslaught(uid), gi_stygian),
}


def mode_title(game: str, key: str) -> str:
    return next(m.title for m in MODES[game] if m.key == key)


async def read_records(client: genshin.Client, game: str, uid: int, modes: list[str]) -> list[Record]:
    """Each mode asked for, read at the same time. A mode HoYoLAB won't give stays in the list with the reason as
    `empty`; errors that stop every mode (a private Battle Chronicle, an expired login) are raised."""
    async def one(key: str) -> Record:
        fetch, convert = READERS[key]
        try:
            return convert(await fetch(client, uid))
        except (genshin.DataNotPublic, genshin.InvalidCookies, genshin.AccountNotFound, genshin.TooManyRequests):
            raise
        except genshin.GenshinException as exc:
            log.warning("HoYoLAB %s %s for %s: %s", game, key, uid, exc)
            return Record(key, mode_title(game, key), empty="HoYoLAB didn't return this mode.")
        except Exception:
            log.exception("Could not read %s %s for %s", game, key, uid)
            return Record(key, mode_title(game, key), empty="Couldn't read this mode right now.")

    return list(await asyncio.gather(*(one(k) for k in modes)))
