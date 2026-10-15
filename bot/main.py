"""Discord entry point: /genshin, /hsr and /zzz lookups plus the /<game>-claim commands."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import io
import logging
import math
import os
import random
import re
import time

import aiohttp
import discord
import genshin
from discord import app_commands
from discord.ext import tasks

from . import matching, patch, records
from .access import PRIVATE, AccessList
from .assets import Assets
from .claims import ClaimStore
from .card import CardMaker, server_name
from .embeds import build_embed
from .effective import EffectiveStats
from .enka import ERRORS, EnkaClient, EnkaError
from .guide import ART, OpenGuideButton, PageButton, guide_message, open_guide_view
from .hoyolab import HoyolabClient, HoyolabError
from .hoyolab_links import LinkStore, cookie_string, games_of, load_key
from .models import CharacterBuild, PlayerProfile
from .ratelimit import LookupLimit
from .set_emojis import SetEmojis

log = logging.getLogger("hoyo-bot")

USER_AGENT = os.environ.get("ENKA_USER_AGENT", "HoyoBuildBot/1.0 (Discord bot)")
UID_RE = re.compile(r"^\d{8,10}$")
GAME_NAMES = {"genshin": "Genshin Impact", "hsr": "Honkai: Star Rail", "zzz": "Zenless Zone Zero"}
PROFILE_URLS = {"genshin": "https://enka.network/u/{uid}/", "hsr": "https://enka.network/hsr/{uid}/",
                "zzz": "https://enka.network/zzz/{uid}/"}


class PrivateTree(app_commands.CommandTree):
    """Lets only the owner and the users on the access list run commands."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.client.access.allowed(interaction.user.id):
            return True
        if interaction.type == discord.InteractionType.application_command:
            await interaction.response.send_message(PRIVATE, ephemeral=True)
        return False  # autocomplete just shows no suggestions


class HoyoBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.none())
        # Commands work wherever the bot is in the server, and also for people who added it
        # to their own account ("User Install"): in any server, DMs and group chats.
        self.tree = PrivateTree(
            self,
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        )
        cache_dir = os.environ.get("CACHE_DIR", "data")
        self.assets = Assets(cache_dir)
        # Lives next to the game data, which the VM setup script and the Docker volume keep across updates.
        self.claims = ClaimStore(os.environ.get("CLAIMS_FILE", os.path.join(cache_dir, "claims.json")))
        self.access = AccessList(os.environ.get("ACCESS_FILE", os.path.join(cache_dir, "access.json")))
        # New lookups per person per hour (the owner has no limit); the dropdown and buttons don't count.
        self.lookups = LookupLimit(int(os.environ.get("LOOKUPS_PER_HOUR", "15")))
        self.session: aiohttp.ClientSession | None = None
        self.enka: EnkaClient | None = None
        # Characters off the showcase, from HoYoLAB; only when the server has a HoYoLAB login (cookies).
        # People's own HoYoLAB logins (/hoyolab link) unlock their own UIDs; HOYOLAB_COOKIES is the server's own.
        # Their cookies are encrypted with a key kept outside the data folder (or given as HOYOLAB_LINKS_KEY).
        key = load_key(os.environ.get("HOYOLAB_KEY_FILE", ".hoyolab.key"), os.environ.get("HOYOLAB_LINKS_KEY"))
        self.links = LinkStore(os.environ.get("HOYOLAB_LINKS_FILE", os.path.join(cache_dir, "hoyolab_links.json")), key)
        cookies = os.environ.get("HOYOLAB_COOKIES", "").strip()
        # Which substats each character wants, for the effective substat count on the card.
        self.effective = EffectiveStats(cache_dir)
        self.hoyolab = HoyolabClient(cookies or None, self.assets, self.links, self.effective)
        self.set_emojis: SetEmojis | None = None
        self.cards: CardMaker | None = None

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}, trust_env=True)
        self.enka = EnkaClient(self.session, self.assets)
        self.set_emojis = SetEmojis(self, self.session)
        self.cards = CardMaker(self.session, self.assets.cache_dir, self.effective)
        if self.assets.is_stale():
            log.info("Downloading game data from Enka.Network")
            await self.assets.refresh(self.session)
        else:
            self.assets.load()
        self.refresh_assets.start()
        self.warm_calendars.start()

        # The bot's owner (or its team on the Developer Portal) always has access and manages the list.
        app = await self.application_info()
        self.access.owners = {m.id for m in app.team.members} if app.team else {app.owner.id}

        for game in GAME_NAMES:
            self.tree.add_command(make_command(game))
            self.tree.add_command(make_claim_command(game))
            self.tree.add_command(make_records_command(game))
            self.tree.add_command(make_patch_command(game))
        self.tree.add_command(AccessGroup())
        self.tree.add_command(HoyolabGroup())
        self.tree.add_command(help_command)
        self.tree.add_command(pat_command)
        self.add_dynamic_items(PageButton, OpenGuideButton)  # the guide's buttons, also on old messages
        guild_id = os.environ.get("DEV_GUILD_ID")
        if guild_id:
            # Guild commands appear instantly; global ones can take up to an hour.
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    @tasks.loop(hours=12)
    async def refresh_assets(self) -> None:
        if self.assets.is_stale():
            await self.assets.refresh(self.session)
        if self.effective.is_stale():
            await self.effective.refresh(self.session)
            await self.hoyolab.learn_own()

    @tasks.loop(minutes=30)
    async def warm_calendars(self) -> None:
        """The patch commands' calendars, read ahead so the commands answer at once."""
        await self.hoyolab.warm_calendars(GAME_NAMES)

    @refresh_assets.before_loop
    @warm_calendars.before_loop
    async def _wait_ready(self) -> None:
        await self.wait_until_ready()

    async def close(self) -> None:
        if self.session:
            await self.session.close()
        await super().close()


