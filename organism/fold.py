""
from __future__ import annotations
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .core import Organism, seed_for_window
from .synth import _OPS, s32

_UN = ("neg", "+1", "-1", ">>31", "~")
_BIN = ("+", "-", "&", "|")
_K = (0, 1)

GRID1 = (0, 1, 2, 5, 7, -1, -3, -8, 100, -100, 1 << 20, -(1 << 20))
GRID2 = ((0, 0), (1, 2), (-1, 3), (5, -2), (-4, -6), (7, 1), (-9, 8),
         (3, -3), (100, -5), (-100, 7), (1 << 18, -9), (-(1 << 18), 4))


class _E:
    __slots__ = ("expr", "fn", "size")

    def __init__(self, expr, fn, size):
        self.expr, self.fn, self.size = expr, fn, size


def _grow(leaves: List[_E], max_size: int, unary, grid_of) -> List[List[_E]]:
    ""
    seen = {grid_of(e): e for e in leaves}
    levels = [list(seen.values())]
    for size in range(1, max_size + 1):
        new: List[_E] = []
        for i in range(size):
            for na in levels[i]:
                if i == size - 1:
                    for op in unary:
                        _, tmpl, fn = _OPS[op]
                        e = _E(tmpl.format(a=na.expr),
                               (lambda f, g: lambda *v: f(g(*v), 0))(fn, na.fn),
                               size)
                        k = grid_of(e)
                        if k not in seen:
                            seen[k] = e
                            new.append(e)
                for op in _BIN:
                    _, tmpl, fn = _OPS[op]
                    for nb in levels[size - 1 - i]:
                        e = _E(tmpl.format(a=na.expr, b=nb.expr),
                               (lambda f, g, h: lambda *v: f(g(*v), h(*v)))
                               (fn, na.fn, nb.fn), size)
                        k = grid_of(e)
                        if k not in seen:
                            seen[k] = e
                            new.append(e)
        levels.append(new)
    return levels


def selfplay(max_size: int = 4, cap: int = 16, on_event=None):
    ""
    say = on_event or (lambda _: None)
    org = Organism(first_seed=seed_for_window(410), oid=4)
    leaves = [_E("x", lambda x: s32(x), 0)] + \
             [_E(str(k), (lambda kk: lambda x: kk)(k), 0) for k in _K]
    grid_of = lambda e: tuple(e.fn(v) for v in GRID1)

    counts: Dict[tuple, int] = {}
    smallest: Dict[tuple, _E] = {}
    seen = {grid_of(e) for e in leaves}
    levels = [[e for e in leaves]]
    for size in range(1, max_size + 1):
        new = []
        for i in range(size):
            for na in levels[i]:
                combos = ([(op, None) for op in _UN] if i == size - 1 else [])
                combos += [(op, nb) for op in _BIN
                           for nb in levels[size - 1 - i]]
                for op, nb in combos:
                    _, tmpl, fn = _OPS[op]
                    if nb is None:
                        e = _E(tmpl.format(a=na.expr),
                               (lambda f, g: lambda x: f(g(x), 0))(fn, na.fn),
                               size)
                    else:
                        e = _E(tmpl.format(a=na.expr, b=nb.expr),
                               (lambda f, g, h: lambda x: f(g(x), h(x)))
                               (fn, na.fn, nb.fn), size)
                    k = grid_of(e)
                    counts[k] = counts.get(k, 0) + 1
                    org.observe(k)                                            
                    if k not in smallest or size < smallest[k].size:
                        smallest[k] = e
                    if k not in seen:
                        seen.add(k)
                        new.append(e)
        levels.append(new)

    ident = tuple(s32(v) for v in GRID1)
    adopted = [k for k in smallest
               if org.adopted(k) and k != ident and len(set(k)) > 1
               and smallest[k].size >= 3]                                     
                                                                             
                                                                           
    adopted.sort(key=lambda k: (-counts[k], smallest[k].size))
    prims = [smallest[k] for k in adopted[:cap]]
    say(f"self-play: {len(counts):,} behaviours, {len(adopted):,} recurred "
        f"and survived the organism's deaths, {len(prims)} promoted")
    return prims


