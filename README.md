# Hoyo Build Bot

A Discord bot that shows a character's stats and build from a player's UID, for
**Genshin Impact**, **Honkai: Star Rail** and **Zenless Zone Zero**.

```
/genshin character:Ayaka uid:618285856
/hsr     character:Seele uid:800069903
/zzz     character:Anby uid:1300003409
```

Claim your own UID once per game with `/genshin-claim`, `/hsr-claim` or
`/zzz-claim`, and then `/hsr character:Seele` shows your own Seele without a UID.
Each person has one claimed UID per game; claiming again replaces it. A UID typed
into the lookup still wins over the claimed one. Claims are saved to
`claims.json` in the cache folder, so they survive restarts and updates.

The reply is just the build card image: the character art, constellations /
eidolons / mindscapes, final stats, every artifact / relic / drive disc with its
substats (a dot per upgrade), the weapon / light cone / W-Engine, set bonuses,
the Crit Value (CRIT DMG + CRIT Rate × 2 over all gear) and the server and UID.
A dropdown under it switches to the player's other showcased characters, next to
a link to the profile on Enka.Network.

Card pictures are downloaded once, shrunk and kept in `images/` inside the cache
folder. If a card can't be drawn, the bot falls back to an all-text reply whose
gear pictures are uploaded once as the bot's own application emojis (under
**Emojis** on the bot's page in the Discord Developer Portal). The card uses the
Inter font, bundled in `bot/fonts/` under the SIL Open Font License.

The bot is private: only its owner (the account that owns the app in the Discord
Developer Portal, or its team) and the people the owner adds can use it. The
owner manages the list from Discord with `/access add user:@someone`,
`/access remove user:@someone` and `/access list`; everyone else gets a short
"This bot is private" reply that only they can see. The list is saved to
`access.json` in the cache folder (override with `ACCESS_FILE`). Each person
can run 15 new lookups per hour (set `LOOKUPS_PER_HOUR` to change it); the
owner has no limit, and the dropdown and buttons on a card don't count.

Data comes from [Enka.Network](https://enka.network), which reads the player's
**in-game showcase**. Only characters on that showcase can be looked up, and the
player must have *Show Character Details* turned on in their profile.

## Setup

1. Create an application at <https://discord.com/developers/applications>, open
   **Bot**, and copy the token. No privileged intents are needed.
2. Invite it: **OAuth2 → URL Generator**, tick `bot` and `applications.commands`,
   permission *Send Messages* and *Embed Links*, then open the URL.
   To use the commands in servers without the bot too (and in DMs), open
   **Installation**, tick **User Install**, and add the app to your account with
   the install link shown there. Servers that block external apps show the
   reply only to you.
3. Run it (Python 3.10+):

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   export DISCORD_TOKEN=your-token-here
   export DEV_GUILD_ID=your-server-id   # optional: commands show up instantly in this server
   python -m bot
   ```

   Or with Docker:

   ```bash
   docker build -t hoyo-build-bot .
   docker run -d --restart unless-stopped -e DISCORD_TOKEN=your-token-here \
     -v hoyo-bot-data:/app/data hoyo-build-bot
   ```

To keep it online around the clock (free on Google Cloud, or $5/month on Railway), see [DEPLOY.md](DEPLOY.md).

Without `DEV_GUILD_ID`, commands are registered globally and can take up to an
hour to appear the first time.

| Variable | Required | Meaning |
| --- | --- | --- |
| `DISCORD_TOKEN` | yes | Bot token. Keep it out of git. |
| `DEV_GUILD_ID` | no | Server ID for instant command registration while testing. |
| `CACHE_DIR` | no | Where game data is cached (default `data`). |
| `ENKA_USER_AGENT` | no | User-Agent sent to Enka.Network. |
| `CLAIMS_FILE` | no | Where claimed UIDs are saved (default `claims.json` in `CACHE_DIR`). |

## How stats are computed

- **Genshin:** Enka sends the final stats directly.
- **Star Rail:** computed from Enka's `honker_meta.json` (character and light cone
  base stats, traces, relic main/sub stats, set bonuses, unconditional light cone
  passives), matching the in-game character screen.
- **ZZZ:** computed with the formulas in Enka's ZZZ docs. W-Engine and disc main
  stats use Enka's approximate formulas, which can be off by about 1.

Game data (names, base stats) is downloaded from Enka's
[API-docs store](https://github.com/EnkaNetwork/API-docs/tree/master/store) on
start and refreshed every 12 hours, so new characters work without a redeploy.
Profiles are cached for the `ttl` Enka returns, as Enka asks.

## Tests

```bash
python -m unittest discover tests
```

The tests parse hand-written API responses with the real game data (downloaded on
first run) and check the numbers against in-game values.

## Layout

```
bot/
  main.py        Discord client, slash commands, autocomplete, dropdown
  enka.py        Enka.Network HTTP client with ttl cache and error messages
  assets.py      Downloads and indexes Enka's game data files
  games/         One parser per game -> models.CharacterBuild
  card.py        Draws the build card image (Pillow)
  embeds.py      All-text fallback reply, used if the card can't be drawn
  matching.py    Forgiving name matching ("raiden", "hutao", typos)
  claims.py      Claimed UIDs per Discord user and game, saved as JSON
  access.py      Who may use the bot (owner + /access list), saved as JSON
  set_emojis.py  Uploads gear piece pictures as emojis (text fallback)
tests/           Parser tests with sample responses
```
