---
title: BUILD-LOG
type: note
permalink: dqverify-repo-20261013/docs/workflow-sota/build-log
---

# WFSOTA BUILD LANE — implementation log (round 1)

> **WRITE-AS-YOU-GO SENTINEL.** If this file still reads "SKELETON — nothing measured yet"
> with an all-UNKNOWN table, the unit died before measuring anything and no verdict here may
> be cited. *(Sentinel cleared at milestone M1: the table below carries real measurements.)*

STATUS: **COMPLETE (round 1) — H6 shipped + red-proven, 4 lint rules landed, gate wired.**
STARTED: 2026-08-12
LANE: WFSOTA build, round 1 of at most 3.
FILE SCOPE: `tools/**`, `.agents/skills/workflow-*/**`, `docs/workflow-sota/**`
(scope note: the repo dual-writes every skill to BOTH `skills/<name>/` and `.agents/skills/<name>/`,
enforced by `ci/check_skill_dual_write.py`. Editing only the `.agents/` copy would break that gate,
so both copies of every `workflow-*` skill file are treated as one in-scope unit.)

## COVERAGE — what is measured vs unmeasured

| # | Claim | State |
|---|---|---|
| C1 | Prior plan located and cited (B2 §4 H1-H8, B3 W1.5) | **MEASURED — CONFIRMED** |
| C2 | `setTimeout`/`clearTimeout` really injected into the workflow sandbox | **MEASURED — 2 independent binary probes** |
| C3 | H6 helper implemented (`withTimeout` + `settle` + typed drop-receipt) | **MEASURED — SHIPPED** |
| C4 | H6 red-proof: un-wrapped barrier HANGS on a synthetic hung agent | **MEASURED — CONTROL FIRES** |
| C5 | H6 green-proof: wrapped barrier settles on survivors, 1 typed timeout receipt | **MEASURED — PASSES** |
| C6 | New lint rules land with BOTH-STATES fixtures (broken fires / fixed silent) | **MEASURED — 4 rules, all both-states** |
| C7 | Every new lint rule proven red on a known-bad input before being trusted | **MEASURED — red first, then green** |
| C8 | `workflow-authoring` SKILL.md corrected against the measured runtime | **DONE** |
| C9 | `workflow-foundry` upgraded (not a competing best-practices doc) | **DONE — L4b + L4c added in place** |
| C10 | Full pre-existing suite still green after the change | **MEASURED — 110 passed, 100% branch** |
| C11 | Dual-write parity (`skills/` == `.agents/skills/`) preserved | **MEASURED — 7 files byte-identical, gate OK** |
| C12 | Commit made with explicit paths only, no sibling files swept | **DONE — staged-path audit below** |

## EVIDENCE

### C1 — the plan exists; this lane implements it rather than re-planning

`docs/audit-design-2026-07-13/B2-RFC-operational.md:360-400` = §4 ORCHESTRATION ENGINE H1–H8,
with `H6 ★ = per-agent timeout + stall heartbeat (barrier-deadlock escape)` called "the single
highest-value orchestration fix" at `:381-386`.
`docs/audit-design-2026-07-13/B3-migration-verification.md:150` = wave item **W1.5**, effort LOW.
`:156` = the exit criterion, verbatim: **"H6 proven to break a synthetic barrier hang."**
`:262-263` = falsifiers #21 / #22 (`STALL_MS = 90 s`). All cited inside the shipped template.

### C2 — `setTimeout` in the sandbox, two mechanically independent probes

1. Grounding lane: fixed-OFFSET read of `claude.exe` at 267,627,551 / 267,593,463 →
   `setTimeout:y.setTimeout, clearTimeout:y.clearTimeout` in both VM context constructors.
2. THIS lane, offset-free: `docs/workflow-sota/_build_verify_runtime_globals.py` streams all
   287,053,472 bytes counting substrings with **no offset knowledge**, carrying a
   `CONTROL_must_be_zero` needle so a broken scanner cannot manufacture agreement. Result:

```
{"counts": {"doc_pipeline_sig": 1, "doc_default_to_pipeline": 1, "doc_parallel_barrier": 1,
            "vm_setTimeout_inject": 10, "vm_clearTimeout_inject": 5,
            "vm_codeGeneration_off": 3, "resume_from_run_id": 27,
            "CONTROL_must_be_zero": 0},
 "detector_control_ok": true, "all_real_needles_present": true}
```

### C3/C4/C5 — H6, and the both-states red-proof