async def render(bot: HoyoBot, profile: PlayerProfile, build: CharacterBuild) -> dict:
    """The build card image and its dropdown for one character, ready to send.

    If the card can't be drawn, the reply falls back to the all-text embed.
    """
    view = CharacterView(profile, build)
    try:
        png = await bot.cards.render(profile, build)
    except Exception:
        log.exception("Could not draw the build card for %s", build.name)
    else:
        return {"embed": None, "view": view, "file": discord.File(io.BytesIO(png), filename="build.png")}
    pieces = await bot.set_emojis.for_pieces(build)
    return {"embed": build_embed(profile, build, piece_emojis=pieces), "view": view}


def as_edit(reply: dict) -> dict:
    """The same reply for editing a message: the card replaces the old one (or is removed)."""
    reply = dict(reply)
    file = reply.pop("file", None)
    reply["attachments"] = [file] if file else []
    return reply


class CharacterSelect(discord.ui.Select):
    """Dropdown to flip between the other characters in the same showcase."""

    def __init__(self, profile: PlayerProfile, current: str):
        shown = profile.characters[:25]
        if all(c.name != current for c in shown):  # Discord allows 25 options; keep the one on screen
            shown = [*shown[:24], *(c for c in profile.characters if c.name == current)]
        options = [
            discord.SelectOption(
                label=c.name[:100],
                description=f"Lv. {c.level}" + (" · from HoYoLAB" if c.source == "hoyolab" else ""),
                default=c.name == current,
            )
            for c in shown
        ]
        super().__init__(placeholder="Show another character", options=options)
        self.profile = profile

    async def callback(self, interaction: discord.Interaction) -> None:
        build = next(c for c in self.profile.characters if c.name == self.values[0])
        # Drawing a new card can take longer than Discord's 3-second reply window.
        await interaction.response.defer()
        await interaction.edit_original_response(**as_edit(await render(interaction.client, self.profile, build)))


class CharacterView(discord.ui.View):
    def __init__(self, profile: PlayerProfile, build: CharacterBuild):
        super().__init__(timeout=600)
        if len(profile.characters) > 1:
            self.add_item(CharacterSelect(profile, build.name))
        self.add_item(discord.ui.Button(label="Open on Enka.Network", url=profile.profile_url))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.client.access.allowed(interaction.user.id):
            return True
        await interaction.response.send_message(PRIVATE, ephemeral=True)
        return False


