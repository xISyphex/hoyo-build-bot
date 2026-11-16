"""The relic search: the best six relics out of an inventory (spec section 5).

1. Filter: the slots' allowed main stats, the set constraint, the relics of excluded characters.
2. Prune each slot: drop relics another relic of the same set group beats or ties on every stat that can matter
   (exact), then keep the top K by a linear score (the gradient of the damage at a reference build), plus the best
   relic for each relevant stat (so stat thresholds the gradient can't see, like 75% Effect Hit Rate, stay
   reachable). In "any set" modes the top relics of the sets whose bonus is worth most are kept too.
3. Enumerate every valid (Head, Hands, Body, Feet) quadruple and (Sphere, Rope) pair and evaluate quadruples x pairs
   in chunks with the vectorised engine. If that is more than MAX_COMBOS, quadruples and pairs are first ranked
   against the best partner found so far and cut.
4. Repeat 2-3 once with the gradient taken at the best build found, which catches the curvature of crit and caps.

The relics the character wears now are always evaluated too, so the answer is never worse than them.
"""

from __future__ import annotations

import itertools
import time
from collections import defaultdict

import numpy as np

from .api import Alternative, EvaluateRequest, OptimizeResult, _evaluation
from .engine import CalcError
from .model import BASIC_STATS
from .prepare import prepare
from .relics import SLOTS, Relic

TOP_K = 10  # relics kept per slot (and per set group when the set is required) by the linear score
FREE_SETS = 3  # "any set": sets whose own top relics are kept too
FREE_K = 4  # relics kept per slot of each of those sets
PLANAR_K = 3  # relics kept per planar slot and planar set (2pc bonuses need both pieces of one set)
MAX_COMBOS = 3_000_000
CHUNK = 150_000
STEP = {"hp": 40.0, "atk": 20.0, "def": 20.0, "spd": 10.0, "hp%": 0.04, "atk%": 0.04, "def%": 0.05, "cr": 0.03,
        "cd": 0.06, "ehr": 0.04, "res": 0.04, "be": 0.06, "err": 0.04, "ohb": 0.04, "elation": 0.04}


def _constraint(req: EvaluateRequest):
    """(mode, sets): ("any", ()), ("4", (A,)), ("22", (A, B)), ("2", (A,))."""
    rs = [str(s) for s in req.relic_sets]
    if not rs:
        return "any", ()
    if len(rs) == 1 or (len(rs) == 2 and rs[0] == rs[1]):
        return "4", (rs[0],)
    if "*" in rs:
        a = next(s for s in rs if s != "*")
        return "2", (a,)
    return "22", (rs[0], rs[1])


def _valid_counts(mode, sets, counts: dict) -> bool:
    if mode == "4":
        return counts.get(sets[0], 0) >= 4
    if mode == "22":
        return counts.get(sets[0], 0) >= 2 and counts.get(sets[1], 0) >= 2
    if mode == "2":
        return counts.get(sets[0], 0) >= 2
    return True