Shipped: `skills/workflow-authoring/templates/h6-timeout-heartbeat.md` — the SINGLE source of
truth. There is deliberately **no** second `.js` copy for it to drift from; the test extracts
and executes the exact bytes an author pastes.
Executable proof: `tools/wf-timeout/{h6_extract.py, h6_harness.mjs, test_h6_timeout.py}`.
The harness runs the block in a Node `vm` context configured like the real sandbox
(`codeGeneration.strings=false`; `Date.now` / argless `new Date()` / `Math.random` shimmed to
throw; timers injected; `parallel` stubbed as a true barrier).

```
$ node h6_harness.mjs --source /tmp/h6.js --scenario unwrapped --timeout-ms 150 --watchdog-ms 1500
{ "scenario": "unwrapped", "hung": true,  "elapsedMs": 1507.9697, "parallelBarriers": 1,
  "settled": false }                                    <-- KNOWN-BROKEN CONTROL FIRES

$ node h6_harness.mjs --source /tmp/h6.js --scenario wrapped   --timeout-ms 150 --watchdog-ms 1500
{ "scenario": "wrapped",   "hung": false, "elapsedMs":  175.0593, "length": 5,
  "endReasons": [null, null, "timeout", null, null],
  "survivors": [0,1,3,4], "drops": [{"label":"u2","why":"timeout"}] }
```

TWO OF MY OWN DETECTORS WERE BROKEN FIRST. Both are recorded, not quietly fixed:

1. The watchdog timer was `unref()`'d. A never-resolving `new Promise(() => {})` does not hold
   the Node event loop open, so the process exited immediately and printed **nothing** — the
   harness was silent in the broken state, which is exactly the failure it exists to prevent.
   Fixed; the explanation stays as a comment at the fix site in `h6_harness.mjs`.
2. `test_helper_is_free_of_banned_nondeterminism` substring-scanned the raw block and FAILED on
   `Date.now` — which appears only inside the helper's own comment saying it does not use it.
   Use-vs-mention. It now scans `workflow_lint.mask_code(...)` (comment/string bodies blanked)
   and keeps a control asserting the mention IS in the raw bytes, so green means the mask
   worked rather than that the text is absent.

### The honest scope of H6 — an overclaim in the PLAN, corrected in the artifact

`B3:262` words falsifier #21 as the hung node being "timed-out and **killed**". `Promise.race`
cannot kill anything: the losing promise keeps running, holds one of the ~14 concurrency slots
(`min(16, cores-2)`), and keeps spending `budget` until it dies on its own. The shipped template
says **"dropped from the barrier; the agent keeps running and keeps its slot"** and names the
settling experiment (read `budget.spent()` at the timeout receipt and again at workflow end; a
rise proves it lived on). The plan's word is not reused anywhere in the artifact.

### C6/C7 — the four new lint rules, each both-states

| rule | level | broken fixture fires | fixed fixtures stay silent |
|---|---|---|---|
| `sandbox-forbidden` | ERROR | 6 (require / import() / static import / eval / new Function / process.*) | 4, incl. the same tokens as MENTIONS in a comment and a string (use-vs-mention) |
| `barrier-without-timeout` | WARN | bare `parallel(agent(...))` | 5: `withTimeout`, hand-rolled `Promise.race`, `settle()`, a barrier with no `agent(`, an unbalanced call |
| `prefer-pipeline` | WARN | the runtime's own smell test | 8, including **all three** shapes the runtime says a barrier IS correct for |
| `budget-loop-unguarded` | WARN | `while (budget.remaining() > N)` | 3, incl. the `budget.total &&` guard |

Also corrected: `args-parse-if-string` → **`args-unguarded`**. Its premise was measured FALSE —
the runtime tool doc says `args` is *"the value passed as Workflow's `args` input, **verbatim**
(undefined if not provided)"*. The rule now warns about the real footgun (absent args) and
names the stringified-caller case as the caller-side mistake it is.

And `parallel-filter-boolean` was widened: a `.map()` that NAMES `null` now counts as
null-tolerant, because typing a drop is *stronger* than deleting it. This was forced by
evidence — the rule fired on the H6 helper itself, and rather than reword the template's claim,
the rule was fixed, with its own both-states test.

### Yield against the real corpus, with a baseline control

```
$ git show HEAD:skills/workflow-authoring/scripts/workflow_lint.py > /tmp/wl_baseline.py
$ python /tmp/wl_baseline.py ~/.claude/workflows --json  ->  12  (11 agent-schema + 1 parallel-filter-boolean)
$ python workflow_lint.py    ~/.claude/workflows --json  ->  27  (+15 barrier-without-timeout)
```

**15 of 15** barrier calls across **10 of 10** saved workflows are unbounded — the new rule
catches 100% of the measured exposure, and NO pre-existing check changed. Note the grounding
lane recorded that baseline as "12 findings, all `agent-schema` warns"; re-measured here it is
11 `agent-schema` + 1 `parallel-filter-boolean`. Minor, but corrected rather than repeated.

