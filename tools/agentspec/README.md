---
title: README
type: note
permalink: dqverify-repo-20261013/tools/agentspec/readme
---

# agentspec

The portable, vendor-neutral **agent-workflow SPEC**, the shared **observation envelope**, the
**dispatch-safety pure core**, and a **hermetic regression-eval registry**.

Stdlib-only, zero runtime dependencies, no I/O on the dispatch path, no wall clock, no entropy.

## Why this package exists

**It is the SINGLE HOME for dispatch safety.** Two independent plans were building the same
argv guard, the same completion oracle and the same progress-stream rejection twice. Any runtime
or vendor adapter now *consumes* these functions; it must not reimplement them.

**The spec is the SINGLE SOURCE OF TRUTH.** A runtime does not invent its own dialect: it loads a
`Workflow`, validates it with `validate_workflow`, and translates it to whatever its vendor rail
needs. That is the mitigation the "second orchestration runtime" decision rests on — without one
shared spec, two runtimes diverge into rival dialects.

## Layout

| module | what it owns |
|---|---|
| `spec.py` | frozen declarative types: `WorkUnit`, `FanOut`, `Barrier`, `Pipeline`, `Workflow`, `ReceiptSpec` |
| `validate.py` | the closed 28-id violation set over a `Workflow` |
| `envelope.py` | `status` / `summary` / `next_actions` / `artifacts` + the error path's three recovery fields |
| `taxonomy.py` | the closed failure vocabulary every lane matches on (+ `family` for policy branching) |
| `argv.py` | `build_argv` / `build_for_rail` / `RailSpec` — the prompt never reaches argv |
| `oracle.py` | **the completion AND-gate** — the most important function here |
| `receipt.py` | decode / parse / schema / forbidden-marker checks |
| `progress.py` | `ResultText` vs `ProgressLog` — a progress stream cannot become a result |
| `terminal.py` | `SUCCESS:<id>` / `FAILED:<id> <reason>` |
| `retry.py` | `win-arg-limit` retries once; `rate-limited` backs off, bounded; nothing else |
| `dispatchpolicy.py` | no fire-and-forget on an awaited dispatch; no implicit timeout |
| `budget.py` | an immutable, monotonic, no-double-count ledger; `cost_per_success` |
| `clock.py` | the injected `Clock` / `SteppableClock` ports (deliberately no `SystemClock`) |
| `determinism.py` | a static check over this package: no clock, no entropy |
| `testlint.py` | the assertion-density lint (anti-coverage-theatre layer 2) |
| `evals/` | the hermetic registry, the fake rail, the injected seam bundle, the live-lane filter |

## The completion oracle

`judge(unit_id, result, spec)` is a six-clause AND:

`exit-zero` → `receipt-present` → `receipt-non-empty` → `receipt-parses` → `receipt-schema` →
`receipt-content`

**Exit 0 is not proof of completion.** Exit 0 with a receipt that is missing, empty, unparseable,
schema-invalid, marker-bearing, or a progress stream is **SEVERED**, never SUCCESS. The verdict
carries *both* the fine cause (`reason`, for the operator) and `severed=True` (the family flag,
for consumers that match on `severed-stream`), so neither audience has to parse the other's
string.

`ReceiptSpec` must supply a non-vacuous content clause — `required_fields` for JSON,
`forbidden_markers` for text. `validate_workflow` reports `unit-receipt-clause-vacuous` **and
`judge` itself raises**, because a consumer that hand-builds a `ReceiptSpec` never goes through
a `Workflow` and used to lose the catch. Without the clause the gate silently reduces to
"exit 0 AND non-empty", and a rail that exits 0 over `"work is still in progress"` reads as
SUCCESS — the progress-stream rule does not save it, since that string carries neither a
bracketed tag nor a background-job phrase. Both call sites share
`ReceiptSpec.is_vacuous()`, so they cannot drift.

## The two failure vocabularies in this repo — map, do not merge

`agentspec/taxonomy.py` is the vendor-neutral set for the SPEC layer.
`hooks/_shared/failure_taxonomy.py` is the pre-existing set for the hook / fan-in-barrier
layer, and it is **not** a duplicate implementation: `hooks/_shared/completion.py` judges
artifact size, sentinels and liveness across four states, while `agentspec/oracle.py` judges a
receipt against a schema across two. Complementary, and the hooks tree is deliberately
untouched by this package. What WOULD bite is a monitor grepping one string set against the
other, so:

