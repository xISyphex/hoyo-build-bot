"""People's own HoYoLAB logins, linked with /hoyolab link.

HoYoLAB only shares full builds with the player themselves, so a person who links their HoYoLAB cookies lets the bot
show every character of the game accounts on that HoYoLAB account (to anyone who looks those UIDs up).

The cookies are a login to the person's HoYoLAB account: they are kept only in this file on the bot's server,
readable by its owner alone, and /hoyolab unlink deletes them.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("hoyo-bot")

# HoYoLAB's names for the games (game_biz, e.g. "hk4e_global") -> ours
GAME_BIZ = {"hk4e": "genshin", "hkrpg": "hsr", "nap": "zzz"}


def cookie_string(ltuid: str, ltoken: str, ltmid: str) -> str:
    return f"ltuid_v2={ltuid.strip()}; ltoken_v2={ltoken.strip()}; ltmid_v2={ltmid.strip()}"


def games_of(accounts) -> dict[str, list[str]]:
    """The UIDs per game on a HoYoLAB account (genshin.py game accounts), for the games the bot knows."""
    uids: dict[str, list[str]] = {}
    for account in accounts:
        game = GAME_BIZ.get(str(account.game_biz).split("_")[0])
        if game:
            uids.setdefault(game, []).append(str(account.uid))
    return uids


class LinkStore:
    """Discord user id -> {"cookies": ..., "uids": {game: [uid, ...]}}, saved to a JSON file only the bot can read."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._links: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            log.exception("Could not read %s; starting with no HoYoLAB links", self.path)
            self.path.replace(self.path.with_suffix(".broken.json"))
            return
        if isinstance(data, dict):
            self._links = {str(k): v for k, v in data.items() if isinstance(v, dict) and v.get("cookies")}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        # Created readable by the bot's own user only, before anything is written to it.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._links, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def link(self, user_id: int, cookies: str, uids: dict[str, list[str]]) -> None:
        self._links[str(user_id)] = {"cookies": cookies, "uids": uids}
        self._save()

    def unlink(self, user_id: int) -> dict[str, list[str]] | None:
        """Forgets the person's cookies. Returns the UIDs they had linked, if any."""
        entry = self._links.pop(str(user_id), None)
        if entry is None:
            return None
        self._save()
        return entry.get("uids", {})

    def uids(self, user_id: int) -> dict[str, list[str]] | None:
        entry = self._links.get(str(user_id))
        return entry.get("uids", {}) if entry else None

    def all_cookies(self) -> set[str]:
        return {entry["cookies"] for entry in self._links.values()}

    def cookies_for(self, game: str, uid: str) -> str | None:
        """The cookies of whoever linked this UID, if anyone did."""
        for entry in self._links.values():
            if uid in entry.get("uids", {}).get(game, []):
                return entry["cookies"]
        return None
