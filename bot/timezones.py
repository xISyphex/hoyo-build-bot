"""People's own time zones (/timezone), for the times drawn on the patch cards. Discord doesn't tell bots a user's time
zone, so each person picks theirs once; it's saved by Discord user ID to a small JSON file."""

from __future__ import annotations

import datetime as dt
import functools
import json
import logging
import os
import re
import zoneinfo
from pathlib import Path

log = logging.getLogger("hoyo-bot")
OFFSET = re.compile(r"^(?:UTC|GMT)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$", re.I)


@functools.lru_cache(maxsize=1)
def _names() -> tuple[str, ...]:
    """The tz database's zones, the region ones first (Europe/Berlin before Etc/GMT-1)."""
    names = zoneinfo.available_timezones()
    return tuple(sorted(n for n in names if "/" in n and not n.startswith(("Etc/", "SystemV/", "US/")))) + ("UTC",)


def parse(text: str | None) -> str | None:
    """The zone's saved name for what someone typed ("Europe/Berlin", "berlin", "UTC+2", "GMT-5:30"), or None."""
    text = (text or "").strip()
    if not text:
        return None
    if found := OFFSET.match(text):
        sign, hours, minutes = found[1], int(found[2]), int(found[3] or 0)
        if hours > 14 or minutes >= 60:
            return None
        return f"UTC{sign}{hours:02d}:{minutes:02d}"
    if text.upper() in ("UTC", "GMT", "Z"):
        return "UTC"
    key = text.replace(" ", "_").lower()
    exact = [n for n in _names() if n.lower() == key]
    city = [n for n in _names() if n.lower().rsplit("/", 1)[-1] == key]
    return (exact or city or [None])[0]


def zone(name: str | None) -> dt.tzinfo | None:
    """The tzinfo for a saved name, or None when it isn't one."""
    if not name:
        return None
    if found := OFFSET.match(name):
        delta = dt.timedelta(hours=int(found[2]), minutes=int(found[3] or 0))
        return dt.timezone(-delta if found[1] == "-" else delta, name)
    try:
        return zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return None


def suggest(current: str, limit: int = 25) -> list[str]:
    """Zones matching what's typed so far, those whose city starts with it first."""
    key = current.strip().replace(" ", "_").lower()
    if not key:
        return list(_names()[:limit])
    starts = [n for n in _names() if n.lower().rsplit("/", 1)[-1].startswith(key)]
    inside = [n for n in _names() if key in n.lower() and n not in starts]
    return (starts + inside)[:limit]


class TimezoneStore:
    """Maps a Discord user id to the name of their time zone."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._zones: dict[str, str] = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            log.exception("Could not read %s; starting with no time zones", self.path)
            self.path.replace(self.path.with_suffix(".broken.json"))
            return
        if isinstance(data, dict):
            self._zones = {str(u): str(z) for u, z in data.items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._zones, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def get(self, user_id: int) -> str | None:
        return self._zones.get(str(user_id))

    def set(self, user_id: int, name: str | None) -> None:
        """Save the user's zone, or forget it with None."""
        if name:
            self._zones[str(user_id)] = name
        else:
            self._zones.pop(str(user_id), None)
        self._save()
