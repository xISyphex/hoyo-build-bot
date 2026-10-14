"""HoYoLAB's Battle Chronicle: every character a player owns, not just the in-game showcase.

Only used for characters Enka.Network can't show, because one HoYoLAB account may look up at most 30 different
UIDs a day. It needs the cookies of a HoYoLAB account (HOYOLAB_COOKIES, kept on the bot's server like the token),
and only works for players whose Battle Chronicle is public.

Names, art and icons come from the same game data as the Enka cards (looked up by character ID), so both kinds of
card look the same; levels, stats and gear come from HoYoLAB.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import re
import time

import genshin
import pydantic

from .assets import Assets
from .effective import EffectiveStats
from .games import genshin as gi
from .games import starrail as sr
from .games import zenless as zz
from .games import fmt_int
from .hoyolab_links import LinkStore
from .models import CharacterBuild, Gear, Stat, Weapon
from .records import Record, read_records

log = logging.getLogger(__name__)

CACHE_SECONDS = 30 * 60
NOTE = "From HoYoLAB: this character isn't on the player's in-game showcase."


class HoyolabError(Exception):
    """Raised with a message that is safe to show to Discord users."""


def _num(text) -> float:
    """'1,234' -> 1234.0, '46.6%' -> 46.6, '' -> 0."""
    match = re.search(r"-?\d+(?:\.\d+)?", str(text or "").replace(",", ""))
    return float(match.group()) if match else 0.0


def _is_pct(text) -> bool:
    return "%" in str(text or "")


def _sets(gear: list[Gear]) -> list[str]:
    counts: dict[str, int] = {}
    for piece in gear:
        counts[piece.set_name] = counts.get(piece.set_name, 0) + 1
    bonuses = []
    for name, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        if count >= 4:
            bonuses.append(f"4pc {name}")
        elif count >= 2:
            bonuses.append(f"2pc {name}")
    return bonuses


# --- Genshin -----------------------------------------------------------------------------------------------------

# HoYoLAB's property types are the game's own fight property numbers.
GI_PROPS = {
    1: "FIGHT_PROP_BASE_HP", 2: "FIGHT_PROP_HP", 3: "FIGHT_PROP_HP_PERCENT", 4: "FIGHT_PROP_BASE_ATTACK",
    5: "FIGHT_PROP_ATTACK", 6: "FIGHT_PROP_ATTACK_PERCENT", 7: "FIGHT_PROP_BASE_DEFENSE", 8: "FIGHT_PROP_DEFENSE",
    9: "FIGHT_PROP_DEFENSE_PERCENT", 20: "FIGHT_PROP_CRITICAL", 22: "FIGHT_PROP_CRITICAL_HURT",
    23: "FIGHT_PROP_CHARGE_EFFICIENCY", 26: "FIGHT_PROP_HEAL_ADD", 28: "FIGHT_PROP_ELEMENT_MASTERY",
    30: "FIGHT_PROP_PHYSICAL_ADD_HURT", 40: "FIGHT_PROP_FIRE_ADD_HURT", 41: "FIGHT_PROP_ELEC_ADD_HURT",
    42: "FIGHT_PROP_WATER_ADD_HURT", 43: "FIGHT_PROP_GRASS_ADD_HURT", 44: "FIGHT_PROP_WIND_ADD_HURT",
    45: "FIGHT_PROP_ROCK_ADD_HURT", 46: "FIGHT_PROP_ICE_ADD_HURT",
}
GI_SLOTS = dict(enumerate(gi.SLOT_ORDER, start=1))  # pos 1 = Flower ... 5 = Circlet
GI_ELEMENT_DMG = {"Pyro": 40, "Electro": 41, "Hydro": 42, "Dendro": 43, "Anemo": 44, "Geo": 45, "Cryo": 46}


def _gi_stat(prop_type: int, value) -> Stat:
    return gi._prop(GI_PROPS.get(prop_type, str(prop_type)), _num(value))


def genshin_build(assets: Assets, char) -> CharacterBuild:
    """One genshin.py GenshinDetailCharacter as a build card."""
    skeleton = gi.parse_character(assets, {"avatarId": char.id, "propMap": {"4001": {"val": char.level}}})
    final = {}
    for prop in [*char.base_properties, *char.selected_properties, *char.extra_properties, *char.element_properties]:
        final.setdefault(prop.info.type, prop.final)

    def pct(t):
        return f"{_num(final.get(t)):.1f}%"

    stats = [
        Stat("HP", fmt_int(_num(final.get(2000)))),
        Stat("ATK", fmt_int(_num(final.get(2001)))),
        Stat("DEF", fmt_int(_num(final.get(2002)))),
        Stat("Elemental Mastery", fmt_int(_num(final.get(28)))),
        Stat("CRIT Rate", pct(20)),
        Stat("CRIT DMG", pct(22)),
        Stat("Energy Recharge", pct(23)),
    ]
    element = skeleton.element if skeleton.element in GI_ELEMENT_DMG else str(char.element).title()
    if _num(final.get(GI_ELEMENT_DMG.get(element))):
        stats.append(Stat(f"{element} DMG Bonus", pct(GI_ELEMENT_DMG[element])))
    if element != "Physical" and _num(final.get(30)):
        stats.append(Stat("Physical DMG Bonus", pct(30)))
    if _num(final.get(26)):
        stats.append(Stat("Healing Bonus", pct(26)))

    active = [s for s in char.skills if s.skill_type == 1][:3]
    talents = [Stat(label, str(s.level)) for label, s in zip(gi.TALENT_LABELS, active)]

    w = char.weapon
    weapon = Weapon(
        name=w.name, level=w.level, refinement=w.refinement, rarity=w.rarity,
        stats=[_gi_stat(p.info.type, p.final) for p in (w.main_stat, w.sub_stat) if p],
        icon_url=w.icon or None,
    )
    gear = []
    for art in char.artifacts:
        subs = [_gi_stat(s.info.type, s.value) for s in art.sub_stats]
        for stat, sub in zip(subs, art.sub_stats):
            stat.rolls = sub.times + 1  # times counts the upgrades, without the first roll
        gear.append(Gear(
            slot=GI_SLOTS.get(art.pos, "?"), set_name=art.set.name, level=art.level, rarity=art.rarity,
            main=_gi_stat(art.main_stat.info.type, art.main_stat.value), subs=subs, piece_icon=art.icon or None,
        ))
    gear.sort(key=lambda g: gi.SLOT_ORDER.index(g.slot) if g.slot in gi.SLOT_ORDER else 99)

    return dataclasses.replace(
        skeleton,
        name=skeleton.name if not skeleton.name.startswith("Character ") else char.name,
        level=char.level,
        element=element,
        constellation=char.constellation,
        stats=stats,
        talents=talents,
        weapon=weapon,
        gear=gear,
        set_bonuses=_sets(gear),
        notes=[NOTE], source="hoyolab",
        icon_url=skeleton.icon_url or char.icon,
    )


# --- Star Rail ---------------------------------------------------------------------------------------------------

SR_NAMES = {
    "Energy Regeneration Rate": "Energy Regen Rate",
    "Outgoing Healing Boost": "Outgoing Healing",
    "Break Effect": "Break Effect",
}
SR_ALWAYS = {"HP", "ATK", "DEF", "SPD", "CRIT Rate", "CRIT DMG", "Break Effect", "Energy Regen Rate",
             "Effect Hit Rate", "Effect RES"}
SR_SLOTS = dict(enumerate(sr.SLOT_ORDER, start=1))  # pos 1 = Head ... 6 = Link Rope
SR_TALENTS = dict(zip(("Point01", "Point02", "Point03", "Point04"), sr.TALENT_LABELS))


def _sr_stat(name: str, value, gear: bool = False) -> Stat:
    name = SR_NAMES.get(name, name)
    if gear:
        name = name.replace(" Boost", "")
        if _is_pct(value) and name in ("HP", "ATK", "DEF", "SPD"):
            name += "%"
    if _is_pct(value):
        return Stat(name, f"{_num(value):.1f}%")
    return Stat(name, f"{_num(value):.1f}" if name == "SPD" and _num(value) % 1 else fmt_int(_num(value)))


def starrail_build(assets: Assets, char) -> CharacterBuild:
    """One genshin.py Star Rail character (detailed, or simple when HoYoLAB hides the details) as a build card."""
    skeleton = sr.parse_character(assets, {"avatarId": char.id, "level": char.level, "rank": char.rank})
    notes = [NOTE]
    properties = getattr(char, "properties", None)
    stats = [_sr_stat(p.info.name, p.final) for p in properties or []]
    # Like the Enka cards: bonuses the character doesn't have (0%) are left out, the core stats always shown.
    stats = [st for st in stats if st.name in SR_ALWAYS or _num(st.value)]
    talents = []
    for skill in getattr(char, "skills", None) or []:
        if skill.anchor in SR_TALENTS and skill.point_type == 2:
            talents.append(Stat(SR_TALENTS[skill.anchor], str(skill.level)))
    talents.sort(key=lambda t: sr.TALENT_LABELS.index(t.name))

    weapon = None
    if char.equip:
        e = char.equip
        weapon = Weapon(name=e.name, level=e.level, refinement=e.rank, rarity=e.rarity,
                        icon_url=f"{sr.SRR_IMAGES}light_cone_preview/{e.id}.png")
    gear = []
    for relic in [*char.relics, *char.ornaments]:
        main = getattr(relic, "main_property", None)
        subs = []
        for p in getattr(relic, "properties", None) or []:
            stat = _sr_stat(p.info.property_name_relic or p.info.name, p.value, gear=True)
            stat.rolls = p.times
            subs.append(stat)
        slot = SR_SLOTS.get(relic.pos, "?")
        set_id = assets.data["hsr_relics"].get(str(relic.id), {}).get("SetID")
        set_name = (assets.hsr_set_name(set_id) if set_id else None) or relic.name
        gear.append(Gear(
            slot=slot, set_name=set_name, level=relic.level, rarity=relic.rarity,
            # Without details, HoYoLAB only says which piece it is and its level.
            main=_sr_stat(main.info.property_name_relic or main.info.name, main.value, gear=True) if main
            else Stat(slot, f"+{relic.level}"),
            subs=subs, piece_icon=relic.icon or None,
        ))
    gear.sort(key=lambda g: sr.SLOT_ORDER.index(g.slot) if g.slot in sr.SLOT_ORDER else 99)
    if not properties:
        notes.append("HoYoLAB doesn't share this player's stats or relic stats, only levels and gear.")
    outfit = getattr(char, "is_wearing_outfit", False)  # HoYoLAB's pictures then show the outfit
    return dataclasses.replace(
        skeleton, level=char.level, constellation=char.rank, stats=stats, talents=talents or skeleton.talents,
        weapon=weapon, gear=gear, set_bonuses=_sets(gear), notes=notes, source="hoyolab",
        art_url=char.image if outfit and getattr(char, "image", None) else skeleton.art_url,
        outfit_icon=char.icon if outfit and getattr(char, "icon", None) else None,
    )


# --- Zenless Zone Zero -------------------------------------------------------------------------------------------

ZZZ_RARITY = {"S": 4, "A": 3, "B": 2}
ZZZ_NAMES = {"Energy Regen": "Energy Regen", "Anomaly Proficiency": "Anomaly Proficiency"}
ZZZ_SKILLS = dict(zz.SKILLS)  # skill type -> label; 5 is the core skill


def _zzz_line(prop) -> Stat:
    """A disc or W-Engine line: the property IDs are the game's own, so Enka's naming applies."""
    pid = int(prop.type)
    value = _num(prop.value)
    _, kind = zz.GROUPS.get(pid // 100, ("", "int"))
    return zz._prop_stat(pid, value * 100 if _is_pct(prop.value) or kind == "pct" else value)


# One roll of each disc substat on an S-rank disc (A-rank rolls are 2/3 of it, B-rank 1/3). HoYoLAB only gives the
# total, so the rolls are worked out from it.
ZZZ_ROLL = {11103: 112, 11102: 3.0, 12103: 19, 12102: 3.0, 13103: 15, 13102: 4.8, 20103: 2.4, 21103: 4.8,
            31203: 9, 23203: 9}
ZZZ_ROLL_SCALE = {"S": 1, "A": 2 / 3, "B": 1 / 3}


def _zzz_sub(prop, rarity: str) -> Stat:
    stat = _zzz_line(prop)
    one = ZZZ_ROLL.get(int(prop.type), 0) * ZZZ_ROLL_SCALE.get(rarity, 1)
    if one:
        stat.rolls = max(1, round(_num(prop.value) / one))
    return stat


def zzz_build(assets: Assets, agent) -> CharacterBuild:
    """One genshin.py ZZZFullAgent as a build card."""
    skeleton = zz.parse_character(assets, {"Id": agent.id, "Level": agent.level, "TalentLevel": agent.rank})
    stats = [Stat(ZZZ_NAMES.get(p.name, p.name), p.final) for p in agent.properties if p.final not in ("", None)]
    talents = []
    for label in [label for _, label in zz.SKILLS]:
        skill = next((s for s in agent.skills if ZZZ_SKILLS.get(int(s.type)) == label), None)
        if skill is None:
            continue
        if label == "Core":
            talents.append(Stat(label, "ABCDEF"[skill.level - 2] if 2 <= skill.level <= 7 else "-"))
        else:
            talents.append(Stat(label, str(skill.level)))

    weapon = None
    if agent.w_engine:
        w = agent.w_engine
        weapon = Weapon(name=w.name, level=w.level, refinement=int(w.refinement), rarity=ZZZ_RARITY.get(w.rarity, 0),
                        stats=[_zzz_line(p) for p in [*w.main_properties, *w.properties]], icon_url=w.icon or None)
    gear = []
    for disc in agent.discs:
        main = disc.main_properties[0] if disc.main_properties else None
        gear.append(Gear(
            slot=f"Disc {disc.position}", set_name=re.sub(r"\s*\[\d\]$", "", disc.name), level=disc.level,
            rarity=ZZZ_RARITY.get(disc.rarity, 0), main=_zzz_line(main) if main else Stat("?", "?"),
            subs=[_zzz_sub(p, disc.rarity) for p in disc.properties], piece_icon=disc.icon or None,
        ))
    gear.sort(key=lambda g: g.slot)
    return dataclasses.replace(
        skeleton, level=agent.level, constellation=agent.rank, stats=stats or skeleton.stats,
        talents=talents or skeleton.talents, weapon=weapon, gear=gear, set_bonuses=_sets(gear), notes=[NOTE], source="hoyolab",
        # in an outfit, HoYoLAB's full picture shows it
        art_url=agent.banner_icon if getattr(agent, "outfit_id", None) and getattr(agent, "banner_icon", None) else skeleton.art_url,
    )


# --- The client --------------------------------------------------------------------------------------------------

ERRORS = (
    (genshin.DataNotPublic, "Their HoYoLAB Battle Chronicle is private, so I can't see the rest of their characters."),
    (genshin.errors.UserNotesAccessDenied, "HoYoLAB only shares these builds with the player themselves, so I can't see the rest of their characters."),
    (genshin.AccountNotFound, "They don't have a HoYoLAB profile for this game, so I can't see the rest of their characters."),
    (genshin.TooManyRequests, "The bot has reached HoYoLAB's daily limit of 30 players. Characters off the showcase work again tomorrow."),
    (genshin.InvalidCookies, "The bot's HoYoLAB login has expired, so only showcase characters work for now."),
)

RECORD_ERRORS = (
    (genshin.DataNotPublic, "Their HoYoLAB Battle Chronicle is private, so their battle records can't be shown."
                            " They can make it public in HoYoLAB, or link their own account with `/hoyolab link`."),
    (genshin.AccountNotFound, "They don't have a HoYoLAB profile for this game, so there are no battle records to show."),
    (genshin.TooManyRequests, "The bot has reached HoYoLAB's daily limit of 30 players. Try again tomorrow."),
    (genshin.InvalidCookies, "The bot's HoYoLAB login has expired, so battle records can't be read right now."),
)


class HoyolabClient:
    """Reads HoYoLAB with the login of whoever linked the UID (/hoyolab link), else with the server's own
    (HOYOLAB_COOKIES), if there is one."""

    def __init__(self, cookies: str | None, assets: Assets, links: LinkStore | None = None,
                 effective: EffectiveStats | None = None):
        self.client = genshin.Client(cookies, lang="en-us") if cookies else None
        self.links = links
        self.effective = effective  # Genshin's substat recommendations are picked up from the details read here
        self._clients: dict[str, genshin.Client] = {}  # one per linked login
        self.assets = assets
        self._cache: dict[tuple[str, str], tuple[float, list[CharacterBuild]]] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        # Answers like "private" are kept too: asking again would only use up the daily limit.
        self._failed: dict[tuple[str, str], tuple[float, str]] = {}
        self._calendars: dict[str, tuple[float, object]] = {}  # each game's version and banners, for /<game>-patch
        self._own_uids: dict[str, int] = {}  # the server's own account in each game, which calendars are read for

    def _client_for(self, game: str, uid: str) -> tuple[genshin.Client | None, bool]:
        """The client to ask about this UID, and whether it's the player's own linked login."""
        cookies = self.links.cookies_for(game, uid) if self.links else None
        if cookies:
            if cookies not in self._clients:
                self._clients[cookies] = genshin.Client(cookies, lang="en-us")
            return self._clients[cookies], True
        return self.client, False

    def available(self, game: str, uid: str) -> bool:
        """Whether HoYoLAB can be asked about this UID at all."""
        return self._client_for(game, uid)[0] is not None

    def forget(self, uids: dict[str, list[str]]) -> None:
        """Drops what's kept for these UIDs, e.g. after someone links or unlinks them."""
        for game, game_uids in uids.items():
            for uid in game_uids:
                self._cache.pop((game, uid), None)
                self._failed.pop((game, uid), None)
        still_linked = self.links.all_cookies() if self.links else set()
        self._clients = {c: client for c, client in self._clients.items() if c in still_linked}

    def cached(self, game: str, uid: str) -> list[CharacterBuild] | None:
        entry = self._cache.get((game, uid))
        return entry[1] if entry and entry[0] > time.monotonic() else None

    async def fetch(self, game: str, uid: str) -> list[CharacterBuild]:
        """Every character the player owns, as build cards. Cached for half an hour."""
        key = (game, uid)
        if (hit := self.cached(game, uid)) is not None:
            return hit
        async with self._locks.setdefault(key, asyncio.Lock()):
            if (hit := self.cached(game, uid)) is not None:
                return hit
            failed = self._failed.get(key)
            if failed and failed[0] > time.monotonic():
                raise HoyolabError(failed[1])
            client, linked = self._client_for(game, uid)
            if client is None:
                raise HoyolabError("HoYoLAB isn't set up for this player.")
            try:
                builds = await self._fetch(client, game, int(uid))
            except genshin.GenshinException as exc:
                message = next((m for kind, m in ERRORS if isinstance(exc, kind)), None)
                if linked and isinstance(exc, genshin.InvalidCookies):
                    message = "Their HoYoLAB link has expired. They can run `/hoyolab link` again."
                if message is None:
                    log.warning("HoYoLAB error for %s %s: %s", game, uid, exc)
                    raise HoyolabError("HoYoLAB returned an error, so only showcase characters work right now.") from exc
                if isinstance(exc, (genshin.DataNotPublic, genshin.AccountNotFound, genshin.errors.UserNotesAccessDenied)):
                    self._failed[key] = (time.monotonic() + CACHE_SECONDS, message)
                raise HoyolabError(message) from exc
            except Exception as exc:
                log.exception("Could not read HoYoLAB data for %s %s", game, uid)
                raise HoyolabError("Couldn't read HoYoLAB right now, so only showcase characters work.") from exc
            self._cache[key] = (time.monotonic() + CACHE_SECONDS, builds)
            now = time.monotonic()
            for k in [k for k, (expires, _) in self._cache.items() if expires < now]:
                self._cache.pop(k, None)
            for k in [k for k, (expires, _) in self._failed.items() if expires < now]:
                self._failed.pop(k, None)
            return builds

    async def records(self, game: str, uid: str, modes: list[str]) -> list[Record]:
        """The player's battle records for these modes (see records.py)."""
        client, linked = self._client_for(game, uid)
        if client is None:
            raise HoyolabError("Battle records come from HoYoLAB, and the bot has no HoYoLAB login set up.")
        try:
            return await read_records(client, game, int(uid), modes)
        except genshin.GenshinException as exc:
            if linked and isinstance(exc, genshin.InvalidCookies):
                raise HoyolabError("Their HoYoLAB link has expired. They can run `/hoyolab link` again.") from exc
            message = next((m for kind, m in RECORD_ERRORS if isinstance(exc, kind)), None)
            if message is None:
                log.warning("HoYoLAB records error for %s %s: %s", game, uid, exc)
                message = "HoYoLAB returned an error. Try again later."
            raise HoyolabError(message) from exc

    async def _fetch(self, client: genshin.Client, game: str, uid: int) -> list[CharacterBuild]:
        builds = []
        if game == "genshin":
            data = await self._genshin_details(client, uid)
            raw = data.characters
            convert = genshin_build
        elif game == "hsr":
            try:
                data = await client.get_starrail_characters(uid)
            except (pydantic.ValidationError, KeyError, TypeError):  # relics come without stats when HoYoLAB hides them
                data = await client.get_starrail_characters(uid, simple=True)
            raw = data.avatar_list
            convert = starrail_build
        else:
            agents = await client.get_zzz_agents(uid)
            raw = []
            for start in range(0, len(agents), 5):  # a few at a time, one request per agent
                raw += await client.get_zzz_agent_info([a.id for a in agents[start:start + 5]], uid=uid)
            convert = zzz_build
        for item in raw:
            try:
                builds.append(convert(self.assets, item))
            except Exception:
                log.exception("Could not read a HoYoLAB %s character (%s)", game, getattr(item, "id", "?"))
        builds.sort(key=lambda b: (-b.rarity, -b.level, b.name))
        return builds

    async def _genshin_details(self, client: genshin.Client, uid: int) -> genshin.models.GenshinDetailCharacters:
        raw = await client.get_genshin_detailed_characters(uid, return_raw_data=True)
        if self.effective:
            self.effective.learn_genshin(raw)
        return genshin.models.GenshinDetailCharacters(**raw)

    def own_server(self, game: str) -> str | None:
        """The server of the account the calendars are read for (its mid-version times are that server's)."""
        from .card import server_name

        uid = self._own_uids.get(game)
        return server_name(game, str(uid)) if uid else None

    async def patch(self, game: str):
        """The game's current version, its end and its banners, from HoYoLAB's calendars read with the server's own
        login (for its own account in that game). Kept for 10 minutes."""
        from . import patch as patches

        if self.client is None:
            raise HoyolabError("The bot has no HoYoLAB login, so it can't read the current version.")
        hit = self._calendars.get(game)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        try:
            if game not in self._own_uids:
                biz = {"genshin": "hk4e", "hsr": "hkrpg", "zzz": "nap"}[game]
                own = [a for a in await self.client.get_game_accounts() if str(a.game_biz).startswith(biz)]
                if not own:
                    raise HoyolabError("The bot's HoYoLAB account doesn't play this game, so it can't read its calendar.")
                self._own_uids[game] = int(own[0].uid)
            uid = self._own_uids[game]
            if game == "hsr":
                info = patches.hsr_patch(await self.client.get_starrail_event_calendar(uid))
            elif game == "genshin":
                info = patches.genshin_patch(await self.client.get_genshin_event_calendar(uid))
            else:
                gacha = await self.client.get_zzz_gacha_calendar(uid)
                events = await self.client.get_zzz_event_calendar(uid)

                def weapon_name(weapon_id) -> str | None:
                    meta = self.assets.data.get("zzz_weapons", {}).get(str(weapon_id), {})
                    return self.assets.zzz_text(meta.get("ItemName")) if meta else None

                info = patches.zzz_patch(gacha, events, weapon_name)
        except HoyolabError:
            raise
        except Exception as exc:
            log.warning("Could not read the %s calendar: %s", game, exc)
            raise HoyolabError("HoYoLAB didn't answer just now. Try again in a bit.") from exc
        self._calendars[game] = (time.monotonic() + 600, info)
        return info

    async def learn_own(self) -> None:
        """Reads the Genshin substat recommendations of every character on the server's own HoYoLAB account (they
        only come with a player's character details). Done once a day; failures are only logged."""
        if not (self.client and self.effective):
            return
        try:
            accounts = await self.client.get_game_accounts()
            for account in accounts:
                if str(account.game_biz).startswith("hk4e"):
                    await self._genshin_details(self.client, int(account.uid))
        except Exception as exc:
            log.warning("Could not read Genshin substat recommendations from HoYoLAB: %s", exc)
