"""Made-up HoYoLAB profile pages, shaped like genshin.py's, for the /<game>-stats tests and previews."""
from types import SimpleNamespace as NS

ENKA = "https://enka.network/ui/"
SRR = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/avatar/"

GI_CHARS = [("Furina", 5, 90, 2), ("Neuvillette", 5, 90, 1), ("Nahida", 5, 90, 0), ("Raiden Shogun", 5, 90, 0), ("Kazuha", 5, 90, 0),
            ("Zhongli", 5, 80, 0), ("Ayaka", 5, 80, 0), ("Xingqiu", 4, 90, 6), ("Bennett", 4, 90, 6), ("Xiangling", 4, 80, 6),
            ("Fischl", 4, 80, 6), ("Sucrose", 4, 70, 6), ("Yelan", 5, 90, 1), ("Kokomi", 5, 80, 0), ("Layla", 4, 70, 3),
            ("Faruzan", 4, 80, 6), ("Chevreuse", 4, 70, 4), ("Kaveh", 4, 60, 1)]
GI_ICONS = {"Raiden Shogun": "Shougun", "Kazuha": "Kazuha", "Ayaka": "Ayaka", "Kokomi": "Kokomi", "Neuvillette": "Neuvillette"}

HSR_CHARS = [("Acheron", 1308, 5, 80, 2), ("Firefly", 1310, 5, 80, 0), ("Castorice", 1407, 5, 80, 1), ("Jingliu", 1212, 5, 80, 0),
             ("Kafka", 1005, 5, 80, 0), ("Silver Wolf", 1006, 5, 80, 0), ("Ruan Mei", 1303, 5, 80, 0), ("Robin", 1309, 5, 80, 1),
             ("Pela", 1106, 4, 80, 6), ("Hook", 1109, 4, 70, 3), ("Moze", 1223, 4, 70, 2), ("Gallagher", 1301, 4, 80, 6),
             ("Tingyun", 1202, 4, 80, 6), ("Asta", 1009, 4, 60, 4), ("Sushang", 1206, 4, 50, 1)]

ZZZ_CHARS = [("Ellen", 21, 5, 60, 1), ("Caesar", 25, 5, 60, 0), ("Soldier 11", 5, 4, 60, 6), ("Soukaku", 17, 4, 60, 6),
             ("Lucy", 27, 4, 50, 4), ("Koleda", 14, 5, 60, 0), ("Nicole", 1, 4, 60, 6), ("Anby", 2, 4, 60, 6), ("Billy", 3, 4, 50, 3)]


def genshin():
    stats = NS(days_active=812, characters=len(GI_CHARS), achievements=1043, spiral_abyss="12-3", max_friendship_characters=34,
               anemoculi=66, geoculi=131, electroculi=181, dendroculi=271, hydroculi=271, pyroculi=337, lunoculi=0,
               common_chests=2310, exquisite_chests=1610, precious_chests=502, luxurious_chests=190, remarkable_chests=80,
               unlocked_waypoints=402, unlocked_domains=58, theater=NS(unlocked=True, has_data=True, max_act=10),
               stygian=NS(unlocked=True, name="Fearless"))
    regions = [("Mondstadt", 1000), ("Liyue", 1000), ("Dragonspine", 1000), ("Inazuma", 1000), ("Enkanomiya", 1000),
               ("Chasm", 987), ("Sumeru", 1000), ("Fontaine", 982), ("Natlan", 931), ("Nod-Krai", 412)]
    chars = [NS(name=n, icon=f"{ENKA}UI_AvatarIcon_{GI_ICONS.get(n, n.replace(' ', ''))}.png", rarity=r, level=l, constellation=c)
             for n, r, l, c in GI_CHARS]
    return NS(info=NS(nickname="Traveler", level=60), stats=stats, characters=chars,
              explorations=[NS(id=i, parent_id=0, name=n, explored=p / 10, icon=None) for i, (n, p) in enumerate(regions)],
              teapot=NS(level=10, comfort=48000, items=3402, visitors=211))


def hsr():
    stats = NS(active_days=640, avatar_num=len(HSR_CHARS), achievement_num=702, chest_num=3021, abyss_process="Eternal Stage 12",
               dreamscape_pass_sticker=48)
    chars = [NS(name=n, icon=f"{SRR}{i}.png", rarity=r, level=l, rank=e) for n, i, r, l, e in HSR_CHARS]
    return NS(stats=stats, characters=chars), NS(nickname="Trailblazer", level=70)


def zzz():
    stats = NS(active_days=420, character_num=len(ZZZ_CHARS), inter_knot_reputation="Virtuoso", shiyu_defense_frontiers=7,
               bangboo_obtained=24, achievement_count=388, hia_coin=NS(name="HIA Commemorative Coins", num=12))
    agents = [NS(name=n, square_icon=f"{ENKA}zzz/IconRole{i:02d}.png", rarity="S" if r == 5 else "A", level=l, rank=m)
              for n, i, r, l, m in ZZZ_CHARS]
    notes = [NS(name="Bangboo Notes", num=24, total=30, is_lock=False), NS(name="Agent Notes", num=33, total=40, is_lock=False)]
    return NS(stats=stats, agents=agents, cat_notes=notes)
