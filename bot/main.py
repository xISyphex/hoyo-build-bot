"""Discord entry point: /genshin, /hsr and /zzz slash commands."""

from __future__ import annotations

import asyncio
import logging
import os
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks

from . import matching
from .assets import Assets
from .embeds import build_embed
from .enka import EnkaClient, EnkaError
from .models import PlayerProfile

log = logging.getLogger("hoyo-bot")

USER_AGENT = os.environ.get("ENKA_USER_AGENT", "HoyoBuildBot/1.0 (Discord bot)")
UID_RE = re.compile(r"^\d{8,10}$")
GAME_NAMES = {"genshin": "Genshin Impact", "hsr": "Honkai: Star Rail", "zzz": "Zenless Zone Zero"}


class HoyoBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self)
        self.assets = Assets(os.environ.get("CACHE_DIR", "data"))
        self.session: aiohttp.ClientSession | None = None
        self.enka: EnkaClient | None = None

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}, trust_env=True)
        self.enka = EnkaClient(self.session, self.assets)
        if self.assets.is_stale():
            log.info("Downloading game data from Enka.Network")
            await self.assets.refresh(self.session)
        else:
            self.assets.load()
        self.refresh_assets.start()

        for game in GAME_NAMES:
            self.tree.add_command(make_command(game))
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
        await interaction.response.edit_message(
            embed=build_embed(self.profile, build), view=CharacterView(self.profile, build.name)
        )


class CharacterView(discord.ui.View):
    def __init__(self, profile: PlayerProfile, current: str):
        super().__init__(timeout=600)
        if len(profile.characters) > 1:
            self.add_item(CharacterSelect(profile, current))
        self.add_item(discord.ui.Button(label="Open on Enka.Network", url=profile.profile_url))


def make_command(game: str) -> app_commands.Command:
    @app_commands.command(name=game, description=f"Show a {GAME_NAMES[game]} character's stats and build")
    @app_commands.describe(uid="In-game UID", character="Character name (from the player's showcase)")
    async def command(interaction: discord.Interaction, uid: str, character: str) -> None:
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        uid = uid.strip()
        if not UID_RE.match(uid):
            await interaction.response.send_message("A UID is 8 to 10 digits, like `618285856`.", ephemeral=True)
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
        await interaction.followup.send(embed=build_embed(profile, build), view=CharacterView(profile, build.name))

    @command.autocomplete("character")
    async def character_autocomplete(interaction: discord.Interaction, current: str):
        bot: HoyoBot = interaction.client  # type: ignore[assignment]
        uid = str(getattr(interaction.namespace, "uid", "") or "").strip()
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


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set the DISCORD_TOKEN environment variable to your bot token.")
    HoyoBot().run(token, log_handler=None)


if __name__ == "__main__":
    run()