| this package | hooks/_shared | note |
|---|---|---|
| `rail-exit-<n>` | `codex-exit-<n>` | same class; ours is vendor-neutral because a rail may be any vendor |
| `rate-limited-<status>` | `"429"` | same class; ours keeps the segment shape so `family()` recognises it |
| `severed-stream` | `severed-stream` | identical string |
| `win-arg-limit` | `win-arg-limit` | identical string |
| `schema-invalid` | `schema-invalid` | identical string |
| `timeout-<n>s` | `timeout` | ours carries the budget in the code |
| — | `unclassified` | absent here **on purpose**: this package's boundary functions REFUSE a non-member rather than bucket it, so an unclassified code cannot enter |

Retry policy agrees across both, with one deliberate difference in the ACTOR:

| reason | this package (`plan_retry`) | hooks (`HANDLERS`) |
|---|---|---|
| `win-arg-limit` | retry once, prompt off argv | `retry`, `max_retries=1`, `--ignore-user-config` |
| `rate-limited` | 6 attempts, doubling backoff, no jitter | `backoff`, `max_retries=5`, jitter |
| `severed-stream` | `retry=False` — **no AUTOMATIC retry** | `redispatch`, `max_retries=1` |

The `severed-stream` row is not a contradiction: `oracle._retry_instruction` does tell the
operator to "re-dispatch the SAME unit once". The difference is who decides — a runtime or a
human that has read the diagnostic tail, never this function looping on its own. Jitter is
absent here because it needs entropy and `determinism.py` fails this package's own source on a
`random` import; the transport shim adds jitter to the schedule agentspec returns.

## Running the gates

```bash
cd tools/agentspec
pip install -e ".[dev]"
pytest -m "not live" --cov=agentspec --cov-branch --cov-report=term-missing --cov-fail-under=100
basedpyright agentspec          # from this directory
```

The opt-in live lane (there are no live rows in this package today, only the mechanism and a
sentinel): `pytest --run-live`.

## Anti-coverage-theatre

100% coverage does not prove behaviour. Three layers, in order:

1. **`tests/test_mutations.py` — 28 mutants**, each required to turn its row RED, plus the
   unmutated state asserted green, plus a coverage assertion that the mutant set spans every row
   id, plus a blast-radius control (a mutant must not red an unrelated row).
1b. **Constant pins.** A mutant swaps a whole FUNCTION through the injected `Impl`, so it
   cannot reach a module CONSTANT. An adversarial reviewer measured that hole on 2026-07-26:
   raising `argv.MIN_SUBSTRING_SCAN_LEN` from `64` to `4096` disabled the third prompt-on-argv
   rule while the suite stayed at `366 passed` and coverage stayed at `100.00%`, because every
   fixture was DERIVED from the constant. Every threshold-shaped constant now carries a literal
   pin plus an absolute-length behavioural test — `WINDOWS_CMDLINE_CAP`,
   `MIN_SUBSTRING_SCAN_LEN`, `RailSpec.cap`, `RailSpec.prompt_transport`,
   `RATE_LIMIT_MAX_ATTEMPTS`, `RATE_LIMIT_BASE_BACKOFF_MS` — and R4 additionally exercises bare
   containment through the eval registry, so the same edit now reds 7 tests in 3 files and
   drops coverage to 98.64%.

   Reproduce the proof for any constant — there is no tooling to install, and the point is that
   the FULL gate command must go RED, not just one test:

   ```bash
   # edit the constant in agentspec/*.py, then:
   pytest -m "not live" --cov=agentspec --cov-branch --cov-fail-under=100   # must exit non-zero
   git checkout -- agentspec/                                              # restore
   ```

   Measured 2026-07-27 over 14 such edits — the two threshold directions, both `RailSpec`
   defaults, the printability check, vacuity at both call sites, the `family` hyphen boundary,
   the rate-limit ceiling, the backoff doubling, member-vs-whole-string matching, and the
   progress-rule over-reach: **14 RED, 0 survivors**, from a baseline of `406 passed,
   1 deselected` at `100.00%`.
2. **`testlint.py`** fails any `test_*` function with zero assertions, and runs over this
   package's own suite.
