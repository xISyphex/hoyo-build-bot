"""Every reviewed definition, found by importing the modules under bot/calc/defs/.

Each module defines DEFINITION (one CharacterDef / LightConeDef / SetDef) or DEFINITIONS (a list of them). Adding a
file is all it takes to register one; see bot/calc/PORTING.md.
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache

from .model import CharacterDef, LightConeDef, SetDef


def _load(package: str, kind: type) -> dict:
    pkg = importlib.import_module(package)
    found: dict = {}
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        defs = getattr(module, "DEFINITIONS", None) or [getattr(module, "DEFINITION", None)]
        for d in defs:
            if d is None:
                continue
            if not isinstance(d, kind):
                raise TypeError(f"{module.__name__}: expected {kind.__name__}, got {type(d).__name__}")
            if d.id in found:
                raise ValueError(f"{module.__name__}: {kind.__name__} {d.id} is defined twice")
            found[d.id] = d
    return found


@lru_cache(maxsize=1)
def characters() -> dict[str, CharacterDef]:
    return _load("bot.calc.defs.characters", CharacterDef)


@lru_cache(maxsize=1)
def light_cones() -> dict[str, LightConeDef]:
    return _load("bot.calc.defs.lightcones", LightConeDef)


@lru_cache(maxsize=1)
def sets() -> dict[str, SetDef]:
    return _load("bot.calc.defs.sets", SetDef)
