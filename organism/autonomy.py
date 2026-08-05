""
from __future__ import annotations
from typing import Callable, Dict, List, Sequence, Tuple

from .synth import _OPS, Grammar, s32, synthesize, verify_with_compiler, _eval

_BASE_OPS = tuple(_OPS)                                                        


def register(name: str, raw_expr: str) -> None:
    ""
    _OPS[name] = (1, "(" + raw_expr.replace("x", "{a}") + ")",
                  lambda a, _unused, _e=raw_expr: _eval(_e, a))


def dict_ops() -> Tuple[str, ...]:
    return tuple(op for op in _OPS if op not in _BASE_OPS)


def run_stream(jobs: Sequence[Tuple[str, Callable[[int], int]]],
               given: Sequence[int], held: Sequence[int],
               max_size: int = 3, rounds: int = 4,
               consts: Sequence[int] = None, on_event=None):
    ""
    say = on_event or (lambda _: None)
    queue: List[Tuple[str, Callable[[int], int]]] = list(jobs)
    solved: Dict[str, dict] = {}

    for rnd in range(1, rounds + 1):
        progressed = False
        for name, fn in list(queue):
            ex = [(x, s32(fn(x))) for x in given]
            ho = [(x, s32(fn(x))) for x in held]
            g = Grammar(ops=tuple(_OPS)) if consts is None else \
                Grammar(ops=tuple(_OPS), consts=tuple(consts))
            r = synthesize(ex, holdout=ho, grammar=g, max_size=max_size)
            if not r.found:
                say(f"round {rnd}  {name}: abstain ({r.evaluations:,} evals) "
                    "— requeued")
                continue
            ok, why = verify_with_compiler(r.expr, ex + ho)
            if not ok:
                say(f"round {rnd}  {name}: REJECTED by compiler ({why}) "
                    "— requeued, nothing registered")
                continue
            register(name, r.expr)
            queue.remove((name, fn))
            solved[name] = dict(round=rnd, expr=r.expr, size=r.size,
                                evals=r.evaluations, minimal=r.minimal)
            progressed = True
            say(f"round {rnd}  {name}: BUILT {r.expr}  size {r.size}, "
                f"{r.evaluations:,} evals — now a primitive")
        if not queue or not progressed:
            break
    return solved, [n for n, _ in queue]
