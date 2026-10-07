# Running the bot 24/7 on Railway

The bot runs on [Railway](https://railway.com). It is deployed straight from this
GitHub repository, and every merge to `main` redeploys it automatically.

**Cost:** the Hobby plan is **$5 per month**, which includes $5 of usage. This bot
needs a small fraction of a CPU and roughly 150 MB of RAM, so it should stay inside
the included $5. New accounts first get a one-time trial credit.

## Why Railway

| Option | Monthly cost | Problem for this bot |
| --- | --- | --- |
| **Railway Hobby** | $5 | None. Runs in the background without sleeping, set up entirely in the browser. |
| Fly.io | about $2 to $3 | No free tier for new accounts since 2024, and setup needs a command-line tool on your PC. |
| Oracle Cloud Always Free | $0 | Oracle stops "idle" free machines, and a Discord bot looks idle. You also run a Linux server yourself. |
| Koyeb free | $0 | Free instance sleeps after 1 hour without web traffic and can't run background workers. |
| Render | $7 | Free services sleep; always-on background workers are paid only. |

## Setup (about 10 minutes)

You need the bot token from the Discord Developer Portal (see the README). You only
ever paste it into Railway; never put it in a file in this repository.

1. Go to <https://railway.com> and sign in with **GitHub**.
2. Click **New Project** → **Deploy from GitHub repo**. If asked, let Railway's
   GitHub app access `hoyo-build-bot`, then pick that repository.
3. Railway finds `railway.json` and builds the `Dockerfile`. The first build fails
   or crashes because the token is missing; that is expected.
4. Click the new service, open the **Variables** tab, click **New Variable**, and add
   - `DISCORD_TOKEN` = your bot token
   - optional: `DEV_GUILD_ID` = your server ID, so commands appear instantly there
5. Railway asks to **Deploy** the change. Click it.
6. Optional but recommended: add a **Volume** to the service (right-click the
   service on the project canvas, or **+ Create** → **Volume**) with mount path
   `/app/data`. The bot then keeps its downloaded
   game data across restarts instead of re-downloading it on each start.
7. Open **Deployments** → the latest one → **View Logs**. When you see a line
   ending in `has connected to Gateway`, the bot is online in Discord.

There is no need to add a domain or a port: the bot connects out to Discord and
never receives web traffic.

## Day to day

- **Updates:** merging a pull request into `main` redeploys automatically.
- **Crashes:** `railway.json` sets the restart policy to *Always*, so Railway restarts it.
- **Spending:** **Workspace → Usage** shows the month so far. You can set a usage
  limit there (for example $10) so a mistake can never cost more.
- **Changing the token:** edit `DISCORD_TOKEN` under **Variables** and redeploy.
- **Stopping the bot:** service **Settings** → **Delete service**, or remove the
  variable so it can't log in.