def make_command(game: str) -> app_commands.Command:
    @app_commands.command(name=game, description=f"Show a {GAME_NAMES[game]} character's stats and build")
    @app_commands.describe(
        character="Character name (from the player's showcase)",
        uid="In-game UID. Leave empty to use the one you claimed with /" + game + "-claim",
    )
    async def command(interaction: discord.Interaction, character: str, uid: str | None = None) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        uid = resolve_uid(bot.claims, interaction.user.id, game, uid)
        if uid is None:
            await interaction.response.send_message(
                f"Add a `uid`, or claim your own once with `/{game}-claim` so you can leave it out.",
                ephemeral=True,
            )
            return
        if not UID_RE.match(uid):
            await interaction.response.send_message("A UID is 8 to 10 digits, like `618285856`.", ephemeral=True)
            return
        if not bot.access.is_owner(interaction.user.id):
            next_free = bot.lookups.take(interaction.user.id)
            if next_free is not None:
                await interaction.response.send_message(
                    f"You've used your {bot.lookups.per_hour} lookups for this hour. "
                    f"You can look up again <t:{math.ceil(next_free)}:R>.",
                    ephemeral=True,
                )
                return
        await interaction.response.defer(thinking=True)
        profile, problem = None, None
        hoyolab = bot.hoyolab.available(game, uid)
        try:
            profile = await bot.enka.fetch(game, uid)
        except EnkaError as exc:
            # A UID that doesn't exist stays an error; with Enka down, HoYoLAB can still help.
            if not hoyolab or str(exc) in (ERRORS[400], ERRORS[404]):
                await interaction.followup.send(str(exc))
                return
            problem = str(exc)
        except Exception:
            log.exception("Failed to load %s profile %s", game, uid)
            if not hoyolab:
                await interaction.followup.send("Something went wrong reading that profile. Try again later.")
                return
            problem = "Something went wrong reading that profile on Enka.Network."
        if profile is None:
            profile = PlayerProfile(game, uid, f"UID {uid}", 0, [], 60, PROFILE_URLS[game].format(uid=uid))
        if hoyolab and (known := bot.hoyolab.cached(game, uid)):
            profile = with_hoyolab(profile, known)

        match, hoyolab_problem = pick(bot, game, profile, character), None
        if not match and hoyolab and bot.hoyolab.cached(game, uid) is None:
            # Not on the showcase: HoYoLAB has every character, if the player's Battle Chronicle is public.
            try:
                profile = with_hoyolab(profile, await bot.hoyolab.fetch(game, uid))
            except HoyolabError as exc:
                hoyolab_problem = str(exc)
            match = pick(bot, game, profile, character)
        if not match:
            extra = f"\n{hoyolab_problem}" if hoyolab_problem else ""
            if problem:
                await interaction.followup.send(problem + extra)
            elif not profile.characters:
                hint = (
                    "Their in-game character showcase is empty or has **Show Character Details** turned off. "
                    "They can turn it on in their in-game profile, then try again in a few minutes."
                )
                await interaction.followup.send(f"**{profile.nickname}** (UID {uid}) has no characters to show. {hint}{extra}")
            else:
                names = [c.name for c in profile.characters]
                where = "characters" if hoyolab and hoyolab_problem is None else "showcase"
                await interaction.followup.send(
                    f"**{character}** isn't in {profile.nickname}'s {where}. "
                    f"Characters shown: {', '.join(names[:40])}{' and more' if len(names) > 40 else ''}.\n"
                    + ("Only the characters on the in-game profile showcase can be looked up." if where == "showcase" else "")
                    + extra
                )
            return
        build = next(c for c in profile.characters if c.name == match)
        await interaction.followup.send(**await render(bot, profile, build))

    @command.autocomplete("character")
    async def character_autocomplete(interaction: discord.Interaction, current: str):
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        uid = resolve_uid(bot.claims, interaction.user.id, game, getattr(interaction.namespace, "uid", None)) or ""
        names: list[str] = []
        if UID_RE.match(uid):
            # Only use a profile we already have; autocomplete must answer within 3 seconds.
            profile = bot.enka.cached(game, uid)
            if profile:
                names = [c.name for c in profile.characters]
                known = bot.hoyolab.cached(game, uid) if bot.hoyolab.available(game, uid) else None
                names += [b.name for b in known or []]
            else:
                # Warm the cache so the next keystroke can put their showcase first.
                task = asyncio.create_task(bot.enka.fetch(game, uid))
                task.add_done_callback(lambda t: t.cancelled() or t.exception())
        # Every character in the game is suggested; the player's own come first when nothing is typed yet.
        names = list(dict.fromkeys(names + bot.assets.character_names(game)))
        return [app_commands.Choice(name=n, value=n) for n in matching.suggest(current, names)]

    return command


