"""Optimizer sessions: the link /hsr-optimize hands out, tied to one Discord user, kept in memory.

A session holds the player's characters as the command gathered them (the showcase from Enka, every character from a
linked HoYoLAB account), so the page works on the same relics the command would. Tokens are random, live 2 hours, and
each user has one live session: a new command replaces the old link. Only a hash of each token is used to find its
session, and the token itself is then compared in constant time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from ..models import CharacterBuild

TTL = 2 * 3600
OPTIMIZE_LIMIT = 20  # optimize runs per session ...
OPTIMIZE_WINDOW = 600.0  # ... in this many seconds


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", "replace")).hexdigest()


@dataclass(eq=False)
class Session:
    token: str = field(repr=False)
    user_id: int
    uid: str
    builds: list[CharacterBuild] = field(repr=False)
    created: float
    expires: float
    preselect: dict = field(default_factory=dict)
    busy: bool = False  # an optimize is running
    calls: deque = field(default_factory=deque, repr=False)  # when optimize ran, for the rate limit
    cache: dict = field(default_factory=dict, repr=False)  # the serialized inventory (bot/web/inventory.py)

    def take_call(self, now: float, limit: int = OPTIMIZE_LIMIT, window: float = OPTIMIZE_WINDOW) -> float | None:
        """Counts one optimize run. Returns None when allowed, else how many seconds until the next one is."""
        while self.calls and self.calls[0] <= now - window:
            self.calls.popleft()
        if len(self.calls) >= limit:
            return self.calls[0] + window - now
        self.calls.append(now)
        return None


class SessionStore:
    def __init__(self, ttl: float = TTL, clock=time.time):
        self.ttl = ttl
        self.clock = clock
        self._by_digest: dict[str, Session] = {}
        self._by_user: dict[int, str] = {}  # user id -> their session's token digest

    def __len__(self) -> int:
        self.purge()
        return len(self._by_digest)

    def create(self, user_id: int, uid: str, builds: list[CharacterBuild], preselect: dict | None = None) -> Session:
        """A new session for the user, replacing the one they had."""
        self.purge()
        old = self._by_user.pop(user_id, None)
        if old:
            self._by_digest.pop(old, None)
        token = secrets.token_urlsafe(32)
        now = self.clock()
        session = Session(token, user_id, uid, list(builds), now, now + self.ttl, dict(preselect or {}))
        digest = _digest(token)
        self._by_digest[digest] = session
        self._by_user[user_id] = digest
        return session

    def get(self, token: str | None) -> Session | None:
        """The live session of this token, or None (unknown, replaced or expired)."""
        if not token or len(token) > 128:
            return None
        digest = _digest(token)
        session = self._by_digest.get(digest)
        if session is None or not hmac.compare_digest(session.token.encode(), token.encode("utf-8", "replace")):
            return None
        if self.clock() >= session.expires:
            self._drop(digest)
            return None
        return session

    def for_user(self, user_id: int) -> Session | None:
        digest = self._by_user.get(user_id)
        session = self._by_digest.get(digest) if digest else None
        return self.get(session.token) if session else None

    def purge(self) -> None:
        now = self.clock()
        for digest in [d for d, s in self._by_digest.items() if now >= s.expires]:
            self._drop(digest)

    def _drop(self, digest: str) -> None:
        session = self._by_digest.pop(digest, None)
        if session and self._by_user.get(session.user_id) == digest:
            del self._by_user[session.user_id]
