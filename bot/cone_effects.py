"""What a Star Rail light cone's passive gives its wearer in combat, read from the passive's own text.

The game data has each passive as a sentence with numbered blanks ("... CRIT DMG increases by #1[i]%, stacking up to
#2[i] time(s)") and the numbers per superimposition. The stats a passive always gives are already in the light cone's
properties; this reads the rest (the parts that need a trigger) and counts them the way /hsr-optimize counts set
effects: active, at full stacks. Effects on DMG of one kind (Ultimate, follow-up attacks, ...) count as DMG Boost.

Keys are the ones bot/optimize.py's bonus uses, plus "Vulnerability" (the enemy takes more DMG: its own multiplier)
and "BreakDMG" (more Break DMG, which only counts for characters who build Break Effect).
"""

from __future__ import annotations

import re

from .assets import Assets

BLANK = r"#(\d)\[[^\]]*\]"
# What a clause is about. The mention nearest to the number names the stat; None is something the index doesn't use.
STATS: list[tuple[str, str | None]] = [
    (r"Outgoing Healing|Incoming Healing|Energy Regeneration|Effect RES|Effect Hit Rate|All-Type RES|Shield"
     r"|Weakness Break Efficiency|DMG taken (?:by the wearer )?(?:is )?(?:reduced|decreases)|less DMG"
     r"|DMG dealt to (?:all )?all(?:y|ies)|SPD (?:is )?(?:lowered|reduced|decreased|decreases)|restores? HP|Additional DMG"
     r"|DMG they receive decreases", None),
    (r"ignor\w*|DEF (?:is |are )?(?:decrease[sd]?|reduced|lowered)|(?:decreases|reduces) [^.,]*DEF", "DefIgnore"),
    (r"DMG (?:taken|received)|DMG they receive|\b(?:take|receive)s?\b|Vulnerab", "Vulnerability"),
    (r"CRIT DMG", "CriticalDamageBase"),
    (r"CRIT Rate", "CriticalChanceBase"),
    (r"Break Effect", "BreakDamageAddedRatioBase"),
    (r"Elation", "ElationDamageAddedRatioBase"),
    (r"\bSPD\b", "SpeedAddedRatio"),
    (r"DMG|\bDoT\b", "DMG"),
    (r"(?<!Basic )(?<!Follow-Up )(?<!Follow-up )\bATK\b", "AttackAddedRatio"),
    (r"\bHP\b", "HPAddedRatio"),
    (r"\bDEF\b", "DefenceAddedRatio"),
]
GAIN = re.compile(rf"\b(by|extra|additional|deals?|ignores?|takes?|receives?)(?: an| a)?(?: extra| additional)? {BLANK}%")
COUNT = rf"(?:{BLANK}|(\d+))"
STACKS = re.compile(rf"(?:up to|max(?:imum)? of|can stack|max) (?:a max(?:imum)? of )?{COUNT} (?:time|stack|points? of Energy|Energy)"
                    rf"|{COUNT} stacks? max", re.I)
OTHERS = re.compile(r"except the wearer|excluding the wearer|wearer's teammates", re.I)


def _stat(text: str) -> str | None:
    found, at = None, -1
    for pattern, key in STATS:
        for match in re.finditer(pattern, text):
            if match.end() > at:
                found, at = key, match.end()
    return found


def _times(match: re.Match | None, params: list[float]) -> tuple[float, int | None]:
    """How often a stacking effect counts, and which blank holds that count."""
    if not match:
        return 1.0, None
    blank = match.group(1) or match.group(3)
    if blank:
        index = int(blank) - 1
        return (params[index] if index < len(params) else 1.0), index
    return float(match.group(2) or match.group(4)), None


def parse(desc: str, params: list[float], always: dict[str, float] | None = None) -> dict[str, float]:
    """The combat effects in one passive text, with these numbers filled in, without what the properties already give."""
    total: dict[str, float] = {}
    sentences = re.split(r"(?<=[.!])\s+", desc)
    anywhere = STACKS.search(desc)
    for n, sentence in enumerate(sentences):
        if OTHERS.search(sentence):
            continue  # a buff for somebody else
        stacks = STACKS.search(sentence)
        for later in sentences[n + 1:n + 3]:  # "... by #1%. (At the same time, ... by #2%.) This effect can stack up to #3 times."
            if not stacks and re.match(r"This effect|The effect|Up to", later):
                stacks = STACKS.search(later)
            if not later.startswith("At the same time"):
                break
        if not stacks and re.search(r"(?:each|every|per) (?:\S+ )?(?:stack|point)|stack of [^,.]* (?:increases|enables)", sentence, re.I):
            stacks = anywhere  # "Each stack of X increases ...", with the limit named in another sentence
        times, count_at = _times(stacks, params)
        # A sentence can carry several effects ("ATK by #1 and CRIT DMG by #2"): each number belongs to the words before it.
        start = 0
        for gain in GAIN.finditer(sentence):
            clause, after = sentence[start:gain.end()], sentence[gain.end():gain.end() + 45]
            start = gain.end()
            index = int(gain.group(2)) - 1
            verb = gain.group(1)
            if index >= len(params) or index == count_at:
                continue
            if after.startswith(" of") and not verb.startswith("ignore"):
                continue  # "equal to #2% of their ATK": an amount, not a bonus
            if verb.startswith("deal"):  # "deals #1% more CRIT DMG": the stat comes after the number
                clause = after.split(" to ")[0].split(",")[0]
            clause = re.sub(r"(?:current )?HP percentage", "", clause)  # a condition on the enemy, not the wearer's HP
            key = _stat(clause)
            if verb.startswith(("take", "receive")):  # "enemies take #2% increased DMG"
                key = "Vulnerability" if re.match(r" (?:increased|more)", after) else None
            if key and "Break DMG" in clause + after.split(",")[0]:  # only for characters who deal Break DMG
                key = {"DMG": "BreakDMG", "Vulnerability": "BreakDMG", "DefIgnore": "BreakDefIgnore"}.get(key, key)
            if key:
                total[key] = total.get(key, 0.0) + params[index] * times
    for key, value in (always or {}).items():  # already counted with the light cone's own stats
        if key in total:
            total[key] = round(total[key] - value, 6)
    return {k: round(v, 6) for k, v in total.items() if v > 1e-6}


# Passives whose size depends on the wearer's own stats in a way the text reader can't follow: counted at their cap.
CAPPED = {"21039": lambda p: {"DMG": p[3]}}


def effect(assets: Assets, equipment: dict | None) -> dict[str, float]:
    """The passive's combat effects of a worn light cone (a showcase "equipment" entry)."""
    if not equipment:
        return {}
    entry = assets.data.get("hsr_lc_ranks", {}).get(str(equipment.get("tid")))
    if not entry:
        return {}
    rank = min(max(int(equipment.get("rank") or 1), 1), len(entry.get("params") or [1])) - 1
    try:
        params = [float(p) for p in entry["params"][rank]]
        always: dict[str, float] = {}
        for prop in (entry.get("properties") or [])[rank] if entry.get("properties") else []:
            always[prop["type"]] = always.get(prop["type"], 0.0) + float(prop["value"])
        if str(equipment.get("tid")) in CAPPED:
            return CAPPED[str(equipment.get("tid"))](params)
        return parse(entry.get("desc", ""), params, always)
    except (KeyError, IndexError, TypeError, ValueError):
        return {}
