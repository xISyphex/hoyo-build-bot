#!/usr/bin/env bash
# Installs the bot as an always-on service on a fresh Debian/Ubuntu VM
# (e.g. Google Cloud's free e2-micro). Run it again to update to the latest main.
#   curl -fsSL https://raw.githubusercontent.com/xISyphex/hoyo-build-bot/main/deploy/gcp-setup.sh | sudo bash
set -euo pipefail

REPO=https://github.com/xISyphex/hoyo-build-bot.git
APP=/opt/hoyo-build-bot
ENV_FILE=/etc/hoyo-build-bot.env

if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo." >&2; exit 1; fi

apt-get update -qq
apt-get install -y -qq git python3 python3-venv >/dev/null

# 1 GB of RAM is enough to run the bot, but pip installs are safer with some swap.
if ! swapon --show | grep -q .; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

id hoyobot >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin hoyobot
if [ -d "$APP/.git" ]; then
  git -c safe.directory="$APP" -C "$APP" pull --ff-only
else
  git clone --depth 1 "$REPO" "$APP"
fi
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
mkdir -p "$APP/data"
chown -R hoyobot:hoyobot "$APP"

if [ ! -s "$ENV_FILE" ]; then
  # Read from the terminal so the token never lands in shell history or a file in the repo.
  read -rsp "Paste your Discord bot token and press Enter: " token </dev/tty; echo
  install -m 600 /dev/null "$ENV_FILE"
  printf 'DISCORD_TOKEN=%s\nCACHE_DIR=%s/data\n' "$token" "$APP" > "$ENV_FILE"
fi

cat > /etc/systemd/system/hoyo-build-bot.service <<UNIT
[Unit]
Description=Hoyo Build Bot (Discord)
After=network-online.target
Wants=network-online.target

[Service]
User=hoyobot
WorkingDirectory=$APP
EnvironmentFile=$ENV_FILE
ExecStart=$APP/.venv/bin/python -m bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable hoyo-build-bot >/dev/null
systemctl restart hoyo-build-bot
sleep 15
systemctl --no-pager --lines=15 status hoyo-build-bot || true
echo
echo "Done. Live logs: sudo journalctl -u hoyo-build-bot -f"