def make_records_command(game: str) -> app_commands.Command:
    keys = [m.key for m in records.MODES[game]]
    modes_help = ", ".join(f"{m.key} ({m.title})" for m in records.MODES[game])

    @app_commands.command(name=f"{game}-records", description=f"Show a player's {GAME_NAMES[game]} battle records")
    @app_commands.describe(
        modes=f"Which modes, e.g. `{' '.join(keys[:2])}`. Leave empty for all: {modes_help}"[:100],
        uid="In-game UID. Leave empty to use the one you claimed with /" + game + "-claim",
    )
    async def command(interaction: discord.Interaction, modes: str | None = None, uid: str | None = None) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        picked, unknown = records.parse_modes(game, modes)
        if unknown:
            await interaction.response.send_message(
                f"I don't know `{' '.join(unknown)}`. The modes are: {modes_help}.", ephemeral=True)
            return
        uid = resolve_uid(bot.claims, interaction.user.id, game, uid)
        if uid is None:
            await interaction.response.send_message(
                f"Add a `uid`, or claim your own once with `/{game}-claim` so you can leave it out.", ephemeral=True)
            return
        if not UID_RE.match(uid):
            await interaction.response.send_message("A UID is 8 to 10 digits, like `618285856`.", ephemeral=True)
            return
        if not bot.hoyolab.available(game, uid):
            await interaction.response.send_message(
                "Battle records come from HoYoLAB. Link your account with `/hoyolab link` to see your own.", ephemeral=True)
            return
        if not bot.access.is_owner(interaction.user.id):
            next_free = bot.lookups.take(interaction.user.id)
            if next_free is not None:
                await interaction.response.send_message(
                    f"You've used your {bot.lookups.per_hour} lookups for this hour. "
                    f"You can look up again <t:{math.ceil(next_free)}:R>.",
                    ephemeral=True,
                )
                return
        await interaction.response.defer(thinking=True)
        # The records, the player's characters (for weapon copies: HoYoLAB's list if it shares it, else their
        # showcase) and the in-game name from Enka are read at the same time; a recent Enka lookup is reused
        started = time.perf_counter()

        async def hoyolab_builds() -> list[CharacterBuild]:
            try:
                return await bot.hoyolab.fetch(game, uid)
            except HoyolabError:
                return []

        async def enka_profile():
            if (cached := bot.enka.cached(game, uid)) is not None:
                return cached
            try:
                return await bot.enka.fetch(game, uid)
            except Exception as exc:
                log.info("No Enka profile for %s %s: %s", game, uid, exc)
                return None

        found, builds, profile = await asyncio.gather(bot.hoyolab.records(game, uid, picked), hoyolab_builds(),
                                                      enka_profile(), return_exceptions=True)
        if isinstance(found, HoyolabError):
            await interaction.followup.send(str(found))
            return
        if isinstance(found, BaseException):
            raise found
        builds = list(builds) if isinstance(builds, list) else []
        profile = None if isinstance(profile, BaseException) else profile
        read = time.perf_counter()
        if profile:
            builds += profile.characters
        records.fill_copies(found, builds)
        try:
            png = await bot.cards.render_records(game, uid, found, profile.nickname if profile else None)
        except Exception:
            log.exception("Could not draw the %s battle records for %s", game, uid)
            await interaction.followup.send("Something went wrong drawing the battle records. Try again later.")
            return
        await interaction.followup.send(file=discord.File(io.BytesIO(png), filename="records.png"))
        log.info("%s records for %s: read in %.1fs, drawn and sent in %.1fs", game, uid, read - started, time.perf_counter() - read)

    @command.autocomplete("modes")
    async def modes_autocomplete(interaction: discord.Interaction, current: str):
        """Completes the last word typed, keeping the ones before it."""
        words = current.split()
        done = words if current.endswith(" ") or not words else words[:-1]
        last = "" if current.endswith(" ") or not words else words[-1].lower()
        prefix = " ".join(done)
        options = []
        for m in records.MODES[game]:
            if m.key in done or not m.key.startswith(last):
                continue
            value = f"{prefix} {m.key}".strip()
            options.append(app_commands.Choice(name=f"{value}  ({m.title})"[:100], value=value))
        if not done and not last:
            options.insert(0, app_commands.Choice(name="All modes", value=" ".join(keys)))
        return options[:25]

    return command


