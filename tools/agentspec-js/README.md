# agentspec-js

The **JS runtime** for the agentspec workflow SPEC. The Python package at `tools/agentspec` is
the single source of truth; this package **translates** it — same constants, same closed
taxonomy, same envelope, same dispatch policies — and adds the **canonical JSON form** that lets
both runtimes emit byte-identical receipts.

Zero runtime dependencies. Node builtins only, matching the Python side's zero-dep stance.

```
npm test        # the coverage gate: 100% line + branch + function, census-guarded
npm run parity  # the C9 parity oracle: run both runtimes, compare BYTES
```

## What is here

| Module | Mirrors | Notes |
|---|---|---|
| `src/canonical.mjs` | `agentspec/canonical.py` | the canonical JSON form (R1-R15) |
| `src/taxonomy.mjs` | `agentspec/taxonomy.py` | the closed failure taxonomy |
| `src/argv.mjs` | `agentspec/argv.py` | prompt transport; **no `argv` member** |
| `src/envelope.mjs` | `agentspec/envelope.py` | the observation envelope |
| `src/spec.mjs` | `agentspec/spec.py` | declarative workflow types |
| `src/validate.mjs` | `agentspec/validate.py` | the closed violation set |
| `src/oracle.mjs` | `agentspec/oracle.py` | the six-clause completion AND-gate |
| `src/receipt.mjs` | `agentspec/receipt.py` | decode / parse / content checks |
| `src/progress.mjs` | `agentspec/progress.py` | progress-stream rejection |
| `src/terminal.mjs` | `agentspec/terminal.py` | `SUCCESS:` / `FAILED:` markers |
| `src/retry.mjs` | `agentspec/retry.py` | bounded retry policy, no jitter |
| `src/budget.mjs` | `agentspec/budget.py` | immutable ledger |
| `src/clock.mjs` | `agentspec/clock.py` | injected clock port, no real clock |
| `src/dispatchpolicy.mjs` | `agentspec/dispatchpolicy.py` | pre-dispatch checks |
| `src/corpus.mjs` | (harness) | reader for the shared conformance corpus |
| `src/pysource.mjs` | (harness) | reads constants OUT of the Python source |
| `src/version.mjs` | `agentspec/__init__.py` | `SPEC_VERSION` |

**Not mirrored, deliberately:** `determinism.py` and `testlint.py` are AST passes over *Python*
source. A JS "mirror" of them would analyse a language neither package is written in, so they
stay Python-only rather than being faked.

## The three gates

### 1. The coverage gate is real, not blind

`node --test --experimental-test-coverage` does **not** see a source file that no test imports:
the file is absent from the table entirely — not listed at 0% — and the run exits **0** reporting
`all files 100.00`. Measured on Node 22 and Node 24, and reproduced in this package.

Three things close it together, and all three are needed:

1. **`test/census.test.mjs`** walks `src/` on disk and `await import()`s every module, forcing
   each into the coverage table at its true rate. It also cross-checks the disk walk against
   `MODULES` in `src/index.mjs` — an independently written literal — so a new file must be
   declared, and it asserts the walk is non-empty so a broken glob fails instead of passing.
2. **All three thresholds.** A never-executed file reports `branch 100.00` while `funcs` is
   `0.00`, so a branches-only gate is still blind.
3. **`--test-coverage-exclude=test/**`, not `--test-coverage-include=src/**`.** Exclude is
   default-IN, so a stray source file outside `src/` is still measured. Include is default-OUT,
   i.e. fail-open — the same bug class as the trap. (`--test-coverage-include` also does not fix
   the trap at all: it filters the already-loaded set and never force-loads.)

`parity/` is excluded from coverage because those are executable scripts, not modules — and that
exclusion is itself bounded by `test/parity-shell.test.mjs`, which pins an allowlist plus a
per-file line budget so logic cannot migrate there to dodge the gate.

### 2. The cross-language drift gate

