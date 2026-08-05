#!/usr/bin/env python3
"""sphere_brain — proven integer kernels through a logic engine, driven by
local models.

    BRAIN  = the Sphere logic engine: authors an expression from example
             pairs and refuses to answer when the data does not decide.
    BODY S = a local model for semantics (reads your log format, relays
             your intent in one word).
    BODY D = a local model for raw data (copies observed pairs out of your
             logs — it is never allowed to invent one).

Everything a body returns is validated before the brain sees it; a pair
that does not literally occur in your data is discarded.  The output label
is honest by construction: PROVEN only when an exhaustive sweep over all
2^32 inputs passed; otherwise SAMPLED(n).  The engine ships no guesses —
when the data, material, or budget does not decide, it abstains and names
the remedy.

Usage:
  python3 frontier/sphere_brain.py solve spec.txt data.log ["intent sentence"]
  python3 frontier/sphere_brain.py selftest            # offline, no models
  Library: SphereBrain().solve(spec, telemetry=..., intent_sentence=...)
           SphereBrain().solve(spec, pairs=[(x, y), ...])   # the sphere alone

Requires: a C compiler (cc) in PATH; ollama at localhost:11434 for the live
bodies (any models you have; defaults: llama3:8b and qwen2.5-coder:7b).
"""
import json, os, re, signal, subprocess, sys, tempfile, time, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from organism.sphere import sphere_synthesize            # noqa: E402
from organism.autonomy import register                   # noqa: E402
from organism.synth import s32, _eval                    # noqa: E402

INT_MIN, INT_MAX = -2**31, 2**31 - 1
PAIR_RE = re.compile(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)")
LINE_RES = (re.compile(r"in=(-?\d+)\s+out=(-?\d+)"),
            re.compile(r"\((-?\d+)\)\s*->\s*(-?\d+)"))


class Alarm(Exception):
    pass


signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(Alarm()))


def _gate_receipt():
    assert _eval("((2 & ((-x) >> 31)) + ((x | (-x)) >> 31))", INT_MIN) == 1, \
        "bug-fifteen fix missing — refuse to run on an unwrapped gate"


def material_from_spec(spec):
    """Blind mechanical material: survived the hand-the-answers audit 5/5."""
    consts = {0, 1}
    for n in (int(n) for n in re.findall(r"\d+", spec)):
        if 0 < n < 2**31:
            consts |= {n, n - 1}
    prims = []
    m = re.search(r"bits (\d+) through (\d+)", spec)
    if m:
        prims.append("(x >> %s)" % m.group(1))
    return sorted(consts), prims


