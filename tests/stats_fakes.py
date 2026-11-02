"""Made-up HoYoLAB profile pages, shaped like genshin.py's, for the /<game>-stats tests and previews."""
from types import SimpleNamespace as NS

ENKA = "https://enka.network/ui/"
SRR_WALL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/image/character_preview/1308.png"  # a stand-in phone wallpaper

# Enka's raw player blocks, shaped like tests/fixtures/*_live.json
GI_PLAYER = {"nickname": "Traveler", "level": 60, "signature": "Exploring Teyvat one waypoint at a time.", "worldLevel": 9,
             "nameCardId": 210189, "showNameCardIdList": [210189, 210178, 210150, 210133, 210104, 210092, 210061, 210001],
             "profilePicture": {"id": 4600}}
HSR_PLAYER = {"nickname": "Trailblazer", "level": 70, "signature": "Next stop: wherever the Express takes us.", "worldLevel": 6,
              "headIcon": 201308, "friendCount": 52,
              "recordInfo": {"achievementCount": 702, "bookCount": 217, "avatarCount": 51, "equipmentCount": 93, "musicCount": 14,
                             "relicCount": 2878, "maxRogueChallengeScore": 9}}
ZZZ_PLAYER = {"SocialDetail": {"Desc": "Video store open late. Ask about the Hollows.", "MedalList": [
    {"MedalIcon": 1002, "Value": 30, "MedalType": 1}, {"MedalIcon": 2004, "Value": 6, "MedalType": 2},
    {"MedalIcon": 3001, "Value": 12, "MedalType": 3}],
    "ProfileDetail": {"Nickname": "Proxy", "Level": 60, "ProfileId": 3201004, "CallingCardId": 3300012,
                      "TitleInfo": {"Title": 3800101}}}}


def genshin():
    stats = NS(days_active=812, characters=94, achievements=1043, spiral_abyss="12-3", max_friendship_characters=34,
               anemoculi=66, geoculi=131, electroculi=181, dendroculi=271, hydroculi=271, pyroculi=337, lunoculi=0,
               common_chests=2310, exquisite_chests=1610, precious_chests=502, luxurious_chests=190, remarkable_chests=80,
               unlocked_waypoints=402, unlocked_domains=58, theater=NS(unlocked=True, has_data=True, max_act=10),
               stygian=NS(unlocked=True, name="Fearless"))
    regions = [("Mondstadt", 1000), ("Liyue", 1000), ("Dragonspine", 1000), ("Inazuma", 1000), ("Enkanomiya", 1000),
               ("Chasm", 987), ("Sumeru", 1000), ("Fontaine", 982), ("Natlan", 931), ("Nod-Krai", 412)]
    return NS(info=NS(nickname="Traveler", level=60), stats=stats, characters=[],
              explorations=[NS(id=i, parent_id=0, name=n, explored=p / 10, icon=None) for i, (n, p) in enumerate(regions)],
              teapot=NS(level=10, comfort=48000, items=3402, visitors=211))


def hsr():
    stats = NS(active_days=640, avatar_num=51, achievement_num=702, chest_num=3021, abyss_process="Eternal Stage 12",
               dreamscape_pass_sticker=48)
    return NS(stats=stats, characters=[], in_game_avatar="", phone_background=SRR_WALL), NS(nickname="Trailblazer", level=70)


def zzz():
    stats = NS(active_days=420, character_num=38, inter_knot_reputation="Virtuoso", shiyu_defense_frontiers=7,
               bangboo_obtained=24, achievement_count=388, hia_coin=NS(name="HIA Commemorative Coins", num=12))
    notes = [NS(name="Bangboo Notes", num=24, total=30, is_lock=False), NS(name="Agent Notes", num=33, total=40, is_lock=False)]
    return NS(stats=stats, agents=[], cat_notes=notes, in_game_avatar="", in_game_data=None)
