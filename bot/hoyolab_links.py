"""People's own HoYoLAB logins, linked with /hoyolab link.

HoYoLAB only shares full builds with the player themselves, so a person who links their HoYoLAB cookies lets the bot
show every character of the game accounts on that HoYoLAB account (to anyone who looks those UIDs up).

The cookies are a login to the person's HoYoLAB account, so they are encrypted in the file, with a key kept apart
from the data folder: opening the file, a backup or a copy of the data folder shows only gibberish. (Whoever runs the
server can still reach what the bot itself can read; this keeps them from being seen by accident.) /hoyolab unlink
deletes them. If the key is lost, the links can't be read and people link again.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

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


def _private_write(path: Path, data: bytes) -> None:
    """Writes a file only the bot's own user can read, replacing it in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # private before anything is written
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def load_key(key_file: str | Path, env_key: str | None = None) -> bytes:
    """The encryption key: HOYOLAB_LINKS_KEY if set, else the key file, made on first use."""
    if env_key:
        return env_key.strip().encode()
    path = Path(key_file)
    try:
        return path.read_bytes().strip()
    except FileNotFoundError:
        key = Fernet.generate_key()
        _private_write(path, key)
        log.info("Made a new key for HoYoLAB links at %s", path)
        return key


class LinkStore:
    """Discord user id -> {"cookies": ..., "uids": {game: [uid, ...]}}, saved to a JSON file with the cookies encrypted."""

    def __init__(self, path: str | Path, key: bytes):
        self.path = Path(path)
        self._fernet = Fernet(key)
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
        if not isinstance(data, dict):
            return
        plain = False
        for user, entry in data.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("cookies"):  # saved before encryption was added: encrypted on the save below
                cookies, plain = entry["cookies"], True
            else:
                try:
                    cookies = self._fernet.decrypt(str(entry.get("encrypted", "")).encode()).decode()
                except InvalidToken:
                    log.warning("Can't read the HoYoLAB link of %s (different key?); they need to link again", user)
                    continue
            self._links[str(user)] = {"cookies": cookies, "uids": entry.get("uids", {})}
        if plain:
            self._save()

    def _save(self) -> None:
        stored = {
            user: {"encrypted": self._fernet.encrypt(entry["cookies"].encode()).decode(), "uids": entry["uids"]}
            for user, entry in self._links.items()
        }
        _private_write(self.path, json.dumps(stored, indent=1, sort_keys=True).encode())

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
