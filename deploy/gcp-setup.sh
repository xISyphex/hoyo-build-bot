#!/usr/bin/env bash
# Installs the bot as an always-on service on a Linux server with systemd
# (Debian/Ubuntu, Fedora/RHEL/Rocky/Alma, openSUSE or Arch; e.g. Google Cloud's
# free e2-micro). Run it again to update to the latest main.
#   curl -fsSL https://raw.githubusercontent.com/xISyphex/hoyo-build-bot/main/deploy/gcp-setup.sh | sudo bash
set -euo pipefail

REPO=https://github.com/xISyphex/hoyo-build-bot.git
APP=/opt/hoyo-build-bot
ENV_FILE=/etc/hoyo-build-bot.env

if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo." >&2; exit 1; fi

if ! command -v systemctl >/dev/null || [ ! -d /run/systemd/system ]; then
  echo "This server doesn't run systemd, which the script needs to keep the bot running." >&2
  exit 1
fi

echo "Installing git and Python..."
if command -v apt-get >/dev/null; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git python3 python3-venv >/dev/null
elif command -v dnf >/dev/null; then
  dnf install -y -q git python3 >/dev/null
elif command -v yum >/dev/null; then
  yum install -y -q git python3 >/dev/null
elif command -v zypper >/dev/null; then
  zypper --non-interactive --quiet install git python3 >/dev/null
elif command -v pacman >/dev/null; then
  pacman -Sy --noconfirm --needed git python >/dev/null
else
  echo "Unknown Linux distribution: install git and Python 3.10 or newer, then run this again." >&2
  exit 1
fi

# The bot needs Python 3.10+. Older RHEL-likes and openSUSE ship an older python3
# but offer a newer one side by side, so try those too.
find_python() {
  for py in python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$py" >/dev/null && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      command -v "$py"; return 0
    fi
  done
  return 1
}
if ! PY="$(find_python)"; then
  if command -v dnf >/dev/null; then
    dnf install -y -q python3.12 >/dev/null 2>&1 || dnf install -y -q python3.11 >/dev/null 2>&1 || true
  elif command -v zypper >/dev/null; then
    zypper --non-interactive --quiet install python312 >/dev/null 2>&1 || zypper --non-interactive --quiet install python311 >/dev/null 2>&1 || true
  fi
  if ! PY="$(find_python)"; then
    echo "The bot needs Python 3.10 or newer, but this server has $(python3 -V 2>&1)." >&2
    echo "Upgrade the system (e.g. Debian 12 or Ubuntu 22.04 or newer) and run this again." >&2
    exit 1
  fi
fi

# Small servers install packages more reliably with some swap. Best effort only:
# some servers (containers, btrfs) can't use a swap file, and the bot runs without one.
if ! swapon --show 2>/dev/null | grep -q . && [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 2000000 ]; then
  if fallocate -l 1G /swapfile 2>/dev/null && chmod 600 /swapfile && mkswap /swapfile >/dev/null 2>&1 && swapon /swapfile 2>/dev/null; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
  else
    rm -f /swapfile
  fi
fi

id hoyobot >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell "$(command -v nologin || echo /bin/false)" hoyobot
if [ -d "$APP/.git" ]; then
  git -c safe.directory="$APP" -C "$APP" pull --ff-only
else
  git clone --depth 1 "$REPO" "$APP"
fi
# Rebuild the venv if it was made with a Python that is too old (e.g. after a move).
if [ -x "$APP/.venv/bin/python" ] && ! "$APP/.venv/bin/python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
  rm -rf "$APP/.venv"
fi
"$PY" -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
mkdir -p "$APP/data"
chown -R hoyobot:hoyobot "$APP"

# Ask for the token when there is none yet (or an earlier run saved it empty).
# Read from the terminal so it never lands in shell history or a file in the repo.
if ! grep -qE '^DISCORD_TOKEN=.+' "$ENV_FILE" 2>/dev/null; then
  token=""
  while [ -z "$token" ]; do
    read -rsp "Paste your Discord bot token and press Enter (nothing shows while pasting): " token </dev/tty; echo
    token="$(printf '%s' "$token" | tr -d '[:space:]')"
  done
  install -m 600 /dev/null "$ENV_FILE"
  printf 'DISCORD_TOKEN=%s\nCACHE_DIR=%s/data\n' "$token" "$APP" > "$ENV_FILE"
  echo "Token saved."
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
echo "Starting the bot..."
sleep 20
journalctl -u hoyo-build-bot -n 15 --no-pager -o cat || true
echo
if systemctl is-active --quiet hoyo-build-bot; then
  echo "Done. The bot is running. Live logs: sudo journalctl -u hoyo-build-bot -f"
else
  echo "The bot is not running. Send the lines above to whoever is helping you."
fi
