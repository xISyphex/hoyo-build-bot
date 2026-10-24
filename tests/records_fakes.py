"""Stand-ins for genshin.py's battle record models (only the fields bot.records reads), for tests and previews."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace as NS

def when(month: int, day: int, hour: int = 4) -> NS:
    """Star Rail's PartialTime: the server's own clock."""
    return NS(year=2026, month=month, day=day, hour=hour, minute=0)


def local(month: int, day: int, hour: int = 4) -> dt.datetime:
    """ZZZ's DateTime: the server's own clock, with its UTC offset."""
    return dt.datetime(2026, month, day, hour, tzinfo=dt.timezone(dt.timedelta(hours=1)))


def unix(month: int, day: int, hour: int = 3) -> dt.datetime:
    """Genshin's Unix times: UTC (a Europe 4:00 reset is 3:00 UTC)."""
    return dt.datetime(2026, month, day, hour, tzinfo=dt.timezone.utc)


SRR = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/avatar/"


def hsr_char(cid: int, rank: int = 0, level: int = 80, rarity: int = 5) -> NS:
    return NS(id=cid, icon=f"{SRR}{cid}.png", level=level, rarity=rarity, rank=rank)


def zzz_char(cid: int, icon: str, mindscape: int = 0, level: int = 60, rarity: str = "S") -> NS:
    return NS(id=cid, icon=f"https://enka.network{icon}", level=level, rarity=rarity, mindscape=mindscape)


def gi_char(cid: int, name: str, level: int = 90, rarity: int = 5, constellation: int | None = None) -> NS:
    char = NS(id=cid, icon=f"https://enka.network/ui/UI_AvatarIcon_{name}.png", level=level, rarity=rarity)
    if constellation is not None:
        char.constellation = constellation
    return char


TEAM_A = [hsr_char(1407, 2), hsr_char(1313, 0), hsr_char(1403, 1), hsr_char(1217, 0)]
TEAM_B = [hsr_char(1310, 1), hsr_char(1303, 0), hsr_char(1306, 0), hsr_char(1304, 0, 80, 5)]
TEAM_C = [hsr_char(1212, 0), hsr_char(1308, 1), hsr_char(1301, 0), hsr_char(1309, 0)]


def moc() -> NS:
    floor = NS(name="Crossing the Afterlife (XII)Starward Mode", star_num=3, starward_stars=3, round_num=7, node_1=NS(avatars=TEAM_A), node_2=NS(avatars=TEAM_B),
               node_3=NS(avatars=TEAM_C))
    return NS(name="", has_data=True, floors=[floor], seasons=[NS(name="Lupine Moon", begin_time=when(10, 6), end_time=when(11, 17, 3))], total_stars=36,
              max_floor="Memory of Chaos (12)", total_battles=14, starward_stars=1)


def pf() -> NS:
    floor = NS(name="Pure Fiction (4)", star_num=3, node_1=NS(avatars=TEAM_A, score=40000), node_2=NS(avatars=TEAM_B, score=38512),
               node_3=NS(avatars=TEAM_C, score=36120))
    return NS(has_data=True, floors=[floor], seasons=[NS(name="Lone Wanderer", begin_time=when(9, 22), end_time=when(11, 3, 3))], total_stars=12, total_battles=5)


def apoc() -> NS:
    floor = NS(name="04", star_num=3,
               node_1=NS(avatars=TEAM_A, score=4000, boss_defeated=True), node_2=NS(avatars=TEAM_B, score=3720, boss_defeated=True),
               node_3=NS(avatars=TEAM_C, score=3405, boss_defeated=True))
    return NS(has_data=True, floors=[floor], seasons=[NS(name="Dawn's Tremor", begin_time=when(10, 20), end_time=when(12, 1, 3))], total_stars=12, total_battles=4)


def aa() -> NS:
    record = NS(
        has_data=True, season=NS(name="Knights of the Scale", begin_time=when(10, 13), end_time=when(11, 24, 3)), boss_stars=3, mini_boss_stars=9, cycles_used=11,
        mini_bosses=[NS(id=1, name="Wolf Knight"), NS(id=2, name="Lion Knight"), NS(id=3, name="Stag Knight")],
        mini_boss_records=[NS(id=1, has_data=True, stars=3, cycles_used=2, characters=TEAM_B),
                           NS(id=2, has_data=True, stars=3, cycles_used=3, characters=TEAM_A[::-1]),
                           NS(id=3, has_data=True, stars=3, cycles_used=2, characters=TEAM_C)],
        boss=NS(name="Sovereign of Thrones", game_mode_name="Hard Mode"),
        boss_record=NS(has_data=True, is_hard_mode=True, stars=3, cycles_used=4, characters=TEAM_A),
    )
    return NS(records=[record], summary=NS(medal_type="gold"))


