"""The guide to the commands: sent as a welcome DM when the owner adds someone with /access add, and shown by /help."""

from __future__ import annotations

import discord

GAMES = (("genshin", "Genshin Impact"), ("hsr", "Honkai: Star Rail"), ("zzz", "Zenless Zone Zero"))


def install_link(app_id: int) -> str:
    """Discord's link for adding the app to your own account (User Install), so its commands work everywhere."""
    return f"https://discord.com/oauth2/authorize?client_id={app_id}&integration_type=1&scope=applications.commands"


def guide_embed(bot_name: str, per_hour: int, app_id: int | None = None, welcome: bool = True,
                owner: bool = False) -> discord.Embed:
    """The guide, covering every command; /access only when it's for the owner."""
    embed = discord.Embed(
        title=f"You can now use {bot_name}" if welcome else f"How to use {bot_name}",
        description="It shows a character's stats and build as a card. Here's how it works.",
        color=0x8C7BFF,
    )
    if app_id:
        embed.add_field(
            name="First, add it to your Discord account",
            value=f"Click the bot's name, press **Add App** on its profile, then **Add to My Apps** and **Authorize**"
            f" (or use [this link]({install_link(app_id)}))."
            " Then the commands work in any server, group chat or DM, even where the bot isn't a member."
            " In servers that block outside apps, only you will see the replies.",
            inline=False,
        )
    embed.add_field(
        name="Look up a character",
        value="\n".join(f"`/{cmd}` for {name}" for cmd, name in GAMES)
        + "\nPick the `character` from the list, then add the player's `uid`.",
        inline=False,
    )
    embed.add_field(
        name="Save your own UID",
        value=" ".join(f"`/{cmd}-claim`" for cmd, _ in GAMES)
        + "\nClaim your UID once per game, and you can leave `uid` out to see your own characters."
        " Claiming again replaces the old one.",
        inline=False,
    )
    embed.add_field(
        name="On the card",
        value="Use the dropdown to switch to another character, or the button to open the profile on Enka.Network.",
        inline=False,
    )
    embed.add_field(
        name="Good to know",
        value="Only characters in the player's in-game showcase can be shown, with character details turned on."
        " After changing the showcase it can take a few minutes to update.\n"
        f"You can look up {per_hour} characters per hour.",
        inline=False,
    )
    if owner:
        embed.add_field(
            name="Only for you (the owner)",
            value="`/access add` lets someone use the bot and DMs them this guide, `/access remove` takes it away,"
            " and `/access list` shows who has access. You have no lookup limit.",
            inline=False,
        )
    embed.set_footer(text="Run /help any time to see this guide again.")
    return embed
