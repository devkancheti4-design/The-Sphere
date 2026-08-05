""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from .core import Organism

M32 = 0xFFFFFFFF


def s32(v: int) -> int:
    v &= M32
    return v - (1 << 32) if v >= (1 << 31) else v


                                        
_OPS: Dict[str, Tuple[int, str, Callable]] = {
    "+":     (2, "({a} + {b})",  lambda a, b: s32(a + b)),
    "-":     (2, "({a} - {b})",  lambda a, b: s32(a - b)),
    "&":     (2, "({a} & {b})",  lambda a, b: s32(a & b)),
    "|":     (2, "({a} | {b})",  lambda a, b: s32(a | b)),
    "^":     (2, "({a} ^ {b})",  lambda a, b: s32(a ^ b)),
    "<<1":   (1, "({a} << 1)",   lambda a, _: s32(a << 1)),
    "<<2":   (1, "({a} << 2)",   lambda a, _: s32(a << 2)),
    "<<3":   (1, "({a} << 3)",   lambda a, _: s32(a << 3)),
    "<<4":   (1, "({a} << 4)",   lambda a, _: s32(a << 4)),
    "<<5":   (1, "({a} << 5)",   lambda a, _: s32(a << 5)),
    ">>1":   (1, "({a} >> 1)",   lambda a, _: a >> 1),
    ">>31":  (1, "({a} >> 31)",  lambda a, _: a >> 31),
    "~":     (1, "(~{a})",       lambda a, _: s32(~a)),
    "neg":   (1, "(-{a})",       lambda a, _: s32(-a)),
    "+1":    (1, "({a} + 1)",    lambda a, _: s32(a + 1)),
    "-1":    (1, "({a} - 1)",    lambda a, _: s32(a - 1)),
}


@dataclass
class Grammar:
    ""
    ops: Sequence[str] = tuple(_OPS)
    consts: Sequence[int] = (0, 1, 2, -1, 7, 31)


DEFAULT_GRAMMAR = Grammar()


@dataclass
class Result:
    found: bool
    expr: Optional[str] = None
    size: Optional[int] = None
    evaluations: int = 0
    minimal: bool = False                                                               
    grammar: Optional[Grammar] = None
    note: str = ""

    def __repr__(self):
        if not self.found:
            return f"Result(NOT FOUND after {self.evaluations:,} evaluations)"
        m = " MINIMAL" if self.minimal else ""
        return (f"Result({self.expr!r}, size={self.size},"
                f" evals={self.evaluations:,}{m})")


class _Node:
    __slots__ = ("vals", "expr", "size")

    def __init__(self, vals, expr, size):
        self.vals, self.expr, self.size = vals, expr, size


