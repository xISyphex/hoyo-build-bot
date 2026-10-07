"""Forgiving character-name matching ("raiden", "hu tao", "zhuyuan", "Ayaka")."""

from __future__ import annotations

import difflib
import re

# Nicknames people commonly type.
ALIASES = {
    "raiden": "Raiden Shogun",
    "ei": "Raiden Shogun",
    "ayaka": "Kamisato Ayaka",
    "ayato": "Kamisato Ayato",
    "kazuha": "Kaedehara Kazuha",
    "kokomi": "Sangonomiya Kokomi",
    "itto": "Arataki Itto",
    "sara": "Kujou Sara",
    "heizou": "Shikanoin Heizou",
    "childe": "Tartaglia",
    "march": "March 7th",
    "m7": "March 7th",
    "dhil": "Dan Heng • Imbibitor Lunae",
    "il": "Dan Heng • Imbibitor Lunae",
    "tb": "Trailblazer",
    "mc": "Trailblazer",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find(query: str, names: list[str]) -> str | None:
    """Best match for query among names, or None."""
    if not names:
        return None
    q = _norm(query)
    alias = ALIASES.get(q)
    if alias and alias in names:
        return alias
    by_norm = {_norm(n): n for n in names}
    if q in by_norm:
        return by_norm[q]
    starts = [n for k, n in by_norm.items() if k.startswith(q) or any(_norm(w).startswith(q) for w in n.split())]
    if len(starts) >= 1 and q:
        return min(starts, key=len)
    contains = [n for k, n in by_norm.items() if q and q in k]
    if contains:
        return min(contains, key=len)
    # Typos: compare against full names and against each word ("ayaak" -> Ayaka).
    candidates = dict(by_norm)
    for name in names:
        for word in name.split():
            candidates.setdefault(_norm(word), name)
    close = difflib.get_close_matches(q, list(candidates), n=1, cutoff=0.6)
    return candidates[close[0]] if close else None


def suggest(query: str, names: list[str], limit: int = 25) -> list[str]:
    """Autocomplete suggestions, best first."""
    q = _norm(query)
    if not q:
        return names[:limit]
    scored = []
    for name in names:
        n = _norm(name)
        if n.startswith(q):
            score = 0
        elif any(_norm(w).startswith(q) for w in name.split()):
            score = 1
        elif q in n:
            score = 2
        else:
            ratio = difflib.SequenceMatcher(None, q, n).ratio()
            if ratio < 0.5:
                continue
            score = 3 - ratio
        scored.append((score, name))
    return [name for _, name in sorted(scored)][:limit]
