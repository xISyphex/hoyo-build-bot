"""Discord entry point: /genshin, /hsr and /zzz lookups plus the /<game>-claim commands."""

from __future__ import annotations

import asyncio
import io
import logging
import math
import os
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks

from . import matching
from .access import PRIVATE, AccessList
from .assets import Assets
from .claims import ClaimStore
from .card import CardMaker
from .embeds import build_embed
from .enka import ERRORS, EnkaClient, EnkaError
from .models import CharacterBuild, PlayerProfile
from .ratelimit import LookupLimit
from .set_emojis import SetEmojis

log = logging.getLogger("hoyo-bot")

USER_AGENT = os.environ.get("ENKA_USER_AGENT", "HoyoBuildBot/1.0 (Discord bot)")
UID_RE = re.compile(r"^\d{8,10}$")
GAME_NAMES = {"genshin": "Genshin Impact", "hsr": "Honkai: Star Rail", "zzz": "Zenless Zone Zero"}


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
        self.set_emojis: SetEmojis | None = None
        self.cards: CardMaker | None = None

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}, trust_env=True)
        self.enka = EnkaClient(self.session, self.assets)
        self.set_emojis = SetEmojis(self, self.session)
        self.cards = CardMaker(self.session, self.assets.cache_dir)
        if self.assets.is_stale():
            log.info("Downloading game data from Enka.Network")
            await self.assets.refresh(self.session)
        else:
            self.assets.load()
        self.refresh_assets.start()

        # The bot's owner (or its team on the Developer Portal) always has access and manages the list.
        app = await self.application_info()
        self.access.owners = {m.id for m in app.team.members} if app.team else {app.owner.id}

        for game in GAME_NAMES:
            self.tree.add_command(make_command(game))
            self.tree.add_command(make_claim_command(game))
        self.tree.add_command(AccessGroup())
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

    @refresh_assets.before_loop
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
        options = [
            discord.SelectOption(label=c.name[:100], description=f"Lv. {c.level}", default=c.name == current)
            for c in profile.characters[:25]
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
        try:
            profile = await bot.enka.fetch(game, uid)
        except EnkaError as exc:
            await interaction.followup.send(str(exc))
            return
        except Exception:
            log.exception("Failed to load %s profile %s", game, uid)
            await interaction.followup.send("Something went wrong reading that profile. Try again later.")
            return

        if not profile.characters:
            hint = (
                "Their in-game character showcase is empty or has **Show Character Details** turned off. "
                "They can turn it on in their in-game profile, then try again in a few minutes."
            )
            await interaction.followup.send(f"**{profile.nickname}** (UID {uid}) has no characters to show. {hint}")
            return

        names = [c.name for c in profile.characters]
        match = matching.find(character, names)
        if not match:
            await interaction.followup.send(
                f"**{character}** isn't in {profile.nickname}'s showcase. "
                f"Characters shown: {', '.join(names)}.\n"
                "Only the characters on the in-game profile showcase can be looked up."
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
            else:
                # Warm the cache so the next keystroke can suggest their showcase.
                task = asyncio.create_task(bot.enka.fetch(game, uid))
                task.add_done_callback(lambda t: t.cancelled() or t.exception())
        if not names:
            names = bot.assets.character_names(game)
        return [app_commands.Choice(name=n, value=n) for n in matching.suggest(current, names)]

    return command


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
        added = interaction.client.access.add(user.id, user.name)
        msg = f"{user.mention} can now use the bot." if added else f"{user.mention} already had access."
        await interaction.response.send_message(msg, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

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
