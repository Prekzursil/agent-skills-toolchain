# Lane WFSOTA — grounding notes (MEASURED)

Grounding lane, 2026-08-12. No production code written. Every claim below carries a
`file:line`, a binary offset, or an exact command + output. Sherman-Kent band on each verdict.

COVERAGE: prior-art located (DONE) · live-workflow census (DONE) · runtime API re-derived from the
installed binary (DONE) · `setTimeout` availability (DONE) · lint rule inventory + both-states
control (DONE) · external SOTA (PARTIAL — WebFetch is blocked on this box for non-Anthropic
domains, so external items are SEARCH-SNIPPET level, not fetched-and-read).

## 1. Prior art — the plan EXISTS. Do not re-plan.

| Artifact | What it is |
|---|---|
| `docs/audit-design-2026-07-13/B2-RFC-operational.md:360-400` | §4 ORCHESTRATION ENGINE **H1–H8**. `H6 ★ = per-agent timeout + stall heartbeat (barrier-deadlock escape)`, explicitly "the PRIORITY (G-6, G-9 Wave-1) … the single highest-value orchestration fix" (`:381-386`). |
| `docs/audit-design-2026-07-13/B3-migration-verification.md:150` | Wave item **W1.5** = H6, effort **LOW (helper)**. |
| same `:156` | Exit criterion: **"H6 proven to break a synthetic barrier hang."** That is the red-proof gate. |
| same `:262-263` | Falsifiers #21 (per-agent-timeout) and #22 (stall-heartbeat, **STALL_MS = 90 s**). |
| same `:195` | W3.2 = the rest: H1 budget sub-pools · H2 HITL · H3 typed drop-receipts · H4 settled `parallel()` · H5 role-tiered routing · **H7 `workflow_lint` stage-0 (SHIPPED)** · H8 bounded loop. |
| `docs/axis-c-design-2026-07-13/research-sota-cross-vendor-orchestration.md` | 33 KB external SOTA already done 2026-07-13, with an explicit anti-overfit anchor: ride native `agent()/parallel()/pipeline()`, build no second runtime. |
| `skills/workflow-foundry/SKILL.md:129-143` | **L4 Pipeline-by-default** already written and correct, incl. the measured caveat that `pipeline()` is not a cacheable resume unit. |
| `skills/workflow-authoring/scripts/workflow_lint.py` | H7 already shipped: 5 checks, 111 tests green in 1.24 s. |

**H6 is NOT shipped.** `grep -rn "withTimeout|raceTimeout|timeoutAfter"` over the repo → 0 hits.
`STALL_MS` appears only in `skills/workflow-monitor/workflow_monitor.py` (observation, not escape).
*(almost-certain 90-99%)*

## 2. Live state — measured, 2026-08-12

`python docs/workflow-sota/_probe_lint_bothstates.py` over `C:/Users/Prekzursil/.claude/workflows`:

| metric | value |
|---|---|
| saved workflows | 10 |
| `parallel(` barrier calls | **15** |
| `pipeline(` calls | **0** |
| `agent(` calls | 38 |
| `.filter(Boolean)` | 19 |
| `Promise.race` / `setTimeout` / `AbortController` | **0 / 0 / 0** |
| resume-manifest wired | 1 of 10 (`plan-gate.mjs`) |
| `workflow_lint` findings | 12, all `agent-schema` warns |

Every fan-out on this box is a bare barrier with no timeout. *(almost-certain)*

## 3. The runtime, re-derived from the installed binary

Source: `C:/Users/Prekzursil/.local/bin/claude.exe` (287,053,472 bytes). Read-only chunked scan.

- Tool doc block @ **offset 269,022,808** → dumped to `RUNTIME-API-DUMP.txt`.
- VM context construction @ **offset 267,627,551** (top level) and **267,593,463** (child
  `workflow()` path) → dumped to `RUNTIME-VM-DUMP.txt`.

Injected globals are **eight**, not three: `agent`, `parallel`, **`pipeline`**, `phase`, `log`,
`args`, `budget`, `workflow` (+ `console`, `setTimeout`, `clearTimeout`).

**`setTimeout` and `clearTimeout` ARE in the sandbox.** Top-level literal, verbatim:

```
Fkn.createContext({__proto__:null, log:…, phase:…, console:m, budget:h,
                   setTimeout:y.setTimeout, clearTimeout:y.clearTimeout},
                  {codeGeneration:{strings:!1,wasm:!1}})
```
`y = kNp(abortSignal)` — an abort-aware timer pair that clears all pending timers on abort.
**Therefore H6 (`Promise.race` + `setTimeout`) is implementable in-script today.**
*(almost-certain 90-99% — two independent sites, top-level and child, both inject it.
Settling experiment: a 3-line, zero-agent workflow returning `typeof setTimeout`.)*