def synthesize(examples: Sequence[Tuple[int, int]],
               holdout: Sequence[Tuple[int, int]] = (),
               grammar: Grammar = DEFAULT_GRAMMAR,
               max_size: int = 4,
               exhaustive: bool = True,
               budget: int = 500_000,
               first_seed: int = 1_000_000_000_000,
               drive: str = "organism",
               on_level=None) -> Result:
    ""
    xs = [a for a, _ in examples]
    want = tuple(s32(b) for _, b in examples)
    if not xs:
        return Result(False, note="no examples given")

    seen = set()
    levels: List[List[_Node]] = [[]]

    def add(vals, expr, size, bucket) -> bool:
        if vals in seen:
            return False
        seen.add(vals)
        bucket.append(_Node(vals, expr, size))
        return True

    add(tuple(s32(x) for x in xs), "x", 0, levels[0])
    for c in grammar.consts:
        add(tuple(s32(c) for _ in xs), str(c), 0, levels[0])

    def check(n: _Node) -> bool:
        if n.vals != want:
            return False
        for hx, hy in holdout:
            v = _eval(n.expr, hx)
            if v is None or v != s32(hy):
                return False
        return True

    for n in levels[0]:
        if check(n):
            return Result(True, n.expr, 0, 0, exhaustive, grammar)

    evals = 0
    if exhaustive:
        for s in range(1, max_size + 1):
            new: List[_Node] = []
            for i in range(s):
                A_, B_ = levels[i], levels[s - 1 - i]
                for na in A_:
                    for opname in grammar.ops:
                        ar, tmpl, fn = _OPS[opname]
                        if ar == 1:
                            if i != s - 1:
                                continue
                            evals += 1
                            vals = tuple(fn(v, 0) for v in na.vals)
                            node = _Node(vals, tmpl.format(a=na.expr), s)
                            if check(node):
                                return Result(True, node.expr, s, evals, True, grammar)
                            add(vals, node.expr, s, new)
                        else:
                            for nb in B_:
                                evals += 1
                                vals = tuple(fn(u, v) for u, v in zip(na.vals, nb.vals))
                                node = _Node(vals, tmpl.format(a=na.expr, b=nb.expr), s)
                                if check(node):
                                    return Result(True, node.expr, s, evals, True, grammar)
                                add(vals, node.expr, s, new)
            levels.append(new)
            if on_level:
                on_level(s, len(new), evals)                                
            if not new:
                break
        return Result(False, evaluations=evals, grammar=grammar,
                      note=f"no expression of size <= {max_size} in this grammar")

                                                                                 
    pool = list(levels[0])
    org = Organism(first_seed=first_seed) if drive == "organism" else None
    rng = 0x243F6A8885A308D3
    ops = list(grammar.ops)
    while evals < budget:
        if org is not None:
            r = org.beat()
        else:
            rng ^= (rng << 13) & M32 * M32
            rng ^= rng >> 7
            rng ^= (rng << 17) & 0xFFFFFFFFFFFFFFFF
            r = rng
        a = pool[r % len(pool)]
        opname = ops[(r >> 17) % len(ops)]
        ar, tmpl, fn = _OPS[opname]
        b = pool[(r >> 29) % len(pool)]
        evals += 1
        if ar == 1:
            vals = tuple(fn(v, 0) for v in a.vals)
            expr = tmpl.format(a=a.expr)
            size = a.size + 1
        else:
            vals = tuple(fn(u, v) for u, v in zip(a.vals, b.vals))
            expr = tmpl.format(a=a.expr, b=b.expr)
            size = max(a.size, b.size) + 1
        node = _Node(vals, expr, size)
        if check(node):
            return Result(True, expr, size, evals, False, grammar,
                          "budgeted: minimality NOT proved")
        if vals not in seen:
            seen.add(vals)
            pool.append(node)
    return Result(False, evaluations=evals, grammar=grammar,
                  note="budget exhausted; minimality says nothing")


def _eval(expr: str, x: int) -> Optional[int]:
    ""
    import ast as _ast
    try:
        tree = _ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None

    def ev(n):
        if isinstance(n, _ast.Name):
            if n.id != "x":
                raise ValueError("unknown name")
            return s32(x)
        if isinstance(n, _ast.Constant):
            return s32(n.value)
        if isinstance(n, _ast.UnaryOp):
            v = ev(n.operand)
            if isinstance(n.op, _ast.USub):
                return s32(-v)
            if isinstance(n.op, _ast.Invert):
                return s32(~v)
            if isinstance(n.op, _ast.UAdd):
                return v
            raise ValueError("op")
        if isinstance(n, _ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            o = n.op
            if isinstance(o, _ast.Add):
                return s32(a + b)
            if isinstance(o, _ast.Sub):
                return s32(a - b)
            if isinstance(o, _ast.Mult):
                return s32(a * b)
            if isinstance(o, _ast.BitAnd):
                return s32(a & b)
            if isinstance(o, _ast.BitOr):
                return s32(a | b)
            if isinstance(o, _ast.BitXor):
                return s32(a ^ b)
            if isinstance(o, _ast.LShift):
                return s32(a << (b & 31))
            if isinstance(o, _ast.RShift):
                return a >> (b & 31)                                         
            raise ValueError("op")
        raise ValueError("node")

    try:
        return ev(tree)
    except Exception:
        return None


def verify_with_compiler(expr: str, pairs: Sequence[Tuple[int, int]],
                         cc: str = "cc") -> Tuple[bool, str]:
    ""
    import subprocess, tempfile, os
    d = tempfile.mkdtemp(prefix="mkd_")
    src, exe = os.path.join(d, "c.c"), os.path.join(d, "c")
    with open(src, "w") as f:
        f.write("#include <stdio.h>\n#include <stdint.h>\n#include <stdlib.h>\n"
                f"int32_t f(int32_t x){{ return {expr}; }}\n"
                "int main(int c,char**v){for(int i=1;i<c;i++)"
                "printf(\"%d\\n\",f((int32_t)strtol(v[i],0,10)));return 0;}\n")
    r = subprocess.run([cc, "-O2", "-w", "-o", exe, src], capture_output=True, text=True)
    if r.returncode != 0:
        return False, "compile error"
    p = subprocess.run([exe] + [str(a) for a, _ in pairs], capture_output=True, text=True)
    if p.returncode != 0:
        return False, "runtime error"
    got = [int(t) for t in p.stdout.split()]
    want = [s32(b) for _, b in pairs]
    return got == want, "ok" if got == want else "mismatch"
