"""The guide to the commands, told by Fairy: sent as a welcome DM when the owner adds someone with /access add,
and shown by /help. Fairy opens with her guide book picture and signs off with a goodbye picture."""

from __future__ import annotations

from pathlib import Path

import discord

GAMES = (("genshin", "Genshin Impact"), ("hsr", "Honkai: Star Rail"), ("zzz", "Zenless Zone Zero"))
ART = Path(__file__).parent / "guide_art"
OPENING, CLOSING = "fairy-guide.jpg", "fairy-goodbye.jpg"
COLOR = 0x4FA3E0  # Fairy's blue
EXAMPLE_UID = "812345678"  # made up, only to show the format
GOODBYE = "I am looking forward to working with you, Proxy~"
CREDITS = (("Guide book art", "nobawns"), ("Goodbye art", "yasiro_hayate"))  # both on x.com


def _italic(text: str) -> str:
    """Slanted look-alike letters, since Discord footers (the small text under a picture) ignore *markdown*."""
    def slant(c: str) -> str:
        if "A" <= c <= "Z":
            return chr(0x1D608 + ord(c) - ord("A"))
        if "a" <= c <= "z":
            return chr(0x1D622 + ord(c) - ord("a"))
        return c
    return "".join(map(slant, text))


def install_link(app_id: int) -> str:
    """Discord's link for adding the app to your own account (User Install), so its commands work everywhere."""
    return f"https://discord.com/oauth2/authorize?client_id={app_id}&integration_type=1&scope=applications.commands"


def guide_message(bot_name: str, per_hour: int, app_id: int | None = None, welcome: bool = True,
                  owner: bool = False, page: int = 0) -> tuple[list[discord.Embed], list[discord.File], discord.ui.View]:
    """One page of the guide book, with a button to flip to the other page.
    Page 1 is Fairy with her guide book and the first rules; page 2 is the other rules and Fairy's goodbye picture
    with the artist credits underneath. The picture file is new each call, since Discord uses it up when it's sent.
    A missing picture is left out."""
    name = OPENING if page == 0 else CLOSING
    files = [discord.File(ART / name, filename=name)] if (ART / name).exists() else []
    have = {f.filename for f in files}

    intro = discord.Embed(
        title="Fairy's Guide for Proxy" if welcome else "Fairy's Guide, once more",
        description=(
            f"Access to **{bot_name}** has been granted, Proxy. I am Fairy, and I will be assisting you."
            " I have compiled everything you need into this guide. Please read it carefully."
            " I would rather not explain it twice."
            if welcome else
            "You need a refresher, Proxy? Very well. I have reopened the guide for you."
            " Do try to remember it this time."
        ),
        color=COLOR,
    )
    if OPENING in have:
        intro.set_image(url=f"attachment://{OPENING}")

    pages = [discord.Embed(color=COLOR), discord.Embed(color=COLOR)]
    step = 0

    def section(page: int, title: str, text: str) -> None:
        nonlocal step
        step += 1
        pages[page].add_field(name=f"{'①②③④⑤⑥⑦⑧⑨'[step - 1]} {title}", value=text, inline=False)

    if app_id:
        section(
            0,
            "Link me to your account",
            "First things first, Proxy. Click the bot's name, press **Add App** on its profile, then"
            f" **Add to My Apps** and **Authorize**. If that fails, [this link]({install_link(app_id)}) does the same."
            " After that I can follow you into any server, group chat or DM, even where the bot isn't a member."
            " In servers that block outside apps, only you will see my replies.",
        )
    section(
        0,
        "Look up a character",
        "\n".join(f"`/{cmd}` for {name}" for cmd, name in GAMES)
        + "\nPick the `character` from the list, then give me the player's `uid`. I'll handle the rest."
        f"\nExample: `/genshin character:Furina uid:{EXAMPLE_UID}`",
    )
    section(
        0,
        "Register your UID",
        " ".join(f"`/{cmd}-claim`" for cmd, _ in GAMES)
        + "\nRegister your UID once per game, and you may leave `uid` out to see your own characters."
        " Registering again simply overwrites the old record. I do keep good records, Proxy."
        " `/hoyolab link` registers your linked UIDs for you. With accounts on several servers, add `server`"
        " to pick one; without it I use your first."
        f"\nExample: `/hsr-claim uid:{EXAMPLE_UID}`, then `/hsr character:Acheron`",
    )
    section(
        1,
        "Operating the card",
        "Use the dropdown to switch to another character, or the button to open the profile on Enka.Network.",
    )
    section(
        1,
        "Show me everything",
        "Your showcase only holds a few characters. `/hoyolab link` lets me see all of yours, Proxy."
        " On hoyolab.com on a PC, log in, press **Ctrl+Shift+I**, open **Application → Cookies**,"
        " and copy `ltuid_v2`, `ltoken_v2` and `ltmid_v2` into the form. They are a login to your HoYoLAB account,"
        " so only share them if you trust this bot's owner. `/hoyolab status` shows what is linked,"
        " and `/hoyolab unlink` makes me forget them. Linking also registers your UIDs, so you can skip `-claim`.\nExample: `/hoyolab link`, then fill in the form.",
    )
    section(
        1,
        "Battle records",
        " ".join(f"`/{cmd}-records`" for cmd, _ in GAMES)
        + "\nYour endgame runs as one picture: scores, cycles, rankings and the teams you used, with every"
        " character's copies and their weapon's. Weapons are the ones equipped now: HoYoLAB doesn't keep the run's."
        " Name the modes you want, or leave `modes` empty for all of them."
        " With accounts on several servers, add `server` to pick one."
        " You don't need `/hoyolab link` for these, but the player's battle records must be public:"
        " on HoYoLAB, open your profile, go to **Privacy Settings** and turn on **Show my Battle Chronicle on my profile**."
        "\nExample: `/hsr-records modes:moc pf`",
    )
    section(
        1,
        "Rules",
        "Without `/hoyolab link`, I can only show characters in the player's in-game showcase, with character details turned on."
        " After changing the showcase, give the data a few minutes to update. Even I can't rush that.\n"
        f"You may look up **{per_hour}** characters per hour. Please don't overwork me, Proxy.",
    )
    section(
        1,
        "Other commands",
        "`/help` opens this guide again. `/genshin-patch`, `/hsr-patch` and `/zzz-patch` show the game's current version,"
        " how long it has left and the banners running now. And `/pat`... pats me. Not that I asked for it, Proxy."
        "\nExample: `/hsr-patch`",
    )
    if owner:
        section(
            1,
            "Administrator commands",
            "For you alone, Proxy. `/access add` grants someone access and sends them this guide,"
            " `/access remove` revokes it, and `/access list` shows everyone with access. You have no lookup limit."
            " `/genshin-news`, `/hsr-news` and `/zzz-news` post every new video from each game's"
            " YouTube channel in the channel you pick; leave `channel` empty to stop them."
            "\nExample: `/access add user:@Proxy`",
        )

    goodbye = discord.Embed(description=f"**{GOODBYE}**", color=COLOR)
    if CLOSING in have:
        goodbye.set_image(url=f"attachment://{CLOSING}")
    pages[0].set_footer(text="Page 1 / 2  ·  Press Next page to keep reading.")
    pages[1].set_footer(text="Page 2 / 2  ·  Run /help any time to see this guide again.")
    goodbye.set_footer(text="   ·   ".join(_italic(f"{what} by @{who}") for what, who in CREDITS))
    view = discord.ui.View(timeout=None)
    view.add_item(PageButton(1 - page, welcome))
    return ([intro, pages[0]] if page == 0 else [pages[1], goodbye]), files, view


