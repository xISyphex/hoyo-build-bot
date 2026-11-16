"""Star Rail damage engine and relic optimizer (see bot/calc/PORTING.md and the docstrings of api.py and engine.py).

Public API:

    from bot.calc import evaluate, optimize, EvaluateRequest, Relic, parse_kelz

    evaluate(assets, request, relics) -> Evaluation
    optimize(assets, request, inventory) -> OptimizeResult
"""

from .api import (Alternative, CharacterRequest, ConeRequest, EnemyOptions, EvaluateRequest, Evaluation,
                  OptimizeResult, TeammateRequest, evaluate, optimize, toggle_listing, toggle_specs)
from .engine import CalcError
from .relics import KelzExport, Relic, character_request, parse_kelz

__all__ = ["Alternative", "CalcError", "CharacterRequest", "ConeRequest", "EnemyOptions", "EvaluateRequest",
           "Evaluation", "KelzExport", "OptimizeResult", "Relic", "TeammateRequest", "character_request", "evaluate",
           "optimize", "parse_kelz", "toggle_listing", "toggle_specs"]
