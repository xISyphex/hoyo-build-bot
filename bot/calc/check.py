"""Review helper for definitions: python -m bot.calc.check <id> [--lc <light cone id>] [--eidolon N] [--teammate]

<id> is a character id (1102), a light cone id (23001) or a set id (115). For a character it prints the resolved
abilities (multipliers at the default ability levels), every effect with its value, the rotation damage of a
reference build (no relics, the given light cone) and the eidolon texts next to the eidolon effects of the
definition, so the literal eidolon numbers can be compared with the game text. With --teammate the effects are
resolved as a teammate of Seele, to see what the character gives the team. Reads the game data from $CACHE_DIR
(default ./data); nothing is downloaded.
"""

from __future__ import annotations

import argparse
import os
import sys

from ..assets import Assets
from . import api, registry
from .engine import CalcError
from .gamedata import GameData


def _fmt(v) -> str:
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def check_character(assets, gd: GameData, cid: str, lc: str | None, eidolon: int, teammate: bool) -> None:
    if teammate:
        req = {"character": {"id": "1102"}, "teammates": [{"id": cid, "eidolon": eidolon}]}
    else:
        req = {"character": {"id": cid, "eidolon": eidolon, **({"light_cone": {"id": lc}} if lc else {})}}
    ev = api.evaluate(assets, req, [])
    main = ev.character
    print(f"{gd.name(cid)} ({cid}) as {'a teammate of Seele' if teammate else 'the main character'}, E{eidolon}")
    print(f"definition: {main.get('definition')}  reviewed: {main.get('reviewed')}  approximate: {ev.approximate}")
    print("\nabilities (per use):")
    for ab in ev.abilities:
        print(f"  {ab['key']:<12} {ab['per_use']:>12.1f} x {ab['uses']:.2f} = {ab['total']:.1f}")
        for h in ab["hits"]:
            mult = " ".join(f"{k}={_fmt(v)}" for k, v in h.get("multipliers", {}).items())
            print(f"      {h.get('label', '')} [{h.get('func')}] {_fmt(h['damage'])}  base={_fmt(h.get('base', 0.0))}  {mult}")
    print("\neffects:")
    for e in ev.effects:
        flag = "" if e["active"] else "  (inactive)"
        print(f"  {e['owner']:<28} {e['source']:<22} {e['stat']:<10} {_fmt(e['value']):>8} -> {e['target']}"
              f" {','.join(e['tags'])}{' ' + e['element'] if e['element'] else ''}{flag}")
    print(f"\ntotal {ev.total:.1f} ({ev.unit}), repetitions {ev.repetitions:.2f}")
    print("stats:", {k: round(v, 4) for k, v in ev.stats.items() if v})
    if ev.notes:
        print("\nnotes:")
        for n in ev.notes:
            print("  -", n)
    print("\neidolons (game text; compare with the E<n> effects above):")
    for n in range(1, 7):
        print(f"  E{n}: {gd.eidolon_text(cid, n)}")


def check_cone(gd: GameData, lid: str) -> None:
    cone = registry.light_cones().get(lid)
    print(f"{gd.cone_name(lid)} ({lid}), {gd.cone_path(lid)}; reviewed definition: {cone is not None}")
    for rank in range(1, 6):
        print(f"  S{rank} params: {gd.cone_params(lid, rank)}  plain stats: {gd.cone_props(lid, rank)}")
    if cone:
        for e in cone.effects:
            print(f"  effect {e.stat} {e.value!r} -> {e.target} when {e.when!r}")


def check_set(gd: GameData, sid: str) -> None:
    sdef = registry.sets().get(sid)
    print(f"{gd.set_name(sid)} ({sid}); reviewed definition: {sdef is not None}")
    for n in (2, 4):
        print(f"  {n}pc text: {gd.set_text(sid, n)}  plain stats: {gd.set_props(sid, n)}")
    if sdef:
        for n, effs in sdef.pieces.items():
            for e in effs:
                print(f"  {n}pc effect {e.stat} {e.value!r} -> {e.target} when {e.when!r}")
        for e in sdef.team:
            print(f"  team effect {e.stat} {e.value!r} -> {e.target} when {e.when!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bot.calc.check", description=__doc__.splitlines()[0])
    ap.add_argument("id")
    ap.add_argument("--lc")
    ap.add_argument("--eidolon", type=int, default=0)
    ap.add_argument("--teammate", action="store_true")
    args = ap.parse_args(argv)
    assets = Assets(os.environ.get("CACHE_DIR", "data"))
    assets.load()
    gd = GameData(assets)
    try:
        if gd.exists(args.id):
            check_character(assets, gd, args.id, args.lc, args.eidolon, args.teammate)
        elif gd.cone_exists(args.id):
            check_cone(gd, args.id)
        elif gd.set_exists(args.id):
            check_set(gd, args.id)
        else:
            print(f"unknown id {args.id}", file=sys.stderr)
            return 2
    except CalcError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
