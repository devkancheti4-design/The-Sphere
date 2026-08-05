""
from __future__ import annotations
from typing import Dict, List, Optional, Sequence, Tuple

from .core import Organism, seed_for_window
from .synth import _OPS, Grammar, Result, s32, _eval, verify_with_compiler

                                                                              
                                                                             

FAMILIES: Dict[str, Tuple[str, ...]] = {
    "LIN": ("+", "-", "neg", "+1", "-1"),
    "SHF": ("<<1", "<<2", "<<3", "<<4", "<<5", ">>1"),
    "SGN": (">>31",),
    "BIT": ("&", "|", "~"),
    "XOR": ("^",),
}
_FAM_CONSTS = {"LIN": (0, 1, 2), "SHF": (), "SGN": (), "BIT": (-1, 7, 31),
               "XOR": ()}
_ALL = tuple(FAMILIES)

INTENT_FAMILIES: Dict[str, Tuple[str, ...]] = {
    "any":   _ALL,
    "arith": ("LIN", "SHF"),
    "mask":  ("LIN", "SHF", "SGN", "BIT"),
    "mix":   ("SHF", "SGN", "BIT", "XOR"),
}


def _space(fams: Sequence[str]) -> Grammar:
    ops = tuple(op for f in _ALL if f in fams for op in FAMILIES[f])
    ks = tuple(k for f in _ALL if f in fams for k in _FAM_CONSTS[f])
    return Grammar(ops=ops, consts=ks or (0, 1))


def _fam_of(op: str) -> str:
                                                                           
                                                                          
    return next((f for f, ops in FAMILIES.items() if op in ops), "DICT")


                                                                               

def data_shield(pairs: Sequence[Tuple[int, int]]) -> Tuple[str, ...]:
    ""
    d = {s32(x): s32(y) for x, y in pairs}
    keys = sorted(d)
    triples = viol = 0
    for i, a in enumerate(keys):
        for b in keys[i:]:
            c = s32(a + b)
            if c in d and (a, b) != (0, 0):
                triples += 1
                if s32(d[a] + d[b]) != d[c]:
                    viol += 1
    if triples >= 3 and viol == 0:
        return ("LIN", "SHF")
    return _ALL


                                                                               
                                                                         

def _partners(want, vals, ops):
                                                                           
                                                                       
                                                                          
                                                                           
                                                                           
    if "+" in ops:
        yield tuple(s32(w - v) for w, v in zip(want, vals)), "+", "ab"
    if "-" in ops:
        yield tuple(s32(w + v) for w, v in zip(want, vals)), "-", "ab"
        yield tuple(s32(v - w) for w, v in zip(want, vals)), "-", "ba"
    if "^" in ops:
        yield tuple(s32(w ^ v) for w, v in zip(want, vals)), "^", "ab"


class _N:
    __slots__ = ("vals", "expr", "size")

    def __init__(self, vals, expr, size):
        self.vals, self.expr, self.size = vals, expr, size


                                                                               