3. **No exclusion.** There is ZERO `# pragma: no cover` and no coverage `omit` in this package —
   `grep -rn "pragma: no cover" agentspec/` returns nothing. That is only achievable because the
   package is pure; a live transport shim legitimately needs one.

Every load-bearing "this is clean" assertion is paired with a **detector control** proving the
check fires on a known-broken fixture, and with an anti-over-reach control proving it stays
silent on the sanctioned path. A probe that is silent in both states measures nothing.

## For consumers

- **basedpyright cannot see a sibling editable install.** If your package imports `agentspec`,
  add `[tool.basedpyright] extraPaths = ["../agentspec"]` to your `pyproject.toml`. Do **not**
  rely on `pip install -e ../agentspec`: setuptools emits a `MetaPathFinder` plus a `.pth` whose
  entire content is an `import …; install()` statement, and basedpyright neither executes `.pth`
  code nor follows a finder. Measured 2026-07-26: 2 import errors with the editable install, 0
  errors non-editable, same tree, with a detector control proving the tool resolves
  site-packages normally.
- Reuse the taxonomy rather than inventing reason strings; `is_reason` is the boundary check.
- Emit the envelope from every adapter. `validate_observation` is cheap and catches the
  "error with no next step" anti-pattern.

---

## UNVERIFIED follow-up — cross-runtime byte parity is NOT buildable yet

**Out of scope for this package, deliberately, and this is why.** A JS runtime and a
cross-runtime byte-parity oracle were both considered and are explicitly excluded. Parity needs a
*specified canonical form* first, because Python and JS canonical JSON **provably diverge in 6 of
7 measured cases** under a naive "UTF-8, sorted keys, no insignificant whitespace" rule:

| case | Python | JS |
|---|---|---|
| integral float | `{"wall_s":1.0}` | `{"wall_s":1}` |
| `1e16` | `{"tokens":1e+16}` | `{"tokens":10000000000000000}` |
| `-0.0` | `{"d":-0.0}` | `{"d":0}` |
| non-ASCII (`café ✓`) | `{"s":"café ✓"}` | `{"s":"café ✓"}` |
| astral key sort | `{"":2,"😀":1}` | `{"😀":1,"":2}` — **order inverts** |
| `\x7f` | `{"s":"ab"}` | `{"s":"a\x7fb"}` raw |
| `1e21` | `{"n":1e+21}` | `{"n":1e+21}` — **agrees** (the detector control) |

Two further divergences compound it:

- **Integer-like object keys.** ECMAScript's `OrdinaryOwnPropertyKeys` enumerates canonical
  array-index keys first, in ascending numeric order, regardless of insertion order — so
  `JSON.stringify` **cannot** honour "keys sorted by UTF-8 byte order" for any key that is a
  decimal `< 2^32-1`. Measured: `{"a":3,"10":1,"2":2}` emits `10,2,a` from Python and `2,10,a`
  from JS. This is not fixable by a flag.
- **Line endings.** Python text-mode writes `\r\n` on Windows while node writes `\n`, so a byte
  diff of two bundles fails on this box for a reason Linux CI never sees.

**Mitigations this package already applies** (so the eventual parity work starts from a smaller
problem): every numeric wire field is an `int` (`wall_ms`, `budget_micro`, `timeout_s`,
`exit_code`), which deletes rows 1-3 outright; `budget.Ledger` refuses `float` and `bool` at the
boundary; and `evals/impl.canonical_json` is documented as PYTHON-side determinism only.

**Settling experiment before anyone builds the oracle:** write the canonical form as a normative
clause that (a) forbids floats, (b) mandates raw UTF-8 with only JSON-mandatory escaping, (c)
sorts keys by UTF-8 *byte* order via an explicit comparator on both sides — never a native string
compare, (d) forbids canonical-integer object keys entirely, and (e) writes bytes with an explicit
`\n`. Then build a shared conformance corpus with one fixture per row above, plus a top-level and
a nested integer-like-key case, and require both runtimes to reproduce it byte-for-byte. Adopting
RFC 8785 (JCS) instead is also sound, but it costs a Python implementation of ECMAScript's
`Number::toString`, which nobody has budgeted.

Until that clause exists, a "parity oracle" would either be impossible to pass or would pass by
normalising away the very fields it claims to compare.