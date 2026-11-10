"""Characters from the next version's beta, so /hsr Aha gear_from:Sparkle can show what they'd have with someone's
gear before they are out.

Hakushin's beta data (static.nanoka.cc, the "latest" version in its manifest) lists the new characters. Each one that
Enka's store doesn't know yet is written into the game data in the store's own shapes, and gets a made-up showcase
entry at max level with every trace and no eidolons, which the parsers and bot/borrow.py read like a real one.
Once Enka's store has the character, the store's entry wins and the beta one is dropped.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from .assets import Assets
from .games import genshin, starrail, zenless
from .models import CharacterBuild

log = logging.getLogger(__name__)

HAKUSHIN = "https://static.nanoka.cc"
PICTURES = HAKUSHIN + "/assets/hsr/"
GAMES = {"genshin": "gi", "hsr": "hsr", "zzz": "zzz"}
STORE_KEY = {"genshin": "gi_avatars", "hsr": "hsr_characters", "zzz": "zzz_avatars"}
PARSERS = {"genshin": genshin, "hsr": starrail, "zzz": zenless}
MAX_PER_GAME = 12

GI_ELEMENTS = {v: k for k, v in genshin.ELEMENT_NAMES.items()}  # Electro -> Electric
GI_PROPS = {"fight_prop_base_hp": "1", "fight_prop_base_attack": "4", "fight_prop_base_defense": "7",
            "fight_prop_hp_percent": "3", "fight_prop_attack_percent": "6", "fight_prop_defense_percent": "9",
            "fight_prop_critical": "20", "fight_prop_critical_hurt": "22", "fight_prop_charge_efficiency": "23",
            "fight_prop_heal_add": "26", "fight_prop_element_mastery": "28", "fight_prop_physical_add_hurt": "30",
            "fight_prop_fire_add_hurt": "40", "fight_prop_elec_add_hurt": "41", "fight_prop_water_add_hurt": "42",
            "fight_prop_grass_add_hurt": "43", "fight_prop_wind_add_hurt": "44", "fight_prop_rock_add_hurt": "45",
            "fight_prop_ice_add_hurt": "46"}
# Hakushin's ZZZ stat names -> the game's property ids
ZZZ_BASE = {"hp_max": "11101", "attack": "12101", "defence": "13101", "break_stun": "12201", "crit": "20101",
            "crit_damage": "21101", "element_abnormal_power": "31401", "element_mystery": "31201", "sp_recover": "30501"}
ZZZ_GROWTH = {"hp_growth": "11101", "attack_growth": "12101", "defence_growth": "13101"}
ZZZ_ELEMENTS = {"Electric": "Elec", "Physical": "Physics", "Fire": "Fire", "Ice": "Ice", "Ether": "Ether", "Wind": "Wind"}


def _hsr(cid: str, d: dict) -> dict:
    stats = d.get("stats") or {}
    top = str(max((int(k) for k in stats), default=0))
    avatar = {k: {"HPBase": s.get("hp_base", 0), "HPAdd": s.get("hp_add", 0), "AttackBase": s.get("attack_base", 0),
                  "AttackAdd": s.get("attack_add", 0), "DefenceBase": s.get("defence_base", 0),
                  "DefenceAdd": s.get("defence_add", 0), "SpeedBase": s.get("speed_base", 0),
                  "CriticalChance": s.get("critical_chance", 0), "CriticalDamage": s.get("critical_damage", 0)}
              for k, s in stats.items()}
    tree, points, anchors = {}, [], {}
    for levels in (d.get("skill_trees") or {}).values():
        last = levels[max(levels, key=int)]
        pid = str(last.get("point_id"))
        points.append({"pointId": int(pid), "level": int(last.get("max_level") or 1)})
        anchors[last.get("anchor")] = pid
        props = {a["property_type"]: a.get("value", 0) for a in last.get("status_add_list") or [] if a.get("property_type")}
        if props:
            tree[pid] = {str(points[-1]["level"]): {"props": props}}
    rarity = 5 if str(d.get("rarity", "")).endswith("5") else 4
    name = " ".join((d.get("name") or "").replace("\u2605", "\u00b7").split())  # the card fonts have no star: "Aeon · Aha"
    return {
        "name": name,
        "data": {
            "hsr_characters": {cid: {
                "Unreleased": True, "Name": name, "Rarity": rarity, "Element": d.get("damage_type", ""),
                "AvatarBaseType": d.get("base_type", ""), "RankIDList": [r.get("id") for r in (d.get("ranks") or {}).values()],
                "Art": f"{PICTURES}avatardrawcard/{cid}.webp", "Icon": f"{PICTURES}avatarroundicon/{cid}.webp",
                "RankIcons": [f"{PICTURES}skillicons/{r['icon'].rsplit('.', 1)[0]}.webp" for r in (d.get("ranks") or {}).values() if r.get("icon")],
            }},
            "hsr_skilltree": {cid: {"0": [anchors[a] for a in ("Point01", "Point02", "Point03", "Point04") if a in anchors]}},
        },
        "meta": {"avatar": {cid: avatar}, "tree": tree},
        "raw": {"avatarId": int(cid), "level": 80, "promotion": int(top), "rank": 0, "skillTreeList": points},
    }


def _zzz(cid: str, d: dict) -> dict:
    stats = d.get("stats") or {}
    base = {prop: stats.get(key, 0) for key, prop in ZZZ_BASE.items()}
    if not base["30501"]:  # agents with another kind of energy
        base["30501"] = stats.get("ep_recover", 0) or stats.get("rp_recover", 0)
    levels = [d["level"][k] for k in sorted(d.get("level") or {}, key=int)]
    cores = [d["extra_level"][k] for k in sorted(d.get("extra_level") or {}, key=int)]
    core_props = [{str(p): e.get("value", 0) for p, e in (c.get("extra") or {}).items()} for c in cores]
    name_key = f"Unreleased_{cid}"
    elements = [ZZZ_ELEMENTS.get(e, e) for e in (d.get("element_type") or {}).values()]
    return {
        "name": d.get("name"),
        "data": {
            "zzz_avatars": {cid: {
                "Unreleased": True, "Name": name_key, "Rarity": int(d.get("rarity") or 0),
                "ProfessionType": next(iter((d.get("weapon_type") or {}).values()), ""), "ElementTypes": elements,
                "Image": f"/ui/zzz/{d['icon']}.png" if d.get("icon") else None,
                "CircleIcon": f"/ui/zzz/{d['icon'].replace('IconRole', 'IconRoleCircle')}.png" if d.get("icon") else None,
                "BaseProps": base, "GrowthProps": {prop: stats.get(key, 0) for key, prop in ZZZ_GROWTH.items()},
                "PromotionProps": [{"11101": lv.get("hp_max", 0), "12101": lv.get("attack", 0), "13101": lv.get("defence", 0)}
                                   for lv in levels],
                "CoreEnhancementProps": [{p: 0 for p in (core_props[0] if core_props else {})}, *core_props],
            }},
        },
        "text": {name_key: d.get("name")},
        "raw": {"Id": int(cid), "Level": 60, "PromotionLevel": len(levels), "CoreSkillEnhancement": len(core_props),
                "TalentLevel": 0, "SkillLevelList": [{"Index": i, "Level": 12} for i in (0, 1, 2, 3, 6)]},
    }


def _genshin(cid: str, d: dict) -> dict:
    mod = d.get("stats_modifier") or {}
    asc = (mod.get("ascension") or [{}])[-1]
    at90 = lambda key: float((mod.get(key) or {}).get("90", 1))
    props = {"1": d.get("base_hp", 0) * at90("hp"), "4": d.get("base_atk", 0) * at90("atk"), "7": d.get("base_def", 0) * at90("def"),
             "20": d.get("crit_rate", 0.05), "22": d.get("crit_dmg", 0.5), "23": 1.0, "28": d.get("elemental_mastery", 0)}
    for key, value in asc.items():
        if key in GI_PROPS:
            props[GI_PROPS[key]] = props.get(GI_PROPS[key], 0) + value
    props[genshin.HP] = props["1"] * (1 + props.get("3", 0))
    props[genshin.ATK] = props["4"] * (1 + props.get("6", 0))
    props[genshin.DEF] = props["7"] * (1 + props.get("9", 0))
    icon = d.get("icon") or ""
    skills = [s.get("id") for s in (d.get("skills") or [])[:3]]
    name_key = f"Unreleased_{cid}"
    return {
        "name": d.get("name"),
        "data": {
            "gi_avatars": {cid: {
                "Unreleased": True, "Element": GI_ELEMENTS.get(d.get("element"), d.get("element") or "None"), "NameTextMapHash": name_key,
                "SideIconName": "/ui/" + icon.replace("UI_AvatarIcon_", "UI_AvatarIcon_Side_") + ".png" if icon else None,
                "QualityType": d.get("rarity"), "WeaponType": d.get("weapon"), "SkillOrder": skills, "ProudMap": {},
                "Consts": [f"/ui/{c['icon']}.png" for c in d.get("constellations") or [] if c.get("icon")],
            }},
        },
        "text": {name_key: d.get("name")},
        "raw": {"avatarId": int(cid), "propMap": {"4001": {"val": "90"}}, "fightPropMap": props,
                "skillLevelMap": {str(s): 10 for s in skills}, "equipList": []},
    }


CONVERT = {"genshin": _genshin, "hsr": _hsr, "zzz": _zzz}


class Unreleased:
    def __init__(self, cache_dir: str | Path):
        self.path = Path(cache_dir) / "unreleased.json"
        self.saved: dict[str, dict[str, dict]] = {}
        self.raw: dict[str, dict[str, dict]] = {g: {} for g in GAMES}  # game -> name -> made-up showcase entry
        try:
            self.saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    async def refresh(self, session, assets: Assets) -> None:
        """Reads the beta's new characters; keeps the saved ones when Hakushin can't be reached."""

        async def get(path: str):
            try:
                async with session.get(f"{HAKUSHIN}/{path}") as resp:
                    return await resp.json(content_type=None) if resp.status == 200 else None
            except Exception:
                return None

        manifest = await get("manifest.json")
        if not manifest:
            log.warning("Could not read Hakushin's manifest; keeping the saved unreleased characters")
            self.apply(assets)
            return
        for game, short in GAMES.items():
            info = manifest.get(short) or {}
            if not info.get("latest") or info.get("latest") == info.get("live"):
                self.saved[game] = {}  # no beta running
                continue
            ids = [str(i) for i in (info.get("new") or {}).get("character") or []][:MAX_PER_GAME]
            pages = await asyncio.gather(*(get(f"{short}/{info['latest']}/en/character/{i}.json") for i in ids))
            found = {}
            for cid, page in zip(ids, pages):
                try:
                    if page and page.get("name"):
                        found[cid] = CONVERT[game](cid, page)
                except Exception:
                    log.exception("Could not read the unreleased %s character %s", game, cid)
            if found or all(p is not None for p in pages):
                self.saved[game] = found
        try:
            self.path.write_text(json.dumps(self.saved), encoding="utf-8")
        except OSError:
            log.exception("Could not save the unreleased characters")
        self.apply(assets)

    def apply(self, assets: Assets) -> None:
        """Writes the saved characters into the game data (again after each time it is re-read)."""
        self.raw = {g: {} for g in GAMES}
        for game, entries in self.saved.items():
            for cid, entry in entries.items():
                if game not in GAMES:
                    continue
                known = assets.data.get(STORE_KEY[game], {}).get(cid)
                if known and not known.get("Unreleased") and (game != "hsr" or cid in assets.data["hsr_meta"]["avatar"]):
                    continue  # released since: Enka's own entry is the one to use
                for key, part in entry.get("data", {}).items():
                    assets.data.setdefault(key, {}).update(part)
                for key, part in entry.get("meta", {}).items():
                    assets.data["hsr_meta"].setdefault(key, {}).update(part)
                texts = entry.get("text") or {}
                if game == "genshin":
                    assets._gi_names.update(texts)
                elif game == "zzz":
                    assets.data["zzz_locs"].setdefault(assets.lang, {}).update(texts)
                if entry.get("name"):
                    self.raw[game][entry["name"]] = entry["raw"]

    def names(self, game: str) -> list[str]:
        return list(self.raw.get(game, {}))

    def build(self, assets: Assets, game: str, name: str) -> CharacterBuild | None:
        """The unreleased character with no gear on, ready for bot/borrow.py."""
        raw = self.raw.get(game, {}).get(name)
        if raw is None:
            return None
        build = PARSERS[game].parse_character(assets, raw)
        build.raw = raw
        build.source = "beta"
        return build