def search(assets, req: EvaluateRequest, inventory: list[Relic], progress=None) -> OptimizeResult:
    """progress(fraction 0..1), when given, is called between chunks; an exception it raises ends the search."""
    t0 = time.perf_counter()
    report = progress or (lambda fraction: None)
    report(0.0)
    main_id = str(req.character.id)
    mode, csets = _constraint(req)
    for s in csets:
        if int(s) >= 300:
            raise CalcError(f"{s} is a planar set; put it in planar_sets")
    planar_ok = {str(s) for s in req.planar_sets}
    for s in planar_ok:
        if int(s) < 300:
            raise CalcError(f"{s} is not a planar set")
    excluded = {str(x) for x in req.excluded_owners} - {main_id}

    seen: set[str] = set()
    pool: dict[str, list[Relic]] = {s: [] for s in SLOTS}
    for r in inventory:
        if r.uid in seen:
            raise CalcError(f"relic {r.uid} is listed twice")
        seen.add(r.uid)
        if r.location and r.location in excluded:
            continue
        allowed = req.main_stats.get(r.slot)
        if allowed and r.main not in allowed:
            continue
        if r.slot in SLOTS[4:]:
            if planar_ok and r.set_id not in planar_ok:
                continue
        elif mode in ("4", "22") and r.set_id not in csets:
            continue
        pool[r.slot].append(r)
    missing = [s for s in SLOTS if not pool[s]]
    if missing:
        raise CalcError("no relic fits these slots: " + ", ".join(missing))

    set_ids = {r.set_id for rs in pool.values() for r in rs}
    prep = prepare(assets, req, set_ids)
    notes = []
    keys = sorted({k for rs in pool.values() for r in rs for k in r.stats()} & set(BASIC_STATS))
    relevant = [k for k in keys if k in prep.relevant]
    vec = {s: np.array([[r.stats().get(k, 0.0) for k in keys] for r in pool[s]], dtype=float) for s in SLOTS}
    rel_idx = [keys.index(k) for k in relevant]

    def score_rows(stat_rows: np.ndarray, count_rows: dict) -> np.ndarray:
        relic = {k: stat_rows[:, i] for i, k in enumerate(keys)}
        total, stats = prep.score(relic, count_rows, stat_rows.shape[0])
        if req.min_stats:
            ok = np.ones(stat_rows.shape[0], dtype=bool)
            for k, floor in req.min_stats.items():
                ok &= np.broadcast_to(np.asarray(stats[k]), ok.shape) >= floor - 1e-9
            total = np.where(ok, total, -np.inf)
        return total

    # reference build: the slots' average relic, with the constraint's sets complete
    ref_counts = _reference_counts(mode, csets, pool)
    ref = sum(vec[s].mean(axis=0) for s in SLOTS)

    def gradient(at: np.ndarray, counts: dict) -> np.ndarray:
        g = np.zeros(len(keys))
        rows = [at]
        for i in rel_idx:
            d = STEP.get(keys[i], 0.04)
            up, down = at.copy(), at.copy()
            up[i] += d
            down[i] = max(0.0, down[i] - d)
            rows += [up, down]
        cnt = {k: np.full(len(rows), v) for k, v in counts.items()}
        vals = score_rows(np.array(rows), cnt)
        for j, i in enumerate(rel_idx):
            span = rows[1 + 2 * j][i] - rows[2 + 2 * j][i]
            g[i] = (vals[1 + 2 * j] - vals[2 + 2 * j]) / span if span else 0.0
        return np.where(np.isfinite(g), g, 0.0)

    best_sets = _valuable_sets(prep, score_rows, ref, keys, pool, mode) if mode in ("any", "2") else []
    best: list[tuple[float, tuple]] = []
    combos_done = 0
    kept_total = 0
    g = gradient(ref, ref_counts)
    tried_candidates: set = set()
    for _round in range(2):
        report(_round / 2)
        cand = {s: _prune(pool[s], vec[s], g, rel_idx, mode, csets, best_sets) for s in SLOTS}
        key = tuple(tuple(c) for c in cand.values())
        if key in tried_candidates:
            break
        tried_candidates.add(key)
        kept_total = max(kept_total, sum(len(c) for c in cand.values()))
        found, n = _enumerate(cand, vec, pool, keys, mode, csets, score_rows, req.top_n,
                              lambda f, r=_round: report((r + f) / 2))
        combos_done += n
        best = _merge(best, found, req.top_n)
        if not best:
            break
        top = best[0][1]
        at = sum(vec[s][i] for s, i in zip(SLOTS, top))
        g = gradient(at, _counts_of([pool[s][i] for s, i in zip(SLOTS, top)]))

    # what the character wears now
    worn = [next((r for r in inventory if r.location == main_id and r.slot == s), None) for s in SLOTS]
    current = None
    if all(worn):
        cur_eval = _evaluation(prepare(assets, req, {r.set_id for r in worn} | set_ids), req, worn)
        current = cur_eval
        cur_counts = _counts_of(worn)
        fits = _valid_counts(mode, csets, cur_counts) and (not planar_ok or all(r.set_id in planar_ok for r in worn[4:]))
        fits = fits and all(not req.main_stats.get(r.slot) or r.main in req.main_stats[r.slot] for r in worn)
        if fits and all(r in pool[r.slot] for r in worn):
            idx = tuple(pool[s].index(r) for s, r in zip(SLOTS, worn))
            stats = np.array([sum(vec[s][i] for s, i in zip(SLOTS, idx))])
            val = score_rows(stats, {k: np.array([v]) for k, v in cur_counts.items()})[0]
            best = _merge(best, [(float(val), idx)], req.top_n)
    report(1.0)
    best = [b for b in best if np.isfinite(b[0])]
    if not best:
        return OptimizeResult(best=None, alternatives=[], current=current, candidates=kept_total,
                              combinations=combos_done, elapsed_ms=(time.perf_counter() - t0) * 1000,
                              notes=notes + ["No combination meets the set constraint and stat minimums."])
    picks = [[pool[s][i] for s, i in zip(SLOTS, idx)] for _, idx in best]
    top_eval = _evaluation(prep, req, picks[0])
    alts = [Alternative(total=float(v), relics=[r.uid for r in p], sets=_counts_of(p)) for (v, _), p in zip(best, picks)]
    return OptimizeResult(best=top_eval, alternatives=alts, current=current, candidates=kept_total,
                          combinations=combos_done, elapsed_ms=(time.perf_counter() - t0) * 1000, notes=notes)


