"""Who may use the bot: its owner plus the Discord users the owner added with /access add."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("hoyo-bot")

PRIVATE = "This bot is private. Ask its owner to add you with `/access add`."


class AccessList:
    """Discord user ids allowed to use the bot, saved to a small JSON file.

    The owners (the bot application's owner, or its team) are always allowed and
    are the only ones who can change the list.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.owners: set[int] = set()
        self.users: dict[int, str] = {}  # id -> name when added, so the list is readable
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            # Keep the broken file for inspection; with an empty list only the owner gets in.
            log.exception("Could not read %s; only the owner can use the bot", self.path)
            self.path.replace(self.path.with_suffix(".broken.json"))
            return
        if isinstance(data, dict):
            self.users = {int(k): str(v) for k, v in data.get("users", {}).items() if str(k).isdigit()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        users = {str(k): v for k, v in sorted(self.users.items())}
        tmp.write_text(json.dumps({"users": users}, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic, so a crash never leaves half a file

    def is_owner(self, user_id: int) -> bool:
        return user_id in self.owners

    def allowed(self, user_id: int) -> bool:
        return user_id in self.owners or user_id in self.users

    def add(self, user_id: int, name: str) -> bool:
        """Allow a user. Returns False if they were already on the list."""
        new = user_id not in self.users
        self.users[user_id] = name
        self._save()
        return new

    def remove(self, user_id: int) -> bool:
        """Take a user off the list. Returns False if they weren't on it."""
        if self.users.pop(user_id, None) is None:
            return False
        self._save()
        return True