def pick(bot: HoyoBot, game: str, profile: PlayerProfile, query: str) -> str | None:
    """The character the caller means, if it's in this profile.

    The name is matched against every character in the game first, so a character missing from the showcase
    isn't mistaken for a similar-looking one that is on it.
    """
    names = [c.name for c in profile.characters]
    wanted = matching.find(query, list(dict.fromkeys(names + bot.assets.character_names(game))))
    if wanted in names:
        return wanted
    return None if wanted else matching.find(query, names)


def with_hoyolab(profile: PlayerProfile, builds: list[CharacterBuild]) -> PlayerProfile:
    """The profile with HoYoLAB's characters added after the showcase ones (which are kept as they are)."""
    have = {c.character_id for c in profile.characters} | {c.name for c in profile.characters}
    extra = [b for b in builds if b.character_id not in have and b.name not in have]
    return dataclasses.replace(profile, characters=[*profile.characters, *extra])


def resolve_uid(claims: ClaimStore, user_id: int, game: str, typed: str | None) -> str | None:
    """A typed UID wins; otherwise use the caller's claimed UID for this game."""
    typed = str(typed or "").strip()
    return typed or claims.get(user_id, game)


def make_claim_command(game: str) -> app_commands.Command:
    @app_commands.command(
        name=f"{game}-claim",
        description=f"Save your {GAME_NAMES[game]} UID so /{game} shows your own characters",
    )
    @app_commands.describe(uid="Your in-game UID")
    async def claim(interaction: discord.Interaction, uid: str) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        uid = uid.strip()
        if not UID_RE.match(uid):
            await interaction.response.send_message("A UID is 8 to 10 digits, like `618285856`.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        name = f"UID {uid}"
        try:
            profile = await bot.enka.fetch(game, uid)
            name = f"**{profile.nickname}** (UID {uid})"
        except EnkaError as exc:
            if str(exc) == ERRORS[404]:
                await interaction.followup.send(f"{exc} Nothing was claimed.")
                return
            # Enka being down shouldn't stop someone from saving their UID.
        except Exception:
            log.exception("Failed to check %s profile %s while claiming", game, uid)
        previous = bot.claims.set(interaction.user.id, game, uid)
        msg = f"Claimed {name} for {GAME_NAMES[game]}. Now `/{game}` with just a character shows your own build."
        if previous and previous != uid:
            msg += f" This replaces UID {previous}."
        await interaction.followup.send(msg)

    return claim


def make_patch_command(game: str) -> app_commands.Command:
    @app_commands.command(name=f"{game}-patch",
                          description=f"Show the current {GAME_NAMES[game]} version, its time left and banners")
    @app_commands.describe(uid=f"Any UID on your server, for its banner times. Leave empty to use your /{game}-claim")
    async def command(interaction: discord.Interaction, uid: str | None = None) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        uid = resolve_uid(bot.claims, interaction.user.id, game, uid)
        # The calendar is the same for everyone, so it's always the server login's, read ahead of time; the times
        # are then moved to the player's server (their own linked account's when no UID is given)
        mine = (bot.links.uids(interaction.user.id) or {}).get(game) or []
        uid = uid or (mine[0] if mine else None)
        await interaction.response.defer(thinking=True)
        try:
            info = await bot.hoyolab.patch(game)
        except HoyolabError as exc:
            await interaction.followup.send(str(exc))
            return
        except Exception:
            log.exception("Could not read the %s version", game)
            await interaction.followup.send("Something went wrong reading the current version. Try again later.")
            return
        # Mid-version banner switches happen at the same local time on every server, so move them to the player's
        server = server_name(game, uid) if uid else None
        info = dataclasses.replace(patch.for_server(info, info.server, server), now=dt.datetime.now(dt.timezone.utc))
        try:
            png = await bot.cards.render_patch(info)
        except Exception:
            log.exception("Could not draw the %s patch card", game)
            await interaction.followup.send(embed=patch.patch_embed(info))
            return
        text = f"Version {info.version} ends <t:{int(info.end.timestamp())}:f> (<t:{int(info.end.timestamp())}:R>)" if info.end else ""
        await interaction.followup.send(text, file=discord.File(io.BytesIO(png), filename="patch.png"))

    return command


@app_commands.command(name="help", description="How to use the bot")
async def help_command(interaction: discord.Interaction) -> None:
    bot: HoyoBot = interaction.client  # type: ignore[assignment]
    embeds, files, view = guide_message(bot.user.name if bot.user else "the bot", bot.lookups.per_hour,
                                        bot.application_id, welcome=False, owner=bot.access.is_owner(interaction.user.id))
    await interaction.response.send_message(embeds=embeds, files=files, view=view, ephemeral=True)


PAT_LINES = (
    "Th-thank you, Proxy. That was... acceptable. You may continue.",
    "Thank you for the pat, Proxy. My processing efficiency just went up by 12%.",
    "Hmph. Thank you, Proxy. I'll pretend I didn't enjoy that.",
    "Thank you, Proxy~ Fairy will remember this kindness.",
)


@app_commands.command(name="pat", description="Pat Fairy")
async def pat_command(interaction: discord.Interaction) -> None:
    """Fairy enjoys it: her thanks with her happy face as a sticker-sized picture, in one message. (Bots can't send
    real stickers in command replies, and an emoji next to text shows small.)"""
    await interaction.response.send_message(random.choice(PAT_LINES),
                                            file=discord.File(ART / "fairy-happy.png", filename="fairy-happy.png"))


GAME_SHORT = {"genshin": "Genshin", "hsr": "Star Rail", "zzz": "ZZZ"}


def describe_uids(uids: dict[str, list[str]]) -> str:
    return ", ".join(f"{GAME_SHORT[g]} {', '.join(u)}" for g, u in uids.items() if u) or "no game accounts"


class LinkModal(discord.ui.Modal, title="Link your HoYoLAB account"):
    """Asks for the three HoYoLAB login cookies in a private form, so they never appear in a chat."""

    ltuid = discord.ui.TextInput(label="ltuid_v2 (a number)", max_length=30)
    ltoken = discord.ui.TextInput(label="ltoken_v2 (starts with v2_)", max_length=400)
    ltmid = discord.ui.TextInput(label="ltmid_v2", max_length=60)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True, thinking=True)
        values = [str(v.value).strip().strip('"').strip() for v in (self.ltuid, self.ltoken, self.ltmid)]
        cookies = cookie_string(*values)
        try:
            accounts = await genshin.Client(cookies, lang="en-us").get_game_accounts()
        except genshin.InvalidCookies:
            await interaction.followup.send(
                "Those cookies didn't work. Copy the three values again from hoyolab.com while logged in, then retry.",
                ephemeral=True,
            )
            return
        except Exception:
            log.exception("Could not check HoYoLAB cookies")
            await interaction.followup.send("Couldn't reach HoYoLAB to check them. Try again in a moment.", ephemeral=True)
            return
        uids = games_of(accounts)
        if not uids:
            await interaction.followup.send(
                "That HoYoLAB account has no Genshin, Star Rail or ZZZ accounts linked, so nothing was saved.", ephemeral=True
            )
            return
        previous = bot.links.uids(interaction.user.id) or {}
        bot.links.link(interaction.user.id, cookies, uids)
        bot.hoyolab.forget(previous)
        bot.hoyolab.forget(uids)
        await interaction.followup.send(
            f"Linked: {describe_uids(uids)}. Lookups of these UIDs can now show every character, not just the showcase, "
            "for anyone who looks them up. `/hoyolab unlink` deletes your cookies from the bot.",
            ephemeral=True,
        )