def _counts_of(relics) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in relics:
        out[r.set_id] += 1
    return dict(out)


def _reference_counts(mode, csets, pool) -> dict:
    if mode == "4":
        c = {csets[0]: 4}
    elif mode == "22":
        c = {csets[0]: 2, csets[1]: 2}
    elif mode == "2":
        c = {csets[0]: 2}
    else:
        c = {}
    planars = defaultdict(int)
    for r in pool["Planar Sphere"] + pool["Link Rope"]:
        planars[r.set_id] += 1
    if planars:
        c[max(planars, key=planars.get)] = 2
    return c


def _valuable_sets(prep, score_rows, ref, keys, pool, mode) -> list[str]:
    """Relic sets whose 4pc (or 2pc) bonus adds most at the reference build, for the "any set" modes."""
    sets = sorted({r.set_id for s in SLOTS[:4] for r in pool[s]}, key=int)
    if not sets:
        return []
    rows = np.repeat(ref[None, :], len(sets) * 2, axis=0)
    cnt = {}
    for i, sid in enumerate(sets):
        cnt.setdefault(sid, np.zeros(len(rows)))
        cnt[sid][2 * i] = 4
        cnt[sid][2 * i + 1] = 2
    vals = score_rows(rows, cnt)
    gain = {sid: max(vals[2 * i], vals[2 * i + 1]) for i, sid in enumerate(sets)}
    return sorted(gain, key=gain.get, reverse=True)[:FREE_SETS]


def _prune(relics: list[Relic], v: np.ndarray, g: np.ndarray, rel_idx, mode, csets, valuable) -> list[int]:
    """Indices of the relics of one slot worth enumerating."""
    if not relics:
        return []
    planar = relics[0].slot in SLOTS[4:]
    groups: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(relics):
        groups[r.set_id].append(i)  # always group by set: set bonuses may depend on it
    lin = v @ g
    keep: set[int] = set()
    for sid, idx in groups.items():
        idx = _undominated(idx, v, rel_idx, lin)
        if planar:
            k = TOP_K if len(groups) <= 2 else PLANAR_K
        elif mode in ("4", "22") or (mode == "2" and sid in csets):
            k = TOP_K
        elif sid in valuable:
            k = FREE_K
        else:
            k = 0
        keep.update(sorted(idx, key=lambda i: -lin[i])[:k])
        groups[sid] = idx
    # overall best regardless of set (the "any" filler pieces), and the best piece for each relevant stat
    everything = [i for idx in groups.values() for i in idx]
    keep.update(sorted(everything, key=lambda i: -lin[i])[:TOP_K])
    for j in rel_idx:
        keep.update(sorted(everything, key=lambda i: (-v[i, j], -lin[i]))[:1])
    return sorted(keep)


def _undominated(idx: list[int], v: np.ndarray, rel_idx, lin) -> list[int]:
    """Drops relics another one of the group beats or ties on every relevant stat (ties keep the better linear score)."""
    if len(idx) <= 1 or not rel_idx:
        return idx[:1] if not rel_idx else idx
    sub = v[np.ix_(idx, rel_idx)]
    order = np.argsort(-lin[idx], kind="stable")
    kept: list[int] = []
    for o in order:
        row = sub[o]
        if kept and np.any(np.all(sub[kept] >= row - 1e-12, axis=1)):
            continue
        kept.append(int(o))
    return [idx[o] for o in kept]