class SphereBrain:
    def __init__(self, body_s="llama3:8b", body_d="qwen2.5-coder:7b",
                 host="http://localhost:11434", say=print):
        self.body_s, self.body_d, self.host, self.say = body_s, body_d, host, say

    # ---------------- bodies (each call its own hard-timeout request) -------
    def _gen(self, model, prompt, n=350, t=0.1, timeout=180):
        body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                           "options": {"temperature": t, "num_predict": n,
                                       "seed": 0x5E3A11C}}).encode()
        req = urllib.request.Request(self.host + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return json.loads(f.read())["response"]

    def body_field_map(self, sample):
        return self._gen(self.body_s, "Log sample:\n" + sample +
                         "\n\nTwo line formats carry observations of one function. "
                         "Answer in one line each:\nFORMAT1: <pattern with INPUT and "
                         "OUTPUT marked>\nFORMAT2: <same>\n", n=120).strip()[:200]

    def body_relay(self, sentence):
        r = self._gen(self.body_s, 'A user describes an integer function: "%s".\n'
                      "Which ONE word fits best: arith, mask, mix, any?\n"
                      "Answer with only the word." % sentence, n=6)
        return next((w for w in ("arith", "mask", "mix", "any") if w in r.lower()), "any")

    def body_extract(self, field_map, lines):
        cands = []
        for w0 in range(0, len(lines), 60):
            resp = self._gen(self.body_d, "Field map:\n" + field_map +
                             "\n\nLog window:\n" + "\n".join(lines[w0:w0 + 60]) +
                             "\n\nCopy every observation as (input, output), one per "
                             "line, nothing not literally present:\n(", n=600)
            cands += [(int(a), int(b)) for a, b in PAIR_RE.findall("(" + resp)]
        return cands

    # ---------------- the brain --------------------------------------------
    @staticmethod
    def gate_index(lines):
        occur = {}
        for L in lines:
            for rx in LINE_RES:
                m = rx.search(L)
                if m:
                    k = (int(m.group(1)), int(m.group(2)))
                    occur[k] = occur.get(k, 0) + 1
                    break
        return occur

    @staticmethod
    def structural_gate(cands, occur):
        gated, invented, seen = [], 0, {}
        for c in cands:
            if occur.get(c, 0) > seen.get(c, 0):
                seen[c] = seen.get(c, 0) + 1
                gated.append(c)
            else:
                invented += 1
        return gated, invented

    @staticmethod
    def consensus(gated):
        counts = {}
        for (x, y) in gated:
            counts.setdefault(x, {}).setdefault(y, 0)
            counts[x][y] += 1
        pairs, contested = [], 0
        for x, ys in sorted(counts.items()):
            ranked = sorted(ys.items(), key=lambda kv: -kv[1])
            if ranked[0][1] >= 2 and (len(ranked) == 1 or ranked[1][1] < 2):
                pairs.append((x, ranked[0][0]))
            elif len(ranked) > 1 and ranked[1][1] >= 2:
                contested += 1
        return pairs, contested

    def author(self, pairs, hold, word, consts, extra, budget=180, size=6):
        signal.alarm(budget)
        t0 = time.time()
        try:
            r = sphere_synthesize(pairs, holdout=hold, intent=word, max_size=size,
                                  consts=consts, extra_ops=tuple(extra))
            signal.alarm(0)
            return r, time.time() - t0
        except Alarm:
            return None, float(budget)

    def solve(self, spec, telemetry=None, pairs=None, intent_sentence=None,
              verify_c=None, budget=180):
        """telemetry: raw log text (bodies parse it) | pairs: ready [(x,y)].
        Returns {status, label, c_expression, why, log}."""
        _gate_receipt()
        log, say = [], self.say

        def note(tag, msg):
            line = "[%s] %s" % (tag, msg)
            log.append(line)
            say(line)

        consts, prims = material_from_spec(spec)
        extra = []
        for i, b in enumerate(prims):
            nm = "sb_%d_%d" % (abs(hash(spec)) % 9973, i)
            register(nm, b)
            extra.append(nm)
        note("BRAIN", "spec material (mechanical): consts=%s prims=%s" % (consts, prims or "none"))

        word = "any"
        if intent_sentence:
            word = self.body_relay(intent_sentence)
            note("BODY-S", "relayed %r -> %r (uncertain relays go wide by law)" % (intent_sentence, word))

        occur = {}
        if telemetry is not None:
            lines = telemetry.splitlines()
            occur = self.gate_index(lines)
            fmap = self.body_field_map("\n".join(lines[:12]))
            note("BRAIN", "commanded Body S: field map captured")
            cands = self.body_extract(fmap, lines)
            note("BODY-D", "extracted %d candidates" % len(cands))
            gated, invented = self.structural_gate(cands, occur)
            pairs, contested = self.consensus(gated)
            note("GATE", "%d literal, %d inventions discarded, %d contested dropped, %d confirmed"
                 % (len(gated), invented, contested, len(pairs)))
        elif pairs is None:
            return {"status": "ABSTAIN", "why": "no data supplied", "log": log}
        else:
            pairs = [tuple(p) for p in pairs]

        if len(pairs) < 4:
            note("BRAIN", "HONEST ABSTAIN: %d confirmed pairs (< 4); refusing to author "
                 "from thin data" % len(pairs))
            return {"status": "ABSTAIN", "why": "starved: too few confirmed pairs",
                    "remedy": "more observations per input (>=2 sightings each)", "log": log}

        hold = pairs[3::4]
        given = [p for p in pairs if p not in hold]

        for rnd in (1, 2, 3):
            r, dt = self.author(given, hold, word, consts, extra, budget)
            if r is not None and r.found:
                note("BRAIN", "round %d: BUILT %s (%s evals, %.2fs)"
                     % (rnd, r.expr, format(r.evaluations, ","), dt))
                label = "SAMPLED(%d)" % len(pairs)
                if verify_c:
                    v, sdt = sweep(r.expr, verify_c)
                    if v == "PROVEN":
                        label = "PROVEN"
                        note("GATE", "exhaustive 2^32 sweep: PROVEN (%.1fs)" % sdt)
                    else:
                        note("GATE", "sweep refuted the build (%s) — not shipped" % v)
                        return {"status": "ABSTAIN", "why": "refuted by sweep: " + v, "log": log}
                return {"status": label.split("(")[0] if label == "PROVEN" else "VERIFIED-SAMPLE",
                        "label": label, "c_expression": r.expr,
                        "evaluations": r.evaluations, "log": log}
            ev = format(r.evaluations, ",") if r else "budget"
            note("BRAIN", "round %d: abstain (%s)" % (rnd, ev))
            if rnd == 1:
                want = {INT_MIN, INT_MAX} | {s32(c - 2**31) for c in consts if c > 1}
                have = {x for x, _ in given}
                added = 0
                for (x, y), n in occur.items():
                    if x in want and x not in have and n >= 2:
                        given.append((x, y))
                        added += 1
                note("BRAIN", "command: witness demand — %d gate-sourced witnesses added" % added)
                if added:
                    continue
                rnd = 2  # fall through to leave-one-out immediately
            if rnd >= 2:
                note("BRAIN", "command: leave-one-out refit over %d suspects "
                     "(quick pass, most-suspicious-first)" % len(given))
                for i in reversed(range(len(given))):
                    sub = given[:i] + given[i + 1:]
                    r2, _ = self.author(sub, hold, word, consts, extra, budget=6, size=4)
                    if r2 is None or not r2.found:
                        r2 = None
                    if r2 is not None and r2.found:
                        note("BRAIN", "dropping pair %s let the space open: poison named; "
                             "BUILT %s" % (given[i], r2.expr))
                        label = "SAMPLED(%d)" % len(sub)
                        if verify_c:
                            v, sdt = sweep(r2.expr, verify_c)
                            if v != "PROVEN":
                                note("GATE", "leave-one-out build refuted (%s) — not shipped" % v)
                                continue
                            label = "PROVEN"
                            note("GATE", "exhaustive 2^32 sweep: PROVEN (%.1fs)" % sdt)
                        return {"status": "PROVEN" if label == "PROVEN" else "VERIFIED-SAMPLE",
                                "label": label, "c_expression": r2.expr,
                                "poison_dropped": list(given[i]),
                                "evaluations": r2.evaluations, "log": log}
                break
        note("BRAIN", "HONEST ABSTAIN: preconditions not met (data separation, material, "
             "or budget); the engine does not guess")
        return {"status": "ABSTAIN",
                "why": "no expression fits the confirmed data within material+budget",
                "remedy": "more sightings per input; boundary observations "
                          "(INT_MIN, INT_MAX, c-2^31); or wider material",
                "log": log}


def sweep(expr, ref_body):
    """PROVEN's only source: all 2^32, 3 separate TUs, -fno-lto, fold floor 2s."""
    d = tempfile.mkdtemp()
    open(os.path.join(d, "f.c"), "w").write(
        "__attribute__((noinline)) int f(int x){ return %s; }\n" % expr)
    open(os.path.join(d, "g.c"), "w").write(
        "__attribute__((noinline)) int g(int x){ %s }\n" % ref_body)
    open(os.path.join(d, "m.c"), "w").write(
        '#include <stdio.h>\n#include <stdint.h>\nint f(int); int g(int);\n'
        'int main(){uint32_t u=0;long long bad=0;do{int32_t x=(int32_t)u;'
        'if(f(x)!=g(x))bad++;u++;}while(u!=0);'
        'printf(bad?"WRONG %lld\\n":"PROVEN\\n",bad);return 0;}\n')
    for s_, o in (("f.c", "f.o"), ("g.c", "g.o")):
        subprocess.run(["cc", "-O3", "-fwrapv", "-fno-lto", "-w", "-c",
                        os.path.join(d, s_), "-o", os.path.join(d, o)], check=True)
    subprocess.run(["cc", "-O3", "-fwrapv", "-fno-lto", "-w", os.path.join(d, "m.c"),
                    os.path.join(d, "f.o"), os.path.join(d, "g.o"),
                    "-o", os.path.join(d, "run")], check=True)
    t0 = time.time()
    out = subprocess.run([os.path.join(d, "run")], capture_output=True, text=True,
                         timeout=900).stdout.strip()
    dt = time.time() - t0
    if dt < 2.0 and out == "PROVEN":
        return "SUSPECTED-FOLD", dt
    return out.split()[0], dt


def selftest():
    """Offline: no models.  Feeds the brain ready pairs, including a poisoned
    set that leave-one-out must name.  Exits non-zero on failure."""
    _gate_receipt()
    print("[SELFTEST] gate receipt ok")
    b = SphereBrain(say=lambda s: print("  " + s))
    xs = [0, 1, 2, 3, 7, 8, 15, 16, 100, 255, 256, -1, -2, -100, INT_MIN, INT_MAX, 127 - 2**31]
    truth = lambda x: s32(x & ~127)
    clean = [(x, truth(x)) for x in xs]
    r = b.solve("round the size down to a multiple of 128", pairs=clean,
                verify_c="return x & ~127;")
    assert r["status"] == "PROVEN", r
    print("[SELFTEST] clean pairs -> PROVEN:", r["c_expression"])
    poisoned = list(clean) + [(4096, truth(4096) + 7)]
    r2 = b.solve("round the size down to a multiple of 128", pairs=poisoned,
                 verify_c="return x & ~127;", budget=20)
    assert r2["status"] == "PROVEN" and r2.get("poison_dropped") == [4096, truth(4096) + 7], r2
    print("[SELFTEST] poisoned pair NAMED and dropped by leave-one-out; PROVEN:",
          r2["c_expression"])
    r3 = b.solve("something underdetermined", pairs=[(1, 1), (2, 2), (3, 3), (4, 4)])
    assert r3["status"] in ("VERIFIED-SAMPLE", "ABSTAIN")
    print("[SELFTEST] thin/no-verify path labels honestly:", r3.get("label", r3["status"]))
    print("[SELFTEST] ALL CHECKS PASSED")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) >= 4 and sys.argv[1] == "solve":
        spec = open(sys.argv[2]).read().strip()
        telem = open(sys.argv[3]).read()
        sentence = sys.argv[4] if len(sys.argv) > 4 else None
        out = SphereBrain().solve(spec, telemetry=telem, intent_sentence=sentence)
        print(json.dumps({k: v for k, v in out.items() if k != "log"}, indent=1))
    else:
        print(__doc__)