`prefer-pipeline` fires **0** times on that corpus, so it is a prospective rule whose only
evidence today is its fixture; the SKILL.md table says exactly that rather than implying a catch.

Two real defects were found by the new rule *inside this repo* and fixed:
`templates/resume-wired-fanout.md` and `templates/governed-run-orchestrator.md` both fanned out
agents through a bare barrier.

### S1 (scope expansion, judged correct and built) — the linter had NO invoker

`workflow_lint.py` shipped with 110 tests and a 100%-coverage CI lane, and **nothing ran it over
any workflow source**. `tools/wf-timeout/wf_gate.py` is the invocation: it lints every fenced
`js` block under `skills/workflow-*/templates/*.md`, **fails closed on an empty walk**, and
carries `--self-test` proving it goes red on a known-bad block. 19 tests, including four that
deliberately break the self-test so the detector-of-the-detector is also proven.

### S2 (scope expansion, judged correct and built) — H3 typed drop-receipts

Built *with* H6, not after, because `settle()` would otherwise ship a silently-lossy barrier.
The runtime yields `null` for at least three distinct causes; `settle()` returns a typed
`{__endReason: 'timeout' | 'threw' | 'null'}` for each instead of a bare null.

### FULL VERIFICATION, final pass

```
skills/workflow-authoring/scripts  pytest --cov=workflow_lint --cov-branch --cov-fail-under=100
                                   -> 110 passed, 452 stmts / 216 branches, 100%
.agents/.../scripts                pytest -q                      -> 110 passed (mirror runs)
tools/wf-timeout                   pytest -q                      ->  39 passed
tools/wf-timeout/wf_gate.py --self-test -> SUCCESS (red on bad, green on clean, closed on empty)
tools/wf-timeout/wf_gate.py             -> SUCCESS 0 error(s), 1 pre-existing warning, 15 blocks
skills/workflow-authoring          pytest tests/test_governed_run_template.py -> 8 passed
ci/check_skill_dual_write.py       -> OK
ci/check_skill_context_budget.py   -> 5710/8000 trigger chars, rc=0
ruff check / ruff format --check   -> All checks passed / 10 files already formatted
```

## RESIDUAL / NOT DONE — honestly scoped

1. ~~**Not wired into `.github/workflows/quality.yml`.**~~ **CLOSED by the INTEGRATE lane** —
   superseded, see `docs/workflow-sota/INTEGRATE-LOG.md`. Left here rather than deleted so the
   round-1 record stays truthful about what round 1 shipped.
   *Round-1 text:* That file is outside this lane's declared
   file scope. The exact step is written out in `tools/wf-timeout/README.md`. Until someone adds
   it, the H6 red-proof and the gate run only when invoked by hand — which is the *same*
   no-op-gate defect this lane fixed for `workflow_lint`, now one layer up. Disclosed, not hidden.
2. **R6 (migrating the live `~/.claude/workflows` barriers to `pipeline()`/`settle()`) not done.**
   It mutates files outside the repo and belongs to the reconcile path. The lint now names all
   15 sites, so the work-list is mechanical.
3. **R5 (two competing resume mechanisms: rule 13 manifest vs native `resumeFromRunId`) not
   resolved.** Both are now documented in the corrected SKILL.md §1; neither was retired.
4. **`prefer-pipeline` has zero real-corpus catches.** Settling experiment: re-run
   `wf_gate.py --live` after R6 introduces multi-stage flows, or hand it the two multi-barrier
   workflows (`trainer-gui-mega-plan.js`, 5 barriers; `harness-self-improve-sweep-imporant.js`, 2).
5. **`setTimeout` availability is proven from the BINARY, twice, not from an executed workflow.**
   Band: almost-certain (90-99%). The harness proves the helper's *logic* under an equivalent
   `vm` context; it does not prove the shipping runtime injects the timer. The cheap settling
   experiment remains: a 3-line, zero-agent workflow returning `typeof setTimeout`. The helper
   ships a `typeof setTimeout !== 'function'` degrade path either way, tested by
   `test_helper_degrades_when_timers_are_not_injected`.
6. **`h6_harness.mjs` has no coverage instrumentation** — it is exercised end-to-end through
   `test_h6_timeout.py` (4 scenarios) rather than line-covered.
7. **The heartbeat is an observation, not a stall verdict.** `h6Heartbeat` reports "still waiting
   on X after STALL_MS". It cannot distinguish hung from slow; that needs orchestrator state the
   sandbox cannot see (S3: `journal.jsonl`, not `ls -lt`). Not built this round.