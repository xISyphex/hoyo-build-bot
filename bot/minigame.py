"""Discord side of the pull minigame (rules and storage are in gacha.py): /daily, /<game>-pull and /<game>-box."""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import random

import discord
from discord import app_commands

from . import gacha, patch
from .card import server_name
from .hoyolab import HoyolabError

log = logging.getLogger("hoyo-bot")

GAME_NAMES = {"genshin": "Genshin Impact", "hsr": "Honkai: Star Rail", "zzz": "Zenless Zone Zero"}
COLOURS = {5: 0xF2C14E, 4: 0xA77BE0, 3: 0x5B8FD6}
PULL_WORD = {"genshin": "wish", "hsr": "warp", "zzz": "signal search"}


def rarity(game: str, r: int) -> str:
    return {5: "S", 4: "A", 3: "B"}[r] if game == "zzz" else f"{r}★"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def banner_choices(info: patch.Patch) -> list[gacha.BannerChoice]:
    """The banners running now that can be pulled on, character banners first."""
    out = []
    for b in patch._running(info.banners, info.now):
        kind = gacha.BANNER_KINDS.get(b.kind)
        if kind is None or not b.featured:
            continue
        choice = gacha.BannerChoice(kind, " & ".join(b.featured), list(b.featured), list(b.others),
                                    set(b.others) if kind == "weapon" else set())
        if all(c.title != choice.title for c in out):
            out.append(choice)
    return sorted(out, key=lambda c: c.kind != "character")


def pick_banner(choices: list[gacha.BannerChoice], typed: str | None) -> gacha.BannerChoice | None:
    if not choices:
        return None
    if typed:
        typed = typed.casefold().strip()
        for c in choices:
            if c.title.casefold() == typed:
                return c
        for c in choices:
            if typed in c.title.casefold():
                return c
    return choices[0]


async def running_banners(bot, game: str, user_id: int) -> list[gacha.BannerChoice]:
    info = await bot.hoyolab.patch(game)
    uid = bot.claims.get(user_id, game)
    server = server_name(game, uid) if uid else None
    info = dataclasses.replace(patch.for_server(info, info.server, server), now=dt.datetime.now(dt.timezone.utc))
    return banner_choices(info)


# ---- /daily ---------------------------------------------------------------------------------------------------------

@app_commands.command(name="daily", description="Collect today's free pulls: one for each game you've claimed a UID in")
async def daily_command(interaction: discord.Interaction) -> None:
    bot = interaction.client
    now = dt.datetime.now(dt.timezone.utc)
    games = [g for g in GAME_NAMES if bot.claims.get(interaction.user.id, g)]
    reset = int(gacha.next_reset(now).timestamp())
    if not games:
        await interaction.response.send_message(
            "Proxy, I can only hand out pulls for games you've claimed a UID in. "
            "Claim yours with `/genshin-claim`, `/hsr-claim` or `/zzz-claim`, then come back.", ephemeral=True)
        return
    got = bot.gacha.daily(interaction.user.id, games, now)
    if got is None:
        await interaction.response.send_message(
            f"You've already collected today's supply, Proxy. The next one is ready <t:{reset}:R>.", ephemeral=True)
        return
    lines = [f"**+1** {GAME_NAMES[g]} pull · you have **{n}** (`/{g}-pull`)" for g, n in got.items()]
    missing = [g for g in GAME_NAMES if g not in got]
    if missing:
        lines.append("-# Claim a UID with " + ", ".join(f"`/{g}-claim`" for g in missing) + " to get those pulls too.")
    embed = discord.Embed(title="Fairy's daily supply", colour=0xFAC428,
                          description="Here's today's ration, Proxy. Spend it wisely.\n\n" + "\n".join(lines))
    embed.set_footer(text="Resets every day at 04:00 UTC+2")
    embed.add_field(name="Next supply", value=f"<t:{reset}:R>")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---- /<game>-pull ---------------------------------------------------------------------------------------------------

FAIRY_LINES = {
    5: ("Proxy! A golden signal! Fairy is... only slightly impressed.", "Jackpot, Proxy. Try not to let it go to your head."),
    4: ("Not bad, Proxy. Fairy has seen worse.", "A purple glow. Fairy files this under 'acceptable'."),
    3: ("Hmm. Fairy recommends lowering your expectations, Proxy.", "Nothing shiny this time, Proxy. The odds are like that."),
}


def pull_embed(game: str, banner: gacha.BannerChoice, results: list[gacha.Pull], left: int, pity: dict) -> discord.Embed:
    best = max(r.rarity for r in results)
    lines = []
    for r in results:
        if r.rarity == 5:
            tag = "" if r.featured else " · lost the 50/50" if banner.kind == "character" else " · off-banner"
            lines.append(f"🌟 **{r.name}** ({rarity(game, 5)}, pull {r.pity}{tag})")
        elif r.rarity == 4:
            lines.append(f"✨ {r.name} ({rarity(game, 4)})")
    threes = sum(r.rarity == 3 for r in results)
    if threes:
        lines.append(f"-# and {threes}× {gacha.THREE_STAR[game]}")
    rule = gacha.RULES[(game, banner.kind)]
    embed = discord.Embed(title=f"{plural(len(results), PULL_WORD[game])} on {banner.title}", colour=COLOURS[best],
                          description=random.choice(FAIRY_LINES[best]) + "\n\n" + "\n".join(lines))
    footer = f"{plural(left, 'pull')} left · {rarity(game, 5)} pity {pity.get('five', 0)}/{rule.hard}"
    if pity.get("guarantee"):
        footer += " · next is guaranteed"
    embed.set_footer(text=footer)
    return embed


