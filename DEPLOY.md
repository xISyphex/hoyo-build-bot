# Running the bot 24/7

Two ways to keep the bot online around the clock:

- **Option A: Google Cloud, free.** One small virtual machine that Google gives away
  permanently. Costs nothing if you stick to the settings below, but needs a credit
  card on file and a one-time setup in a browser terminal.
- **Option B: Railway, $5 per month.** Everything is clicks in the browser, and
  updates deploy themselves.

The bot only connects out to Discord and Enka; it never needs a website, domain or
open port. Get the bot token from the Discord Developer Portal first (see the README)
and never put it in a file in this repository.

## Other hosts considered

| Option | Monthly cost | Problem for this bot |
| --- | --- | --- |
| Oracle Cloud Always Free | $0 | Oracle stops free machines it sees as idle, and a Discord bot looks idle. |
| Koyeb free | $0 | Sleeps after 1 hour without web traffic and can't run background workers. |
| Render free | $0 | Sleeps; always-on background workers start at $7. |
| Fly.io | about $2 | No free tier for new accounts since 2024; setup needs a command-line tool. |
| Small "free Discord bot hosts" | $0 | Unknown companies holding your bot token; uptime often needs manual renewal. |

## Option A: Google Cloud free VM

Google's Always Free tier includes one **e2-micro** machine (2 shared CPUs, 1 GB RAM,
30 GB disk) in three US regions, every month, with no time limit. A credit card is
needed to create the billing account, but nothing is charged while you stay inside
those limits. The settings below keep you inside them. Your Google Cloud console may
show German labels; the names below are the English ones.

1. Go to <https://console.cloud.google.com>, sign in, and accept the terms. Create a
   billing account when asked (new accounts also get a 90-day trial credit).
2. Open **Compute Engine → VM instances** and click **Enable** for the API, then
   **Create instance**.
3. Use exactly these settings:
   - **Region:** `us-central1` (Iowa), `us-west1` (Oregon) or `us-east1` (South Carolina).
     Any other region is billed.
   - **Machine type:** series **E2**, type **e2-micro**.
   - **Boot disk:** Debian 12, **Standard persistent disk**, 30 GB or less.
     (The default "Balanced" disk is not free.)
   - Leave the firewall boxes for HTTP/HTTPS unticked.
4. Click **Create**. When the VM shows a green tick, click **SSH** in its row. A
   terminal opens in your browser.
5. Paste this line and press Enter:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/xISyphex/hoyo-build-bot/main/deploy/gcp-setup.sh | sudo bash
   ```

   It installs the bot, asks you to paste the token (the input stays hidden), and
   starts it as a service that restarts on crashes and reboots. The last lines show
   its status; `has connected to Gateway` in the log means the bot is online.

6. Optional safety net: **Billing → Budgets & alerts**, create a budget of $1 so
   Google emails you if anything ever starts costing money.

### Day to day on Google Cloud

- **Update the bot** after merging changes: open **SSH** again and run the same
  `curl ... | sudo bash` line. It keeps the token and pulls the latest `main`.
- **Logs:** `sudo journalctl -u hoyo-build-bot -f`
- **Change the token:** `sudo nano /etc/hoyo-build-bot.env`, then
  `sudo systemctl restart hoyo-build-bot`.
- **Stop:** `sudo systemctl disable --now hoyo-build-bot`, or delete the VM.

## Option B: Railway, $5 per month

Railway deploys straight from this GitHub repository and redeploys on every merge
to `main`. The Hobby plan is **$5 per month** including $5 of usage, which this bot
should stay inside. Setup takes about 10 minutes, all in the browser.

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

### Day to day on Railway

- **Updates:** merging a pull request into `main` redeploys automatically.
- **Crashes:** `railway.json` sets the restart policy to *Always*, so Railway restarts it.
- **Spending:** **Workspace → Usage** shows the month so far. You can set a usage
  limit there (for example $10) so a mistake can never cost more.
- **Changing the token:** edit `DISCORD_TOKEN` under **Variables** and redeploy.
- **Stopping the bot:** service **Settings** → **Delete service**, or remove the
  variable so it can't log in.