class PageButton(discord.ui.DynamicItem[discord.ui.Button], template=r"guide:(?P<page>[01]):(?P<kind>[wh])"):
    """Flips the guide to the other page. The page and the kind of guide are in the button's ID, so it keeps working
    after the bot restarts, even on a welcome DM from weeks ago."""

    def __init__(self, page: int, welcome: bool) -> None:
        self.page, self.welcome = page, welcome
        super().__init__(discord.ui.Button(
            label="Next page ▶" if page == 1 else "◀ Previous page",
            style=discord.ButtonStyle.primary if page == 1 else discord.ButtonStyle.secondary,
            custom_id=f"guide:{page}:{'w' if welcome else 'h'}",
        ))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) -> "PageButton":
        return cls(int(match["page"]), match["kind"] == "w")

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        embeds, files, view = guide_message(
            bot.user.name if bot.user else "the bot", bot.lookups.per_hour, bot.application_id, self.welcome,
            bot.access.is_owner(interaction.user.id), self.page,
        )
        await interaction.response.edit_message(embeds=embeds, attachments=files, view=view)


def open_guide_view(user_id: int) -> discord.ui.View:
    """The button under a channel message that tags someone whose DMs are closed."""
    view = discord.ui.View(timeout=None)
    view.add_item(OpenGuideButton(user_id))
    return view


class OpenGuideButton(discord.ui.DynamicItem[discord.ui.Button], template=r"guide:open:(?P<user>\d+)"):
    """Shows the welcome guide privately to the person it was posted for. Like PageButton, it works after restarts."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(discord.ui.Button(
            label="Open Fairy's guide", emoji="📖", style=discord.ButtonStyle.primary, custom_id=f"guide:open:{user_id}",
        ))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) -> "OpenGuideButton":
        return cls(int(match["user"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                f"This guide is for <@{self.user_id}>. If you have access, `/help` shows you your own.", ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        bot = interaction.client
        embeds, files, view = guide_message(
            bot.user.name if bot.user else "the bot", bot.lookups.per_hour, bot.application_id,
        )
        await interaction.response.send_message(embeds=embeds, files=files, view=view, ephemeral=True)