def sphere_synthesize(examples: Sequence[Tuple[int, int]],
                      holdout: Sequence[Tuple[int, int]] = (),
                      intent: str = "any",
                      max_size: int = 6,
                      consts: Optional[Sequence[int]] = None,
                      extra_ops: Sequence[str] = (),
                      on_event=None) -> Result:
    ""
    xs = [s32(a) for a, _ in examples]
    want = tuple(s32(b) for _, b in examples)
    if not xs:
        return Result(False, note="no examples given")

    say = on_event or (lambda _: None)

                                                                        
    o_data, o_intent, o_second, o_search = (
        Organism(first_seed=seed_for_window(w), oid=i)
        for i, w in enumerate((330, 400, 410, 420), 1))
    fam_id = {f: i for i, f in enumerate(_ALL)}
    fam_id["DICT"] = len(_ALL)

    maskD = data_shield(examples)
    maskI = INTENT_FAMILIES.get(intent, _ALL)
    maskI2: Optional[Tuple[str, ...]] = None
    second_may_speak = True                                                    
    evals = 0

    def ok(expr: str) -> bool:
        ""
        if not holdout:
            return True
        vals = [_eval(expr, hx) for hx, _ in holdout]
        if any(v is None for v in vals):
            ok_c, _why = verify_with_compiler(expr, list(holdout))
            return ok_c
        return all(v == s32(hy) for v, (_hx, hy) in zip(vals, holdout))

    def die(org: Organism):
        c = org.cycles
        while org.cycles == c:
            org.beat()

    while True:
        fams = tuple(f for f in maskD if f in maskI) or _ALL
        g = _space(fams)
        if consts is not None or extra_ops:
            g = Grammar(ops=tuple(g.ops) + tuple(o for o in extra_ops
                                                 if o not in g.ops),
                        consts=tuple(consts) if consts is not None
                        else g.consts)
        small = fams
        say(f"space D∩I = {'+'.join(fams)}  ({len(g.ops)} operators, "
            f"{len(g.consts)} consts)")

        index: Dict[tuple, _N] = {}
        levels: List[List[_N]] = [[]]
        narrowed = False
        deaths4 = o_second.cycles

        def add(vals, expr, size, bucket):
            if vals in index:
                return None
            n = _N(vals, expr, size)
            index[vals] = n
            bucket.append(n)
            return n

        def join(n):
            nonlocal evals
            if any(v is None for v in n.vals):
                                                                        
                                                                            
                                                                            
                return None
            for pv, op, order in _partners(want, n.vals, g.ops):
                p = index.get(pv)
                if p is not None:
                    evals += 1
                    a, b = (p, n) if order == "ab" else (n, p)
                    expr = _OPS[op][1].format(a=a.expr, b=b.expr)
                    if ok(expr):
                        return Result(True, expr, a.size + b.size + 1, evals,
                                      False, g, f"sphere: forced {op}-join — "
                                      "exact, minimality not proved")
            return None

        for c in [None] + list(g.consts):
            vals = tuple(xs) if c is None else tuple(s32(c) for _ in xs)
            n = add(vals, "x" if c is None else str(c), 0, levels[0])
            if n and n.vals == want and ok(n.expr):
                return Result(True, n.expr, 0, evals, True, g, "sphere: size 0")
            if n and (r := join(n)):
                return r

        found_exhausted = False
        for size in range(1, max_size + 1):
            active = [op for op in g.ops
                      if maskI2 is None or _fam_of(op) in maskI2
                      or _fam_of(op) == "DICT"]
            new: List[_N] = []
            for i in range(size):
                for na in levels[i]:
                    for opname in active:
                        ar, tmpl, fn = _OPS[opname]
                        bs = [None] if ar == 1 else levels[size - 1 - i]
                        if ar == 1 and i != size - 1:
                            continue
                        for nb in bs:
                            evals += 1
                            o_search.beat()                                     
                            o_data.beat()
                            o_intent.beat()
                            if ar == 1:
                                vals = tuple(fn(v, 0) for v in na.vals)
                                expr = tmpl.format(a=na.expr)
                            else:
                                vals = tuple(fn(u, v)
                                             for u, v in zip(na.vals, nb.vals))
                                expr = tmpl.format(a=na.expr, b=nb.expr)
                            if any(v is None for v in vals):
                                continue                                      
                                                                          
                            if vals == want and ok(expr):
                                where = "D∩I∩I2" if narrowed else "D∩I"
                                return Result(True, expr, size, evals, True, g,
                                              f"sphere: minimal in {where}")
                            n = add(vals, expr, size, new)
                            if n:
                                o_second.observe(fam_id[_fam_of(opname)])
                                if r := join(n):
                                    return r
            levels.append(new)
            say(f"level {size}: {len(new):,} new  ({evals:,} evals)")
            if not new:
                break
            if o_second.cycles > deaths4:                                     
                deaths4 = o_second.cycles
                spoken = tuple(f for f in fams if o_second.adopted(fam_id[f]))
                if (second_may_speak and spoken and set(spoken) < set(fams)
                        and maskI2 != spoken):
                    maskI2, narrowed = spoken, True
                    say(f"org4 death: what recurred needs {'+'.join(spoken)} "
                        f"— small space D∩I∩I2")

                                                                           
        if narrowed:
            die(o_second)
            maskI2, second_may_speak = None, False                             
            say("death of org4: the small space starved — back to D∩I")
        elif set(maskD) != set(_ALL):
            die(o_data)
            maskD, second_may_speak = _ALL, True                              
            say("death of the data shield: re-cuts wider")
        elif set(maskI) != set(_ALL):
            die(o_intent)
            maskI, second_may_speak = _ALL, True
            say("death of the intent shield: re-cuts wider")
        else:
            return Result(False, evaluations=evals,
                          note=f"sphere: no expression of size <= {max_size} "
                               "— every cut widened, the space closed empty")