def _enumerate(cand, vec, pool, keys, mode, csets, score_rows, top_n, report=lambda fraction: None):
    """Evaluates quadruples x pairs; returns ([(score, (i_head, ..., i_rope))], combinations evaluated)."""
    quads = []
    q_sets = []
    for combo in itertools.product(*(cand[s] for s in SLOTS[:4])):
        sets = [pool[s][i].set_id for s, i in zip(SLOTS[:4], combo)]
        counts: dict[str, int] = {}
        for sid in sets:
            counts[sid] = counts.get(sid, 0) + 1
        if _valid_counts(mode, csets, counts):
            quads.append(combo)
            q_sets.append(counts)
    pairs = list(itertools.product(cand["Planar Sphere"], cand["Link Rope"]))
    if not quads or not pairs:
        return [], 0
    qv = np.array([sum(vec[s][i] for s, i in zip(SLOTS[:4], q)) for q in quads])
    pv = np.array([vec["Planar Sphere"][a] + vec["Link Rope"][b] for a, b in pairs])
    all_sets = sorted({sid for c in q_sets for sid in c} | {pool[s][i].set_id for s in SLOTS[4:] for i in cand[s]})
    qc = {sid: np.array([c.get(sid, 0) for c in q_sets], dtype=float) for sid in all_sets}
    pc = {sid: np.array([(pool["Planar Sphere"][a].set_id == sid) + (pool["Link Rope"][b].set_id == sid)
                         for a, b in pairs], dtype=float) for sid in all_sets}

    def eval_block(qi: np.ndarray, pi: np.ndarray) -> np.ndarray:
        rows = (qv[qi][:, None, :] + pv[pi][None, :, :]).reshape(-1, qv.shape[1])
        cnt = {sid: (qc[sid][qi][:, None] + pc[sid][pi][None, :]).reshape(-1) for sid in all_sets}
        return score_rows(rows, cnt).reshape(len(qi), len(pi))

    n_done = 0
    qi_all, pi_all = np.arange(len(quads)), np.arange(len(pairs))
    if len(quads) * len(pairs) > MAX_COMBOS:
        # rank quadruples against the best pairs and pairs against the best quadruples, then cut both
        p_lin = eval_block(qi_all[:1], pi_all)[0]
        p_top = np.argsort(-p_lin)[:3]
        q_score = np.max(np.concatenate([eval_block(c, p_top) for c in np.array_split(qi_all, max(1, len(qi_all) // 20000))]), axis=1)
        n_done += len(pairs) + len(quads) * len(p_top)
        q_top = np.argsort(-q_score)[:5]
        p_score = np.max(eval_block(q_top, pi_all), axis=0)
        n_done += len(q_top) * len(pairs)
        n_p = max(4, min(len(pairs), int(np.sqrt(MAX_COMBOS / 20))))
        pi_all = np.argsort(-p_score)[:n_p]
        n_q = max(1, MAX_COMBOS // len(pi_all))
        qi_all = np.argsort(-q_score)[:n_q]
    found: list[tuple[float, tuple]] = []
    per = max(1, CHUNK // len(pi_all))
    for start in range(0, len(qi_all), per):
        report(start / len(qi_all))
        qi = qi_all[start:start + per]
        block = eval_block(qi, pi_all)
        n_done += block.size
        flat = block.reshape(-1)
        k = min(top_n, flat.size)
        top = np.argpartition(-flat, k - 1)[:k]
        for t in top:
            a, b = divmod(int(t), len(pi_all))
            q = quads[qi[a]]
            p = pairs[pi_all[b]]
            found.append((float(flat[t]), (*q, *p)))
        found = _merge([], found, top_n)
    return found, n_done


def _merge(a, b, n):
    seen = {}
    for v, idx in [*a, *b]:
        if idx not in seen or seen[idx] < v:
            seen[idx] = v
    return sorted(((v, i) for i, v in seen.items()), key=lambda x: -x[0])[:n]
