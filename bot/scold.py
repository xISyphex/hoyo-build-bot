"""/scold: Fairy scolds someone for every Star Rail character on the owner's MVP list (/hsr-mvp) their account lacks.

The owner picks who may ask for a scolding with /scold-enable, each with their own scold text. Both the enabled
people and the MVP list (Star Rail character IDs) are saved to a small JSON file."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("hoyo-bot")

MENTION = re.compile(r"<@!?(\d{15,25})>|\b(\d{15,25})\b")
DEFAULT_TEXT = "Proxy, Fairy is very disappointed in you"
NOT_ENABLED = "Fairy doesn't take orders from you."


def parse_users(text: str | None) -> list[int]:
    """The Discord users named in a text option: mentions (<@id>, <@!id>) and raw IDs, in order, without repeats."""
    found = []
    for match in MENTION.finditer(text or ""):
        uid = int(match[1] or match[2])
        if uid not in found:
            found.append(uid)
    return found


def join_names(names: list[str]) -> str:
    """"A", "A and B", "A, B and C"."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def name_ids(characters: dict) -> dict[str, list[str]]:
    """Each Star Rail character name and its IDs (March 7th and the Trailblazer have one per Path), from the game
    data's character table, given as {id: name}."""
    ids: dict[str, list[str]] = {}
    for cid, name in characters.items():
        if name and "{" not in name:
            ids.setdefault(name, []).append(str(cid))
    return ids


def missing(mvp: list[str], owned: set[str], names: dict[str, str]) -> list[str]:
    """The MVP characters' names (in list order) that the account has none of. IDs that share a name (March 7th's
    Paths) count as one character, owned when any of them is; IDs the game data doesn't know keep their ID as name."""
    owned = {str(o).split("-")[0] for o in owned}
    groups: dict[str, list[str]] = {}
    for cid in mvp:
        groups.setdefault(names.get(str(cid), str(cid)), []).append(str(cid))
    return [name for name, ids in groups.items() if not owned.intersection(ids)]


def scold_text(target_id: int, text: str, lacking: list[str], showcase: bool = False) -> str:
    """The public message: the tag, the saved text, then what they didn't pull."""
    text = " ".join((text or DEFAULT_TEXT).split()).rstrip(" .") or DEFAULT_TEXT
    line = f"<@{target_id}> {text} for not pulling **{join_names(lacking)}**."
    if showcase:
        line += ("\n-# Fairy could only check their in-game showcase. `/hoyolab link` lets her see every character,"
                 " so some of these may be hiding off the showcase.")
    return line


def nothing_text(target_id: int, showcase: bool = False) -> str:
    line = f"<@{target_id}> has every character on the MVP list. Fairy finds nothing to scold... this time."
    if showcase:
        line += "\n-# Fairy checked their in-game showcase only."
    return line


class ScoldStore:
    """Who may use /scold (Discord user id -> their scold text) and the MVP list (Star Rail character IDs)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.enabled: dict[str, str] = {}
        self.mvp: list[str] = []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            log.exception("Could not read %s; starting with nobody enabled to scold", self.path)
            self.path.replace(self.path.with_suffix(".broken.json"))
            return
        if isinstance(data, dict):
            enabled = data.get("enabled")
            if isinstance(enabled, dict):
                self.enabled = {str(u): str(t) for u, t in enabled.items() if str(u).isdigit()}
            if isinstance(data.get("mvp"), list):
                self.mvp = [str(c) for c in data["mvp"]]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"enabled": self.enabled, "mvp": self.mvp}, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic, so a crash never leaves half a file

    def text(self, user_id: int) -> str | None:
        """The user's scold text, or None when they aren't enabled."""
        return self.enabled.get(str(user_id))

    def enable(self, user_ids: list[int], text: str) -> None:
        """Let these users scold, with this text (replacing any they had)."""
        for uid in user_ids:
            self.enabled[str(uid)] = text
        self._save()

    def disable(self, user_ids: list[int]) -> list[int]:
        """Stop these users from scolding. Returns the ones who were enabled."""
        removed = [uid for uid in user_ids if self.enabled.pop(str(uid), None) is not None]
        if removed:
            self._save()
        return removed

    def set_mvp(self, ids: list[str]) -> None:
        self.mvp = list(dict.fromkeys(str(i) for i in ids))
        self._save()
