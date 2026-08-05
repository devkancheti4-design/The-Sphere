# The Sphere

**Proven code from your data — through a logic engine, not a guess.**

## One step

```bash
./setup.sh
```

That's it: it pulls the two bodies (llama3:8b for semantics, qwen2.5-coder:7b
for raw data), verifies the brain with an offline self-test that ends in a
real proof over all 2^32 inputs, and you have a local setup with a
frontier-level brain. Any ollama models can be the bodies instead:

```python
SphereBrain(body_s="mistral", body_d="deepseek-coder:6.7b")
```

The Sphere authors small integer functions (int32 → int32) from example
input/output pairs and *proves* them: a result labeled **PROVEN** passed an
exhaustive sweep over all 4,294,967,296 possible inputs. When the data does
not decide an answer, the Sphere does not guess — it abstains and tells you
what is missing.

Local models plug in as **bodies**: one reads your log format and relays your
intent, one copies observed pairs out of your raw logs. They never write the
answer and they cannot invent data — every pair is checked against your raw
material before the engine sees it.

## Quick start

```bash
# 1. offline self-test (needs only a C compiler)
python3 frontier/sphere_brain.py selftest

# 2. the sphere alone — you supply pairs
python3 - <<'PY'
from frontier.sphere_brain import SphereBrain
r = SphereBrain().solve("round the size down to a multiple of 128",
                        pairs=[(0,0),(1,0),(127,0),(128,128),(255,128),
                               (256,256),(-1,-128),(-2147483648,-2147483648),
                               (2147483647,2147483520)],
                        verify_c="return x & ~127;")
print(r["label"], r["c_expression"])
PY

# 3. full brain-body — local models parse your logs (needs ollama)
python3 frontier/sphere_brain.py solve spec.txt service.log "masks only, no math"
```

## What the labels mean

- **PROVEN** — passed the exhaustive 2^32 sweep. Not tested: proven.
- **SAMPLED(n)** — exact on the n confirmed pairs and a held-out gate;
  supply `verify_c` to upgrade to PROVEN.
- **ABSTAIN** — the data, material, or budget did not decide. The response
  names the remedy (more sightings per input, boundary observations, wider
  material). An abstain is never silently upgraded.

## Measured record

On a laptop, sessions measured: proofs authored in tens to thousands of
engine evaluations (typically well under a second); cost per proven kernel
on the order of $0.00001 in electricity, verification included; and across
every measured battery the engine shipped **zero wrong answers** — every
failure was an abstain with a named cause.

## Scope, honestly

int32 → int32 expression kernels (bit manipulation, masks, arithmetic,
sign logic) — the code that is cheap to write wrong and expensive to ship
wrong. It does not write your services; it makes the sharp little functions
inside them provably correct.
