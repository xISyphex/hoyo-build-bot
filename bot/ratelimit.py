"""How many lookups each person may run per hour (a sliding window, kept in memory)."""

from __future__ import annotations

import time
from collections import deque


class LookupLimit:
    def __init__(self, per_hour: int, window: float = 3600.0):
        self.per_hour = per_hour
        self.window = window
        self._calls: dict[int, deque[float]] = {}

    def take(self, user_id: int, now: float | None = None) -> float | None:
        """Count one lookup. Returns None if allowed, else the time when the next one is."""
        now = time.time() if now is None else now
        calls = self._calls.setdefault(user_id, deque())
        while calls and calls[0] <= now - self.window:
            calls.popleft()
        if len(calls) >= self.per_hour:
            return calls[0] + self.window
        calls.append(now)
        return None