Other measured runtime facts:
- Runs under Node `vm` (`new Script(..., {filename:"workflow.js"})`); `import()` throws;
  `codeGeneration.strings=false` → no `eval`/`new Function`.
- `Date.now()` / argless `new Date()` / `Math.random()` are **shimmed to throw**, not merely
  discouraged. Exact messages at offset 267,582,347.
- `runInContext(h, TAt(30000))` → a **30 s SYNCHRONOUS** execution cap. It does NOT bound an
  awaited agent.
- `pipeline(items, ...stages)`: no barrier between stages; stage callbacks get
  `(prevResult, originalItem, index)`; a throwing stage drops that item to `null` and skips its
  remaining stages. Runtime's own words: **"DEFAULT TO pipeline()."**
- Concurrency cap `min(16, cores-2)`; this box has 16 cores → **14**. Lifetime cap 1000 agents.
- Native resume: `Workflow({scriptPath, resumeFromRunId})` replays the longest unchanged prefix
  of `agent()` calls from cache.
- `budget.total` is a HARD ceiling — `agent()` throws once `spent() >= total`.
- `args` is passed **verbatim as JSON**, not as a string.

## 4. Documentation drift in `skills/workflow-authoring/SKILL.md`

| line | says | actual |
|---|---|---|
| `:23` | "injects three globals — `agent`, `parallel`, `phase`" | eight (see §3) |
| `:63-66` | "args-as-string (the recorded gotcha) … **one single string**" | verbatim JSON |
| `:42` | effort `'low'\|'medium'\|'high'\|'xhigh'` | + `'max'` |
| `:120` | "Prefer `pipeline()`-style flows" (as a style) | `pipeline()` is a real global with a signature |
| — | no mention of `log()`, `budget`, `workflow()`, `resumeFromRunId`, `opts.phase` stage races | all real |

This drift is **already recorded** at
`skills/workflow-authoring/templates/governed-run-orchestrator.md:92` — known, never fixed.
The lint's `args-parse-if-string` rule (`workflow_lint.py:538-560`) teaches the same wrong fact.

## 5. Detector controls run

- `parallel-filter-boolean` both-states: fires on broken, silent on fixed → **DETECTOR-OK**.
- My own first probe reported `parallel-filter-boolean` in `broken_checks` while printing
  `fires_on_broken=false` — a self-contradicting output caused by asserting the wrong rule name.
  MY probe was the broken detector. Fixed and re-run.
- Baseline: `pytest skills/workflow-authoring/scripts/test_workflow_lint.py
  skills/workflow-authoring/tests/test_governed_run_template.py -q` → **111 passed in 1.24s**.

## 5b. The sharpest framing: timeouts are 100% SPECIFIED and 0% IMPLEMENTED

`platform/workflows/` holds **115 blueprints** in a validated DSL
(`platform/schema/workflow-dsl.schema.json`, validated + mutation-proved by
`platform/lib/wfdsl/`). Across them: **911 `timeout_seconds` fields and 35 `on_timeout`
handlers** (97 of 115 files mention a timeout).

`platform/workflows/shared-prod-shard-fanout-build.json` even records the incident verbatim:
*"chain 9's job was submitted with no job-level timeout and ran for 11 hours against a hung
unit."*

**There is no executor.** `platform/lib/wfdsl/` contains `validate.py`, `semantics.py`,
`expr.py`, `resolve.py`, `capabilities.py`, `mutations.py` — no compiler/emitter to runnable
Workflow JS. So 911 declared timeouts bind nothing, and the executable substrate
(`~/.claude/workflows/*.js`) has **0**.

Consequence for the build lane: do **not** build a DSL executor — that is the "second
orchestration runtime" the anti-overfit anchor bans
(`docs/axis-c-design-2026-07-13/research-sota-cross-vendor-orchestration.md:9`). Lift the H6
semantics *from* `per-unit-four-phase-pipeline.json` (`retry_policy` two-strikes-then-pivot,
`failure_policy.on_failure: continue` + `terminal_state_required` + `never_silent`,
`resume.granularity: fanout-item`) and implement them as a paste-in JS helper over the native
globals.

## 6. Scratch files in this directory

`_probe_*.py`, `_dump_*.py`, `RUNTIME-API-DUMP.txt`, `RUNTIME-VM-DUMP.txt`, `_*_out.json` are
read-only measurement scratch. The two `RUNTIME-*.txt` dumps are verbatim strings from a vendor
binary — useful locally, but the build lane should decide deliberately whether they belong in git
rather than committing them by reflex.
