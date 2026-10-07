"""Claimed UIDs: one UID per Discord user per game, saved to a small JSON file."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("hoyo-bot")


class ClaimStore:
    """Maps (Discord user id, game) to a UID. A new claim replaces the old one."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._claims: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            # Keep the broken file for inspection instead of silently overwriting it.
            log.exception("Could not read %s; starting with no claims", self.path)
            self.path.replace(self.path.with_suffix(".broken.json"))
            return
        if isinstance(data, dict):
            self._claims = {
                str(user): {str(g): str(u) for g, u in games.items()}
                for user, games in data.items()
                if isinstance(games, dict)
            }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._claims, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic, so a crash never leaves half a file

    def get(self, user_id: int, game: str) -> str | None:
        return self._claims.get(str(user_id), {}).get(game)

    def set(self, user_id: int, game: str, uid: str) -> str | None:
        """Claim uid for this user and game. Returns the UID it replaced, if any."""
        games = self._claims.setdefault(str(user_id), {})
        previous = games.get(game)
        games[game] = uid
        self._save()
        return previous