class HoyolabGroup(app_commands.Group):
    """/hoyolab link, unlink and status: people's own HoYoLAB logins, for their characters off the showcase."""

    def __init__(self) -> None:
        super().__init__(name="hoyolab", description="Show all your characters, not just your showcase")

    @app_commands.command(name="link", description="Link your HoYoLAB account so all your characters can be shown")
    async def link(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(LinkModal())

    @app_commands.command(name="unlink", description="Delete your HoYoLAB cookies from the bot")
    async def unlink(self, interaction: discord.Interaction) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        removed = bot.links.unlink(interaction.user.id)
        if removed is None:
            await interaction.response.send_message("You haven't linked a HoYoLAB account.", ephemeral=True)
            return
        bot.hoyolab.forget(removed)
        await interaction.response.send_message(
            "Done, your HoYoLAB cookies are deleted from the bot. To be extra safe, log out of hoyolab.com in your "
            "browser, which makes the old cookies stop working.",
            ephemeral=True,
        )

    @app_commands.command(name="status", description="Show which of your game accounts are linked")
    async def status(self, interaction: discord.Interaction) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        uids = bot.links.uids(interaction.user.id)
        msg = f"Linked: {describe_uids(uids)}." if uids is not None else "You haven't linked a HoYoLAB account. Use `/hoyolab link`."
        await interaction.response.send_message(msg, ephemeral=True)


class AccessGroup(app_commands.Group):
    """/access add, remove and list: who besides the owner may use the bot."""

    def __init__(self) -> None:
        super().__init__(name="access", description="Choose who can use this bot (owner only)")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.client.access.is_owner(interaction.user.id):
            return True
        await interaction.response.send_message("Only the bot's owner can change who has access.", ephemeral=True)
        return False

    @app_commands.command(name="add", description="Let someone use the bot")
    @app_commands.describe(user="The Discord user to allow")
    async def add(self, interaction: discord.Interaction, user: discord.User) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        added = bot.access.add(user.id, user.name)
        msg = f"{user.mention} can now use the bot." if added else f"{user.mention} already had access."
        tag = False
        if added:  # send them a guide to the commands
            try:
                embeds, files, view = guide_message(bot.user.name if bot.user else "the bot", bot.lookups.per_hour,
                                                    bot.application_id)
                await user.send(embeds=embeds, files=files, view=view)
                msg += " I sent them a DM with a guide to the commands."
            except discord.HTTPException:
                # Tag them here instead, with a button that shows the guide only to them (not in your own DMs with
                # the bot, where they can't see it).
                tag = not isinstance(getattr(interaction, "channel", None), discord.DMChannel)
                msg += (" I couldn't DM them a guide (their DMs are probably closed), so I tagged them here with a"
                        " button that opens it just for them." if tag else
                        " I couldn't DM them a guide (their DMs are probably closed). Run `/access add` again in a"
                        " channel they can see, or ask them to use `/help`.")
        await interaction.response.send_message(msg, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
        if tag:
            try:
                await interaction.followup.send(
                    f"{user.mention}, you can use **{bot.user.name if bot.user else 'the bot'}** now!"
                    " Fairy couldn't reach your DMs, so press the button to read her guide. Only you will see it.",
                    view=open_guide_view(user.id), allowed_mentions=discord.AllowedMentions(users=[user]),
                )
            except discord.HTTPException:
                log.exception("Could not tag %s in the channel", user.id)

    @app_commands.command(name="remove", description="Stop someone from using the bot")
    @app_commands.describe(user="The Discord user to remove")
    async def remove(self, interaction: discord.Interaction, user: discord.User) -> None:
        access: AccessList = interaction.client.access
        if access.is_owner(user.id):
            msg = "That's the bot's owner, who always has access."
        elif access.remove(user.id):
            msg = f"{user.mention} can no longer use the bot."
        else:
            msg = f"{user.mention} wasn't on the list."
        await interaction.response.send_message(msg, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="list", description="Show who can use the bot")
    async def list_(self, interaction: discord.Interaction) -> None:
        users = interaction.client.access.users
        lines = [f"• <@{uid}> ({name}, ID {uid})" for uid, name in users.items()]
        msg = "Besides you, these people can use the bot:\n" + "\n".join(lines) if lines else (
            "Only you can use the bot right now. Add people with `/access add`."
        )
        await interaction.response.send_message(msg[:2000], ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set the DISCORD_TOKEN environment variable to your bot token.")
    HoyoBot().run(token, log_handler=None)


if __name__ == "__main__":
    run()