ZZZ_A = [zzz_char(1191, "/ui/zzz/IconRoleCircle21.png", 2), zzz_char(1211, "/ui/zzz/IconRoleCircle22.png", 0),
         zzz_char(1151, "/ui/zzz/IconRoleCircle27.png", 0, 60, "A")]
ZZZ_B = [zzz_char(1041, "/ui/zzz/IconRoleCircle05.png", 1), zzz_char(1131, "/ui/zzz/IconRoleCircle17.png", 0, 60, "A"),
         zzz_char(1101, "/ui/zzz/IconRoleCircle14.png", 6)]


BANGBOO = NS(id=54001, rarity="S", level=60, icon="")


def sd() -> NS:
    layers = [NS(id=62059051, score=31890, rating="S", clear_time=104, characters=ZZZ_A, bangboo=BANGBOO),
              NS(id=62059052, score=29760, rating="S", clear_time=132, characters=ZZZ_B, bangboo=None),
              NS(id=62059053, score=27105, rating="A", clear_time=171, characters=ZZZ_A[::-1], bangboo=BANGBOO)]
    brief = NS(score=88755, rating="S", rank_percent="4.21%", total_clear_time=407)
    return NS(schedule_id=62059, brief_info=brief, fifth_frontier=NS(layers=layers), begin_time=local(10, 10), end_time=local(10, 24, 3))


def da() -> NS:
    boss = lambda name: NS(name=name)  # noqa: E731
    return NS(has_data=True, total_score=60120, total_star=9, rank_percent="2.8%", challenges=[
        NS(boss=boss("Notorious - Dead End Butcher"), score=20480, star=3, agents=ZZZ_A, bangboo=BANGBOO),
        NS(boss=boss("Notorious - Marionette"), score=20110, star=3, agents=ZZZ_B),
        NS(boss=boss("Notorious - Pompey"), score=19530, star=3, agents=ZZZ_A[::-1]),
    ], hard_challenges=[NS(boss=boss("Notorious - Miasma Priest"), score=24860, star=2, agents=ZZZ_B[::-1])],
        hard_rank_percent="0.16%", start_time=local(10, 13), end_time=local(10, 27, 3))


GI_A = [gi_char(10000089, "Furina", constellation=2), gi_char(10000073, "Nahida"), gi_char(10000052, "Shougun"),
        gi_char(10000054, "Kokomi")]
GI_B = [gi_char(10000002, "Ayaka"), gi_char(10000032, "Bennett", rarity=4), gi_char(10000063, "Shenhe"),
        gi_char(10000025, "Xingqiu", rarity=4)]


def abyss() -> NS:
    battle = lambda half, team: NS(half=half, characters=team)  # noqa: E731
    chambers = [NS(chamber=i, stars=3, battles=[battle(1, GI_A), battle(2, GI_B)]) for i in (1, 2, 3)]
    floor = NS(floor=12, stars=9, max_stars=9, chambers=chambers)
    return NS(unlocked=True, floors=[NS(floor=11, chambers=[]), floor], total_stars=36, max_floor="12-3", total_battles=12,
              start_time=unix(9, 16), end_time=unix(10, 16, 2))


def theater() -> NS:
    acts = [NS(round_id=i, medal_obtained=True, characters=GI_A if i % 2 else GI_B) for i in range(1, 11)]
    stats = NS(best_record=10, medal_num=10, difficulty=4)
    return NS(unlocked=True, datas=[NS(has_data=True, stats=stats, acts=acts, schedule=NS(start_time=int(unix(10, 1).timestamp()), end_time=int(unix(11, 1, 2).timestamp())))])


def stygian() -> NS:
    team = [gi_char(10000089, "Furina", constellation=2), gi_char(10000073, "Nahida", constellation=0),
            gi_char(10000052, "Shougun", constellation=0), gi_char(10000054, "Kokomi", constellation=1)]
    run = NS(has_data=True, best_record=NS(difficulty=6, time_used=212),
             challenges=[NS(name="Lord of the Hidden Depths", time_used=68, team=team, enemy=NS(name="")),
                         NS(name="Radiant Moonfly", time_used=74, team=team[::-1], enemy=NS(name="")),
                         NS(name="Knuckle Duckle", time_used=70, team=team, enemy=NS(name=""))])
    return [NS(single_player=run, season=NS(name="Season 3", start_at=unix(10, 8), end_at=unix(11, 5, 2)))]