def author_fold(train: Sequence[Tuple[Sequence[int], int]],
                holdout: Sequence[Tuple[Sequence[int], int]],
                oracle: Callable[[Sequence[int]], int],
                counter_arrays: Sequence[Sequence[int]],
                rounds: int = 3,
                e1_size: int = 2, e2_size: int = 3,
                dict_prims: Sequence[Tuple[str, str]] = (),
                on_event=None):
    ""
    from .synth import _eval
    say = on_event or (lambda _: None)
    prims = selfplay(on_event=say)
    for p in prims:                                                         
        _OPS[f"u{prims.index(p)}"] = (
            1, "(" + p.expr.replace("x", "{a}") + ")",
            (lambda g: lambda a, _u: g(a))(p.fn))
    for name, raw in dict_prims:                                            
        _OPS[name] = (1, "(" + raw.replace("x", "{a}") + ")",
                      (lambda e: lambda a, _u: _eval(e, a))(raw))
    if dict_prims:
        say(f"dict: {len(dict_prims)} entries from past authored work — "
            + ", ".join(n for n, _ in dict_prims))
    unary = _UN + tuple(f"u{i}" for i in range(len(prims))) \
        + tuple(n for n, _ in dict_prims)

    leaves = [_E("c", lambda c, x: s32(c), 0), _E("x", lambda c, x: s32(x), 0)] \
        + [_E(str(k), (lambda kk: lambda c, x: kk)(k), 0) for k in _K]
    grid_of = lambda e: tuple(e.fn(c, x) for c, x in GRID2)
    levels = _grow(leaves, e2_size, unary, grid_of)
    pool = [e for lv in levels for e in lv]
    say(f"two-variable space: {len(pool):,} distinct behaviours to size "
        f"{e2_size} (material: {len(unary)} unary + {len(_BIN)} binary ops)")

                                                                          
                                                                            
                                                                  
    def dep2(e):
        return (any(e.fn(a, x) != e.fn(b, x)
                    for a, b, x in ((0, 5, 3), (1, -4, 7), (-2, 9, -6)))
                and any(e.fn(c, a) != e.fn(c, b)
                        for c, a, b in ((4, 0, 5), (-3, 2, -8), (6, 1, -1))))

    steps = [e for e in pool if dep2(e)]
    say(f"{len(steps):,} of {len(pool):,} behaviours read both inputs")

    train = [(list(a), s32(w)) for a, w in train]
    evals = 0

    def run_one(e, arr):
        c = s32(arr[0])
        for x in arr[1:]:
            c = e.fn(c, x)
        return c

    def run_two(e1, e2, arr):
        s = b = s32(arr[0])
        for x in arr[1:]:
            s = e1.fn(s, x)
            b = e2.fn(b, s)
        return b

    def scan_seq(e1, arr):
        s = s32(arr[0])
        out = [s]
        for x in arr[1:]:
            s = e1.fn(s, x)
            out.append(s)
        return tuple(out)

    for rnd in range(1, rounds + 1):
                                                                       
        got = None
        for e in pool:
            evals += 1
            if all(run_one(e, a) == w for a, w in train):
                got = ("ONE", e, None)
                break
        if got is None:
                                                                            
                                                                
            sigs: Dict[tuple, _E] = {}
            for e in steps:
                if e.size <= e1_size:
                    k = tuple(scan_seq(e, a) for a, _ in train)
                    if k not in sigs or e.size < sigs[k].size:
                        sigs[k] = e
            e1s = sorted(sigs.items(), key=lambda kv: kv[1].size)
            say(f"scheme TWO: {len(e1s):,} distinct scan behaviours × "
                f"{len(steps):,} reducers, size-ordered")
            wants = [w for _, w in train]
            for total in range(2, e1_size + e2_size + 1):
                for seqs, e1 in e1s:
                    if e1.size >= total:
                        continue
                    for e2 in steps:
                        if e2.size != total - e1.size:
                            continue
                        evals += 1
                        hit = True
                        for seq, w in zip(seqs, wants):
                            b = seq[0]
                            for s in seq[1:]:
                                b = e2.fn(b, s)
                            if b != w:
                                hit = False
                                break
                        if hit:
                            got = ("TWO", e1, e2)
                            break
                    if got:
                        break
                if got:
                    break
        if got is None:
            say(f"round {rnd}: ABSTAIN after {evals:,} program evaluations")
            return None

        scheme, e1, e2 = got
        run = (lambda a: run_one(e1, a)) if scheme == "ONE" else \
              (lambda a: run_two(e1, e2, a))
        say(f"round {rnd}: authored scheme {scheme}"
            f"  e1 = {e1.expr}" + (f"  e2 = {e2.expr}" if e2 else "") +
            f"  ({evals:,} program evaluations)")

        if not all(run(a) == s32(w) for a, w in holdout):
            say(f"round {rnd}: REJECTED by held-out arrays — searching on")
            train.append(next((list(a), s32(w)) for a, w in holdout
                              if run(a) != s32(w)))
            continue
        bad = next((a for a in counter_arrays if run(list(a)) != s32(oracle(a))),
                   None)
        if bad is None:
            return scheme, e1.expr, (e2.expr if e2 else None), evals, prims
        say(f"round {rnd}: verifier counterexample {list(bad)} — fed back "
            "as one more data pair, nothing else")
        train.append((list(bad), s32(oracle(bad))))
    return None
