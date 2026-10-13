"""The guide to the commands, told by Fairy: sent as a welcome DM when the owner adds someone with /access add,
and shown by /help. Fairy opens with her guide book picture and signs off with the heart picture."""

from __future__ import annotations

from pathlib import Path

import discord

GAMES = (("genshin", "Genshin Impact"), ("hsr", "Honkai: Star Rail"), ("zzz", "Zenless Zone Zero"))
ART = Path(__file__).parent / "guide_art"
OPENING, CLOSING = "fairy-guide.jpg", "fairy-heart.jpg"
COLOR = 0x4FA3E0  # Fairy's blue
GOODBYE = "I am looking forward to working with you, Master~"


def install_link(app_id: int) -> str:
    """Discord's link for adding the app to your own account (User Install), so its commands work everywhere."""
    return f"https://discord.com/oauth2/authorize?client_id={app_id}&integration_type=1&scope=applications.commands"


def guide_message(bot_name: str, per_hour: int, app_id: int | None = None, welcome: bool = True,
                  owner: bool = False) -> tuple[list[discord.Embed], list[discord.File]]:
    """The guide as three embeds (Fairy with her guide book, the rules, Fairy's goodbye) plus the two pictures.
    The files are new each call, since Discord uses them up when they're sent. Missing pictures are left out."""
    files = [discord.File(ART / name, filename=name) for name in (OPENING, CLOSING) if (ART / name).exists()]
    have = {f.filename for f in files}

    intro = discord.Embed(
        title="Fairy's Guide for Master" if welcome else "Fairy's Guide, once more",
        description=(
            f"Access to **{bot_name}** has been granted, Master. I am Fairy, and I will be assisting you."
            " I have compiled everything you need into this guide. Please read it carefully."
            " I would rather not explain it twice."
            if welcome else
            "You need a refresher, Master? Very well. I have reopened the guide for you."
            " Do try to remember it this time."
        ),
        color=COLOR,
    )
    if OPENING in have:
        intro.set_image(url=f"attachment://{OPENING}")

    rules = discord.Embed(color=COLOR)
    step = 0

    def section(title: str, text: str) -> None:
        nonlocal step
        step += 1
        rules.add_field(name=f"{'①②③④⑤⑥'[step - 1]} {title}", value=text, inline=False)

    if app_id:
        section(
            "Link me to your account",
            "First things first, Master. Click the bot's name, press **Add App** on its profile, then"
            f" **Add to My Apps** and **Authorize**. If that fails, [this link]({install_link(app_id)}) does the same."
            " After that I can follow you into any server, group chat or DM, even where the bot isn't a member."
            " In servers that block outside apps, only you will see my replies.",
        )
    section(
        "Look up a character",
        "\n".join(f"`/{cmd}` for {name}" for cmd, name in GAMES)
        + "\nPick the `character` from the list, then give me the player's `uid`. I'll handle the rest.",
    )
    section(
        "Register your UID",
        " ".join(f"`/{cmd}-claim`" for cmd, _ in GAMES)
        + "\nRegister your UID once per game, and you may leave `uid` out to see your own characters."
        " Registering again simply overwrites the old record. I do keep good records, Master.",
    )
    section(
        "Operating the card",
        "Use the dropdown to switch to another character, or the button to open the profile on Enka.Network.",
    )
    section(
        "Rules",
        "I can only show characters in the player's in-game showcase, with character details turned on."
        " After changing the showcase, give the data a few minutes to update. Even I can't rush that.\n"
        f"You may look up **{per_hour}** characters per hour. Please don't overwork me, Master.",
    )
    if owner:
        section(
            "Administrator commands",
            "For you alone, Master. `/access add` grants someone access and sends them this guide,"
            " `/access remove` revokes it, and `/access list` shows everyone with access. You have no lookup limit.",
        )

    goodbye = discord.Embed(description=f"**{GOODBYE}**", color=COLOR)
    if CLOSING in have:
        goodbye.set_image(url=f"attachment://{CLOSING}")
    goodbye.set_footer(text="Run /help any time to see this guide again.")
    return [intro, rules, goodbye], files