def make_pull_command(game: str) -> app_commands.Command:
    @app_commands.command(name=f"{game}-pull", description=f"Spend your minigame pulls on a {GAME_NAMES[game]} banner running now")
    @app_commands.describe(count=f"How many to pull (1-{gacha.MAX_PULLS})",
                           banner="Which running banner. Leave empty for the first character banner")
    async def command(interaction: discord.Interaction, count: app_commands.Range[int, 1, gacha.MAX_PULLS] = 1,
                      banner: str | None = None) -> None:
        bot = interaction.client
        have = bot.gacha.pulls(interaction.user.id, game)
        if have < count:
            await interaction.response.send_message(
                f"You have {plural(have, 'pull')} for {GAME_NAMES[game]}, Proxy, not {count}. "
                "Collect more with `/daily`.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        try:
            choices = await running_banners(bot, game, interaction.user.id)
        except HoyolabError as exc:
            await interaction.followup.send(str(exc))
            return
        except Exception:
            log.exception("Could not read the %s banners for a pull", game)
            await interaction.followup.send("I couldn't read the current banners. Your pulls are safe; try again later.")
            return
        chosen = pick_banner(choices, banner)
        if chosen is None:
            await interaction.followup.send("No banner is running right now, Proxy. Your pulls are safe.")
            return
        results = bot.gacha.pull(interaction.user.id, game, chosen, count, gacha.pool(bot.assets, game))
        if results is None:  # spent elsewhere in the meantime
            await interaction.followup.send("You don't have that many pulls any more, Proxy.")
            return
        pity = bot.gacha.pity(interaction.user.id, game, chosen.kind)
        await interaction.followup.send(embed=pull_embed(game, chosen, results, bot.gacha.pulls(interaction.user.id, game), pity))

    @command.autocomplete("banner")
    async def banner_autocomplete(interaction: discord.Interaction, current: str):
        try:
            choices = await running_banners(interaction.client, game, interaction.user.id)
        except Exception:
            return []
        current = current.casefold()
        return [app_commands.Choice(name=c.title[:100], value=c.title[:100])
                for c in choices if current in c.title.casefold()][:25]

    return command


# ---- /<game>-box ----------------------------------------------------------------------------------------------------

PAGES = ("characters", "weapons")
PAGE_TITLES = {"genshin": ("Characters", "Weapons"), "hsr": ("Characters", "Light cones"), "zzz": ("Agents", "W-Engines")}


def box_embed(game: str, name: str, box: dict, page: str, pulls: int) -> discord.Embed:
    items = sorted(box.get(page, {}).items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
    lines = [f"{'🌟' if r == 5 else '✨'} {rarity(game, r)} **{n}** x{c}" for n, (r, c) in items]
    text = "\n".join(lines) or "Nothing here yet. Pull with `/" + game + "-pull`."
    if len(text) > 4000:
        text = text[:text.rfind("\n", 0, 3990)] + "\n…"
    title = PAGE_TITLES[game][PAGES.index(page)]
    embed = discord.Embed(title=f"{name}'s {GAME_NAMES[game]} box · {title}", description=text,
                          colour=COLOURS[max((r for r, _ in box.get(page, {}).values()), default=3)])
    total = sum(c for _, c in box.get(page, {}).values())
    embed.set_footer(text=f"{plural(total, 'item')} · {plural(pulls, 'pull')} left")
    return embed


class BoxView(discord.ui.View):
    def __init__(self, game: str, name: str, box: dict, pulls: int, page: str = "characters"):
        super().__init__(timeout=600)
        self.game, self.name, self.box, self.pulls = game, name, box, pulls
        for p, label in zip(PAGES, PAGE_TITLES[game]):
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary if p == page else discord.ButtonStyle.secondary)
            button.callback = self._show(p)
            self.add_item(button)

    def _show(self, page: str):
        async def callback(interaction: discord.Interaction) -> None:
            view = BoxView(self.game, self.name, self.box, self.pulls, page)
            await interaction.response.edit_message(embed=box_embed(self.game, self.name, self.box, page, self.pulls), view=view)
        return callback


def make_box_command(game: str) -> app_commands.Command:
    @app_commands.command(name=f"{game}-box", description=f"Show the 4- and 5-star {GAME_NAMES[game]} items pulled in the minigame")
    @app_commands.describe(user="Whose box to show. Leave empty for your own")
    async def command(interaction: discord.Interaction, user: discord.User | None = None) -> None:
        bot = interaction.client
        who = user or interaction.user
        box = bot.gacha.box(who.id, game)
        pulls = bot.gacha.pulls(who.id, game)
        await interaction.response.send_message(embed=box_embed(game, who.display_name, box, "characters", pulls),
                                                view=BoxView(game, who.display_name, box, pulls))

    return command