`test/crosslang.test.mjs` reads `tools/agentspec/agentspec/*.py` and asserts that every shared
vocabulary this package declares still equals the Python declaration — members **and** order.
The closed taxonomy, `PROMPT_TRANSPORTS`, `WINDOWS_CMDLINE_CAP`, `MIN_SUBSTRING_SCAN_LEN`, the
envelope fields, the oracle clauses, the validator's violation set and the canonical rejection
codes are all derived from one source rather than retyped as an independent JS decision.

The extractor (`src/pysource.mjs`) is itself validated against known-broken inputs, because a
parser that quietly returned `[]` would turn the whole drift gate green while measuring nothing.

### 3. The parity oracle

`fixtures/canonical-corpus.json` is the **contract**: 88 language-neutral cases in plain JSON.
`parity/emit_py.py` and `parity/emit_js.mjs` are two independent readers of it, and
`parity/oracle.mjs` runs both and compares the emitted manifests **byte for byte**.

Every case pins the **type**, not just the value (`{"int":"1"}` is an integer-typed value bounded
by 2^53; `{"num":"1"}` is a double), because a bare JSON number cannot say which it means — an
ambiguity that produced a false mismatch during the design probe.

## The canonical JSON form

Stock `json.dumps` and stock `JSON.stringify` disagree on **47 of 75** probe cases, and on
**15 of 15** container cases carrying an object key or two array elements — i.e. every realistic
receipt. Tuning the two stdlib encoders towards each other still leaves 32 divergences. So both
sides run a **custom encoder** and neither calls `JSON.stringify` for structure.

The 15 rules and the measured row behind each are documented in the `agentspec/canonical.py`
module docstring. The ones most likely to surprise:

- **R3** keys sort by **UTF-16 code unit** (JS `.sort()`), not code point. `sort_keys=True` does
  not fix this — V8 emits integer-like keys first in numeric order.
- **R6** the int/float tag is **erased**: `1.0` and `1` are one wire value. Lossy by design.
- **R7** the safe-integer bound belongs to the **integer type** (Python `int` / JS `BigInt`),
  never to a double. `1e100` is fine; `int(10**30)` is rejected.
- **R10/R11** unpaired surrogates and U+2028/U+2029 are escaped; a well-formed pair stays raw.
- **R13** an explicit depth cap of 100, so the boundary is not Python's recursion limit on one
  side and V8's stack on the other.

### Where the two languages cannot agree

Six conditions are **rejected** rather than papered over, with the identical code on both sides.
All six are segment-shaped, so `taxonomy.family()` resolves them to the existing closed member
`schema-invalid` — **the taxonomy does not grow for this module.**

| Condition | Code | Why agreement is impossible |
|---|---|---|
| `NaN` / `±Infinity` | `schema-invalid-nonfinite` | Python emits invalid JSON, JS emits `null` |
| integer type beyond ±(2^53−1) | `schema-invalid-int-range` | JS `Number` loses it silently; `BigInt` cannot stringify |
| non-string key | `schema-invalid-nonstring-key` | both coerce, with **different** rules |
| `undefined`/function/`Date`/`Map`/`Set`/boxed/hole/getter | `schema-invalid-unsupported-type` | `JSON.stringify` mangles each silently |
| reference cycle | `schema-invalid-cyclic` | no representation exists |
| depth > 100 | `schema-invalid-max-depth` | otherwise platform-dependent |

### One honest asymmetry

A JS string is a sequence of UTF-16 **code units**; a Python `str` is a sequence of **code
points**. Python can represent "a lone high surrogate immediately followed by a lone low
surrogate" as a value distinct from the astral character; **JS cannot represent that at all.**

The canonical form resolves this by **folding** an adjacent well-formed pair into its astral code
point on the Python side (`_fold_surrogate_pair`), so Python `"\ud83d\ude00"` and
`"\U0001f600"` both produce the bytes JS produces for its single string. That is lossy in one
direction, and it is the only mapping that keeps parity total. Not folding is worse than lossy:
it emits raw surrogates and `dumpb` then dies with `UnicodeEncodeError`.
