"""The guide to the commands, told by Fairy: sent as a welcome DM when the owner adds someone with /access add,
and shown by /help. Fairy opens with her guide book picture and signs off with a goodbye picture."""

from __future__ import annotations

from pathlib import Path

import discord

GAMES = (("genshin", "Genshin Impact"), ("hsr", "Honkai: Star Rail"), ("zzz", "Zenless Zone Zero"))
ART = Path(__file__).parent / "guide_art"
OPENING, CLOSING = "fairy-guide.jpg", "fairy-goodbye.jpg"
COLOR = 0x4FA3E0  # Fairy's blue
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
                  owner: bool = False) -> tuple[list[discord.Embed], list[discord.File]]:
    """The guide as four embeds (Fairy with her guide book, two pages of rules, Fairy's goodbye picture with the artist
    credits underneath) plus the two pictures.
    The files are new each call, since Discord uses them up when they're sent. Missing pictures are left out."""
    files = [discord.File(ART / name, filename=name) for name in (OPENING, CLOSING) if (ART / name).exists()]
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
        pages[page].add_field(name=f"{'①②③④⑤⑥'[step - 1]} {title}", value=text, inline=False)

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
        + "\nPick the `character` from the list, then give me the player's `uid`. I'll handle the rest.",
    )
    section(
        0,
        "Register your UID",
        " ".join(f"`/{cmd}-claim`" for cmd, _ in GAMES)
        + "\nRegister your UID once per game, and you may leave `uid` out to see your own characters."
        " Registering again simply overwrites the old record. I do keep good records, Proxy.",
    )
    section(
        1,
        "Operating the card",
        "Use the dropdown to switch to another character, or the button to open the profile on Enka.Network.",
    )
    section(
        1,
        "Rules",
        "I can only show characters in the player's in-game showcase, with character details turned on."
        " After changing the showcase, give the data a few minutes to update. Even I can't rush that.\n"
        f"You may look up **{per_hour}** characters per hour. Please don't overwork me, Proxy.",
    )
    if owner:
        section(
            1,
            "Administrator commands",
            "For you alone, Proxy. `/access add` grants someone access and sends them this guide,"
            " `/access remove` revokes it, and `/access list` shows everyone with access. You have no lookup limit.",
        )

    goodbye = discord.Embed(description=f"**{GOODBYE}**", color=COLOR)
    if CLOSING in have:
        goodbye.set_image(url=f"attachment://{CLOSING}")
    pages[0].set_footer(text="Page 1 / 2")
    pages[1].set_footer(text="Page 2 / 2  ·  Run /help any time to see this guide again.")
    goodbye.set_footer(text="   ·   ".join(_italic(f"{what} by @{who}") for what, who in CREDITS))
    return [intro, *pages, goodbye], files
