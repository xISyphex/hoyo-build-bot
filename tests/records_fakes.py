"""Stand-ins for genshin.py's battle record models (only the fields bot.records reads), for tests and previews."""

from __future__ import annotations

from types import SimpleNamespace as NS

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


def moc() -> NS:
    floor = NS(name="Memory of Chaos (12)", star_num=3, round_num=7, node_1=NS(avatars=TEAM_A), node_2=NS(avatars=TEAM_B))
    return NS(name="", has_data=True, floors=[floor], seasons=[NS(name="Lupine Moon")], total_stars=36,
              max_floor="Memory of Chaos (12)", total_battles=14)


def pf() -> NS:
    floor = NS(name="Pure Fiction (4)", star_num=3, node_1=NS(avatars=TEAM_A, score=40000), node_2=NS(avatars=TEAM_B, score=38512))
    return NS(has_data=True, floors=[floor], seasons=[NS(name="Lone Wanderer")], total_stars=12, total_battles=5)


def apoc() -> NS:
    floor = NS(name="Apocalyptic Shadow (4)", star_num=3,
               node_1=NS(avatars=TEAM_A, score=4000, boss_defeated=True), node_2=NS(avatars=TEAM_B, score=3720, boss_defeated=True))
    return NS(has_data=True, floors=[floor], seasons=[NS(name="Dawn's Tremor")], total_stars=12, total_battles=4)


def aa() -> NS:
    record = NS(
        has_data=True, season=NS(name="Knights of the Scale"), boss_stars=3, mini_boss_stars=6, cycles_used=9,
        mini_bosses=[NS(id=1, name="Wolf Knight"), NS(id=2, name="Lion Knight")],
        mini_boss_records=[NS(id=1, has_data=True, stars=3, cycles_used=2, characters=TEAM_B),
                           NS(id=2, has_data=True, stars=3, cycles_used=3, characters=TEAM_A[::-1])],
        boss=NS(name="Sovereign of Thrones", game_mode_name="Hard Mode"),
        boss_record=NS(has_data=True, is_hard_mode=True, stars=3, cycles_used=4, characters=TEAM_A),
    )
    return NS(records=[record], summary=NS(medal_type="gold"))


ZZZ_A = [zzz_char(1191, "/ui/zzz/IconRoleCircle21.png", 2), zzz_char(1211, "/ui/zzz/IconRoleCircle22.png", 0),
         zzz_char(1151, "/ui/zzz/IconRoleCircle27.png", 0, 60, "A")]
ZZZ_B = [zzz_char(1041, "/ui/zzz/IconRoleCircle05.png", 1), zzz_char(1131, "/ui/zzz/IconRoleCircle17.png", 0, 60, "A"),
         zzz_char(1101, "/ui/zzz/IconRoleCircle14.png", 6)]


def sd() -> NS:
    layers = [NS(score=31890, rating="S", clear_time=104, characters=ZZZ_A),
              NS(score=29760, rating="S", clear_time=132, characters=ZZZ_B),
              NS(score=27105, rating="A", clear_time=171, characters=ZZZ_A[::-1])]
    brief = NS(score=88755, rating="S", rank_percent="4.21%", total_clear_time=407)
    return NS(brief_info=brief, fifth_frontier=NS(layers=layers))


def da() -> NS:
    boss = lambda name: NS(name=name)  # noqa: E731
    return NS(has_data=True, total_score=60120, total_star=9, rank_percent="2.8%", challenges=[
        NS(boss=boss("Notorious - Dead End Butcher"), score=20480, star=3, agents=ZZZ_A),
        NS(boss=boss("Notorious - Marionette"), score=20110, star=3, agents=ZZZ_B),
        NS(boss=boss("Notorious - Pompey"), score=19530, star=3, agents=ZZZ_A[::-1]),
    ])


GI_A = [gi_char(10000089, "Furina", constellation=2), gi_char(10000073, "Nahida"), gi_char(10000052, "Shougun"),
        gi_char(10000054, "Kokomi")]
GI_B = [gi_char(10000002, "Ayaka"), gi_char(10000032, "Bennett", rarity=4), gi_char(10000063, "Shenhe"),
        gi_char(10000025, "Xingqiu", rarity=4)]


def abyss() -> NS:
    battle = lambda half, team: NS(half=half, characters=team)  # noqa: E731
    chambers = [NS(chamber=i, stars=3, battles=[battle(1, GI_A), battle(2, GI_B)]) for i in (1, 2, 3)]
    floor = NS(floor=12, stars=9, max_stars=9, chambers=chambers)
    return NS(unlocked=True, floors=[NS(floor=11, chambers=[]), floor], total_stars=36, max_floor="12-3", total_battles=12)


def theater() -> NS:
    acts = [NS(round_id=i, medal_obtained=True, characters=GI_A if i % 2 else GI_B) for i in range(1, 11)]
    stats = NS(best_record=10, medal_num=10, difficulty=4)
    return NS(unlocked=True, datas=[NS(has_data=True, stats=stats, acts=acts)])


def stygian() -> NS:
    team = [gi_char(10000089, "Furina", constellation=2), gi_char(10000073, "Nahida", constellation=0),
            gi_char(10000052, "Shougun", constellation=0), gi_char(10000054, "Kokomi", constellation=1)]
    run = NS(has_data=True, best_record=NS(difficulty=6, time_used=212),
             challenges=[NS(name="Lord of the Hidden Depths", time_used=68, team=team, enemy=NS(name="")),
                         NS(name="Radiant Moonfly", time_used=74, team=team[::-1], enemy=NS(name="")),
                         NS(name="Knuckle Duckle", time_used=70, team=team, enemy=NS(name=""))])
    return [NS(single_player=run, season=NS(name="Season 3"))]

