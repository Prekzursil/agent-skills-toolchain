# Architecture Candidate — DISTRIBUTED WORKFLOW RUNTIME (`A5-R`)

**Unit:** `tournament/distributed-runtime` (Phase 3 — architecture tournament)
**Advocate position:** committed candidate, argued honestly, own costs exposed.
**Spec:** `_USER-PROMPTS.md:10769-10796` (Phase 3 — architecture tournament).
**Prior design consumed, not redesigned:** `13-ARCHITECTURE-CANDIDATES.md:466-538` (`A5`), anchor
gate `:117-137` (`§1`), hazards `:100-116` (`§0.3`), mechanism namespace `MECH-NN` `:1005-1008`.
**Measured against:** working tree at `HEAD = 833fb1ea`, which is `dc90d64a` **plus two commits**
(`36070a6f` "fix(ci): repair main", `833fb1ea` "fix(ci): stop tracking agent probe scripts").
The brief pins `dc90d64a`; every number below was read at `833fb1ea` and the delta is CI-only.
**Status:** MEASURED. 7 of 7 required sections written. Every count in this file was produced by a
named command in this session, not recalled.

---

## 0. What this architecture reuses, and what it replaces — read this first

**It replaces nothing. Zero Wave 1 files are edited, moved, or deleted.** `A5-R` is strictly
additive: it is a *reader* of Wave 1's control planes and a *writer* of Wave 1's receipt format.

**REUSED, unmodified — 411 files:**

| tree | count | measurement |
|---|---|---|
| `platform/schema/*.schema.json` | **9** | `ls platform/schema/*.schema.json \| wc -l` → 9 (the 8 Wave-1 schemas + `artifact-class-profiles.schema.json` from the substrate sibling) |
| `platform/lib/**/*.py` | **50** | `find platform/lib -maxdepth 2 -name '*.py' \| wc -l` → 50 |
| `platform/council/**/*.councilspec.json` | **117** | 48 protocols + 69 presets, `find platform/council -name '*.councilspec.json' \| wc -l` → 117 |
| `platform/registry/*` | **7** | 161 classified candidates across 5 shards + COVERAGE + METHOD |
| `command-center/schema/**` | **233** | 231 generated `$ref` shims + 2 meta docs |
| `command-center/WORK-UNIT-CATALOG.json` | 1 | `work_units[]` = **2,007**; the separate `items[]` = **103** (untouched) |
| `command-center/PHASE-GRAPH.json` | 1 | 21 phases, 46 edges (32 HARD / 14 SOFT), 13 allocation buckets |
| `tools/{agentrail,command-center,event-ledger,monitorcore,fanout-schema}` | 5 trees | existing dispatch, register, ledger, monitor, fan-in-schema machinery |

**ADDED — 12 files** (6 modules, 5 test modules, 1 schema). Enumerated in §1.6.
**Test baseline it must not break:** `475 tests collected in 2.34s`
(`cd platform/lib && python -m pytest -q --no-header --collect-only`). This independently
corroborates the substrate sibling's "475 passed" by a *mechanically different* route — collection
without execution. Two signals agree.

`A5-R` therefore does **not** silently discard Wave 1. It is the first consumer Wave 1 has ever
had, and that is its whole argument for existing.

---

## 1. DESIGN

### 1.1 The problem, stated as a measurement rather than a vibe

Wave 1 built a **contract layer** with no **runtime**. Concretely, at `833fb1ea`:

1. **There is no scheduler over the 2,007 units.** `command-center/DEPENDENCY-GRAPH.json` reports
   `node_count: 103, edge_count: 21`. Two independent signals show it covers the *wrong*
   collection: (a) 103 == `len(catalog["items"])`, not 2,007; (b) its generator
   `tools/command-center/catalog.py:153 build_graph()` calls `by_id()` → `items()` →
   `catalog.get("items")` at `catalog.py:131`. The 2,007 work units have **no** ordering artifact.
2. **`execution_substrate` is a populated declaration with no dispatcher.** All 2,007 units carry
   one of 4 values — `local-parallel 784 · local-serialized 565 · worktree-isolated 456 ·
   cloud-batch 202` — and `work-unit.normative.schema.json#/$defs/execution_substrate` closes the
   enum at 8 values *"so a runner has a closed set to dispatch on"* (its own `$comment`). No runner
   reads it. 202 units are declared for cloud batch with `mcp__cloud-hub__modal_sandbox_*` /
   Databricks permissions and nothing dispatches them.
3. **The receipt format already declares the runtime's own observability contract.**
   `platform/schema/receipt.schema.json` carries `$defs` named `scheduler_report`,
   `concurrency_report`, `resume_report`, `cache_report`, `monitor_report`,
   `fault_injection_report` — **42 units** already point at those six fragments. Each `$ref`s
   `#/$defs/generic_report` = `receipt_core` + `report.kind` + `observations` (`minItems: 1`) + an
   explicit both-states control reference, and each is `const`-pinned by
   `artifact-class-profiles.schema.json` (verified: `schema_resolver.resolve(...).report_kind_pinned
   is True` for all six). **The runtime's output contract was written before the runtime.**
   *(Detector note: my first probe read only `properties`/`required` on those defs and printed them
   as EMPTY. That was an artifact of reading the wrong keyword — they are `{"$ref": ...}`. I raw-dumped
   them and corrected before writing. A format check that does not cover `$ref`/`allOf` composition
   produces confident false negatives.)*

So the gap is not "we need a workflow engine". It is: **Wave 1's contracts have no evaluator that
walks the whole catalog, so nothing can tell you what is runnable, what is done, or what is stuck.**

### 1.2 The anchor, and why the obvious design is banned

`13-ARCHITECTURE-CANDIDATES.md:117-121` states the anti-overfit anchor: an option counts only if it
rides the existing hook/skill/MCP bus and reintroduces **none** of — a 2nd orchestration runtime, a
vector-DB/KG memory, a **durable-execution engine**, a trained critic, observability SaaS, a
guardrail framework. The `§1` table verdict for A5 is *"**PASS only as A5-compliant**; A5-naive is
anchor-**REJECTED**"*.

I accept that ruling and do not re-litigate it. **Temporal / Restate / Prefect are out.** `A5-R` is
the compliant form of `13:493` — *"the run record IS the durable log"* — advanced from a
`workflow-authoring` convention (which is all it could be in August) to a real evaluator over the
2,007-unit catalog that now exists.

### 1.3 The core inversion

> **A unit is complete iff `completion_predicate.evaluate()` returns a satisfied verdict on its
> receipt. Not when the agent returns. Not when the file exists.**

Everything else follows. There is no run database, no broker, no queue, no daemon. Run state is
**derived on every tick** from the receipt tree, which means a crash costs nothing but a re-derive
and there is no second source of truth to drift. `platform/lib/completion_predicate.py` (12
conditions, `REDUCER_ID = "platform/lib/completion_predicate.py@v1"`, 65 tests, 12/12 mutations
killed with an independent control) is the evaluator. It already exists. `A5-R` is the loop that
calls it 2,007 times.

This is also the answer to hazard **H-h, untyped silence** (`13:74-78`, the anchor hazard for the
whole lane): a unit that dies at the orchestrator boundary leaves **no receipt**, and "no receipt"
is a *typed absence* in a derived-state model — it is simply not in `satisfied`. It cannot be
mistaken for success, because success has exactly one representation and it is a file that passes a
12-condition gate.

### 1.4 Scheduling: the two-level design, and the mechanism I had to throw away

I first proposed compiling the 1,004 bucket-level dependency edges down to unit-level edges by
joining `PHASE-GRAPH.allocation_buckets.buckets[].feeds_phases` against the catalog's `phase` field.
**I measured it and it is catastrophic.** `_probe_dr_acyclic.py`, three graphs over the same 2,007
nodes, with an injected-3-cycle control that fires (`detector_fires_on_known_broken: true`):

| graph | edges | acyclic | orderable | unschedulable | frontier @ t0 | depth |
|---|---|---|---|---|---|---|
| **G1** unit-id edges only | 2,644 | **true** | 2,007 | 0 | **489** | **19** |
| G2 bucket → catalog `bucket` field | 14,335 | false | 1,934 | 73 | 443 | — |
| G3 bucket → `feeds_phases` join *(my proposal)* | 246,406 | false | 194 | **1,813** | 25 | — |

My own mechanism leaves **90% of the catalog unschedulable**. It is REFUTED, by measurement, before
shipping. The design consequence is the real contribution:

**Bucket edges are phase-level constraints and must not be expanded to unit level.** They are
already expressed by `PHASE-GRAPH`'s 46 edges. But "discard them" is only defensible if the
discard is lossless, so I classified all 1,004 against the transitive closure of the phase DAG
(`_probe_dr_bucketedge.py`, with a reachability control):

| class | edges | share | disposition |
|---|---|---|---|
| **REDUNDANT** with phase order | **795** | 79% | safe to drop silently |
| **SAME-PHASE** intra-phase constraint | **141** | 14% | information the phase DAG *cannot* express (e.g. 89 × `phase 0 → B01`, and B01 itself feeds phase 0). Dropping these is **lossy** — must be REPORTED |
| **CONTRADICTS** phase order | **68** | 7% | e.g. 24 × `phase 11 → B13`, where B13 feeds only later phases. A measured catalog **defect** — this is the source of the G2/G3 cycles |

So the scheduler is **two-level, and the level split is forced by the data, not by taste**:

* **Phase level** — order from `PHASE-GRAPH.json`: 21 nodes, 32 HARD + 14 SOFT edges, hard critical
  path `0→1→2→3→4→7→7A→10→11→14→15` (11 phases, 10 hard edges).
* **Unit level** — order from **G1** only: acyclic, 19 levels deep, 489 units ready at `t0`.
* **Bucket level** — *not scheduled*. Classified, reported, and for the 68 contradictions, raised
  as a defect. Never silently absorbed.

### 1.5 Substrate binding, and a data-loss hazard the catalog currently declares

`execution_substrate` becomes a real dispatch table. But one binding cannot be honoured as written:

**601 of the 784 `local-parallel` units also hold `Edit` or `Write`** (`_probe_dr_scheduling.py:
shared_checkout_mutation_hazard`). That is 601 units declared to mutate **one** working tree and
**one** git index concurrently. This is the exact failure the estate has already paid for —
`feedback_parallel_agent_worktree`: file-disjoint agents share one git index and a broad `add`
sweeps siblings.

`A5-R` therefore **force-promotes** `local-parallel ∧ mutating → worktree-isolated` at plan time,
emits the promotion count in the `scheduler_report`, and never silently honours the unsafe
declaration. Promotion is a *report*, not an edit: the catalog is not rewritten.

| declared substrate | units | bound to |
|---|---|---|
| `local-parallel` (non-mutating: 183) | 183 | in-process pool, shared checkout, read-only tools |
| `local-parallel` (mutating: **601**) | 601 | **promoted** → `git worktree add`, promotion logged |
| `local-serialized` | 565 | a single lane, one at a time |
| `worktree-isolated` | 456 | `git worktree add`, honoured as declared |
| `cloud-batch` | 202 | `mcp__cloud-hub__modal_sandbox_*` / Databricks via the existing MCP bus |

### 1.6 Concrete file layout — the 12 new files

```
platform/lib/runtime/
  state.py       PURE. receipt tree -> {satisfied, failed, missing}. Calls completion_predicate
                 .evaluate() + receipt_schema_gate.evaluate_full(). Memoised on receipt sha256.
  schedule.py    PURE. (catalog, PHASE-GRAPH, state) -> Frontier. Builds G1, refuses on the 41
                 invalid dep tokens, classifies the 1,004 bucket edges, force-promotes the 601.
  lease.py       The ONLY mutable shared state: one O_CREAT|O_EXCL file per unit under
                 command-center/receipts/_leases/<unit-id>.lease  {pid, host, expires_utc}.
                 3 syscalls. No daemon, no broker.
  substrate.py   PURE mapping: execution_substrate -> a launcher descriptor + tool allowlist.
  dispatch.py    THE IMPURE SHELL. Ports/Protocol-based, modelled on and delegating to
                 tools/agentrail/agentrail/runner.py. Real disk, real clock, real spawn.
  cli.py         python -m runtime {plan|status|run|resume|explain <unit>}
  test_state.py  test_schedule.py  test_lease.py  test_substrate.py  test_dispatch.py
platform/schema/
  run-manifest.schema.json    the ONE new schema (schemas 9 -> 10)
```

**Control planes stay singular** — the spec's condition for a hybrid winner
(`_USER-PROMPTS.md:10796`). `A5-R` introduces **no new control plane**:

| plane | file | owner | `A5-R` role |
|---|---|---|---|
| unit definitions | `command-center/WORK-UNIT-CATALOG.json` | Wave 1 | read-only |
| phase/bucket order | `command-center/PHASE-GRAPH.json` | Wave 1 | read-only |
| artifact contract | `platform/schema/ARTIFACT-CLASS-REGISTRY.json` + `schema_resolver.py` | substrate sibling | read-only |
| completion truth | `command-center/receipts/**` | the units themselves | derived-from |
| trace | `tools/event-ledger/ledger.py` | existing | append |
| view | `tools/monitorcore/` | existing | unchanged |

### 1.7 Why `tools/agentrail` is the single biggest reuse

`tools/agentrail/agentrail/runner.py:1-19` documents itself as *"THE IMPURE SHELL — the only module
that binds a real disk, a real clock, a real process"*, with `LocalFileSystem` / `MonotonicClock` /
`SubprocessSpawn` behind Protocols and a `dispatch()` that is *"pure-with-ports, so the whole
resolve → plan → spill → spawn → receipt → judge sequence is testable end to end against fakes"*.
It already imports `agentspec.argv.ArgvTooLong` — i.e. it already handles the Windows 32,767-char
`CreateProcess` limit that `rules/common/cross-vendor-dispatch.md §3` records as having killed two
real Codex runs. `A5-R`'s `dispatch.py` is a thin adapter onto that, not a new spawner.

---

## 2. COST AND COMPLEXITY ANALYSIS

### 2.1 Build cost

| item | estimate | basis |
|---|---|---|
| `state.py` | ~180 lines | wraps two existing evaluators |
| `schedule.py` | ~320 lines | G1 build + Kahn + bucket classifier + promotion + refusal |
| `lease.py` | ~90 lines | `O_CREAT\|O_EXCL`, expiry, reap |
| `substrate.py` | ~110 lines | 8-value table + tool allowlist |
| `dispatch.py` | ~260 lines | ports adapter onto agentrail |
| `cli.py` | ~140 lines | 5 subcommands |
| **new production Python** | **~1,100 lines** | — |
| tests (to the estate's both-states standard) | **~1,500 lines** | 5 modules; ratio matches Wave 1 (2,152 lib lines → 112 councilspec tests) |
| 1 new schema | ~120 lines | `run-manifest.schema.json` |

Confidence *likely* (55-80%) that ~1,100 lines is within ±30%. The falsifier is cheap: build
`state.py` + `schedule.py` first (§5 step 1) and compare.

### 2.2 Run cost — the number that decides whether any of this is worth it

`_probe_dr_scheduling.py`: declared `timeout_seconds` sums to **2,291 hours**. Phase-ordered span,
worst case (every unit burns its full timeout), units within a phase at concurrency *c*:

| concurrency | span (h) | span (days, 24/7) |
|---|---|---|
| 1 | 2,291.0 | 95.5 |
| 5 | 462.9 | 19.3 |
| 10 | 235.8 | 9.8 |
| 20 | 124.5 | 5.2 |
| 50 | 63.1 | 2.6 |
| 100 | 49.5 | 2.1 |

Timeout distribution: min 900 s, p50 3,600 s, p90 7,200 s, max 14,400 s, 12 distinct values, 0
missing. Two readings of this table matter:

* **The distribution argues FOR distribution.** 1 → 20 concurrency buys an 18.4× reduction. That is
  the entire economic case, and it is the case the 202 `cloud-batch` units were declared for.
* **Returns collapse after ~50.** 50 → 100 buys only 1.27×, because the phase DAG serialises 21
  phases and the widest phase has 295 units. Fan-out-LARGE (50-100 agents) is *not* rewarded here;
  the ceiling is the phase graph, not the worker count. Anyone promising 100-way speedup on this
  catalog is selling the wrong axis.

### 2.3 Complexity added, stated as things that can now break

1. A **derived-state recompute** that is O(units) predicate evaluations per tick. The predicate does
   sha256 over artifacts (`completion_predicate._sha256_of`); at 2,007 units this is not free.
   Mitigated by memoising on receipt sha256 — but the memo is now a cache, and caches lie.
   **UNVERIFIED: the per-tick recompute cost.** Settling experiment: generate 2,007 synthetic
   receipts and time `state.derive()` cold and warm; if cold exceeds ~10 s the tick must become
   incremental, which is a materially different design.
2. **Leases** introduce a distributed-systems failure class the estate does not have today (§3).
3. **1,021 receipts land in one directory** — `command-center/receipts`, the largest of **32**
   distinct output directories. Directory enumeration and `git status` both degrade at that fan-out.
   Output paths themselves are safe: 2,007 units → **2,007 distinct `output_path` values, 0
   collisions** (measured).
   *(Correction against my own first draft: I initially wrote "12 output dirs", which was a
   `most_common(12)` slice misread as a total. The real count is 32. Reporting the head of a
   truncated histogram as a population count is the same scope error this program has already paid
   for three times.)*
4. **Two consistency obligations** the codebase does not have yet: promotion decisions must be
   stable across runs, and the bucket-edge classification must not drift when `PHASE-GRAPH` changes.

### 2.4 What it costs to *not* build this

Zero of the 2,007 units can currently be dispatched, ordered, resumed, or reported on. Wave 1's
475 tests prove the contracts are internally consistent; nothing proves they are *executable*. That
is the definition of green-not-live, which is `failure_classification` value #1 in the catalog's own
`defaults` block.

---

## 3. FAILURE-MODE ANALYSIS

| # | failure | trigger | detection | mitigation | residual |
|---|---|---|---|---|---|
| **F1** | **Partial artifact that validates.** A unit dies mid-write leaving a receipt that passes all 12 conditions but describes work that did not happen. | crash between artifact write and completion | predicate `c3` min-size, `c8` negative-controls, `c11` manifest | write-temp + atomic rename; `c2` digest match | **NOT CLOSED.** This is `13:530-534`'s own named hole. `A5-R` narrows it; it does not eliminate it. A schema-valid lie is still a lie. |
| **F2** | **Duplicate dispatch.** Lease expires while the unit is alive-but-slow; a second worker claims it. | timeout mis-set (p90 = 7,200 s; a hung unit looks identical) | two `produced_by` values for one `unit_id` | heartbeat-renewed lease (`renew` on ledger append), not fixed TTL | mtime/heartbeat cannot distinguish *stalled* from *long-completed* — `bash-hud-and-terminal-emit.md §3`. Duplicate dispatch is **detectable after the fact, not preventable**. |
| **F3** | **Clock skew** across local + Modal + Databricks makes lease expiry incoherent. | any `cloud-batch` unit | `timestamps` block in `receipt_core` (required) | leases are **local-only**; cloud units get a token in the run manifest instead of a lease | cloud-batch concurrency is capped by the dispatcher, not leased. Weaker guarantee, stated. |
| **F4** | **Cycle blocks the run.** G1 is acyclic *today*; a catalog edit can break it. | any dependency edit | Kahn on every `plan`; the injected-3-cycle control proves the detector fires | `plan` refuses on `acyclic == false` and names the SCC | none — refusal is correct |
| **F5** | **41 invalid dep tokens** (`ARC` 19, `WFA` 17, `CC` 4, `IMP` 1) across 40 units. | present **now** | `dependency_token` pattern + G1 build | `plan` **refuses**, does not warn | the 40 units are unschedulable until the catalog is fixed. Correct, and it makes the defect blocking instead of decorative. |
| **F6** | **68 contradictory bucket edges** silently absorbed, producing a wrong order. | present **now** | the classifier in §1.4 | reported as a defect class, never scheduled | requires a catalog fix or an owner ruling |
| **F7** | **141 same-phase bucket edges dropped**, losing real ordering. | present **now** | classifier | reported with the 89 × `phase 0 → B01` majority called out | **lossy by construction.** Honest disclosure, not a fix. |
| **F8** | **Phase 16 never runs.** `PHASE-GRAPH.allocation_buckets.FINDING_unfunded_phase` — verdict `CONFIRMED`: phase 16 (self-improvement loop) is the only one of 21 with no allocation bucket. The catalog does hold 12 phase-16 units. | at run end | frontier reports phase 16 with 12 units and no bucket funding | surface it; do not silently zero it | the closed loop stays unfunded until an owner decision |
| **F9** | **Force-promotion is wrong for some of the 601.** A unit that legitimately needs the shared tree gets a worktree and fails. | promotion | per-unit `FAILED:<id>` with `substrate-promoted` reason | opt-out field, owner-reviewed | promotion trades a data-loss risk for a correctness risk. I take that trade deliberately: data loss is unrecoverable, a failed unit is a retry. |
| **F10** | **Memo cache staleness** → a stale `satisfied` marks an incomplete unit done. | receipt rewritten with identical sha256 (practically impossible) or a memo keyed on path not content | memo key **is** the content digest | low |
| **F11** | **The 2,048 vs 2,007 gap.** `PHASE-GRAPH` declares 2,048 bucket-funded units; the catalog has 2,007. 41 units of declared work have no unit. | at plan | frontier reports both totals | report the delta | coincidentally equal to the 41 invalid dep tokens. **UNVERIFIED whether these two 41s are the same 41** — settling experiment: intersect the 40 units carrying invalid tokens with per-bucket funding deltas. I did not run it; do not assume they are related. |

---

## 4. SECURITY REVIEW

1. **Receipts are untrusted data.** They are agent/tool output, so AGENTS.md §9 applies: the resume
   path **parses, never executes**. `13:513` states this for A5-compliant and it is binding. No
   `eval`, no dynamic import from a receipt, no shelling out on a receipt field. `state.py` is pure
   and takes only `json.loads` output.
2. **`tool_permissions` becomes an enforcement boundary, not a comment.** 85 distinct permission
   tokens, max 15 per unit. Today they are advisory strings; `substrate.py` passes them as an
   **allowlist** to the launcher. This is a security *improvement* over the status quo, but it also
   means a typo in a permission string now silently under-permits a unit — the run must report
   `permission_denied` distinctly from `unit_failed`.
3. **The 601 force-promotions are a security control, not only a correctness one.** Concurrent
   mutation of one git index is how sibling work gets swept into another agent's commit. Promotion
   to a worktree removes the shared-index write surface for 601 units.
4. **Cloud-batch crosses a trust boundary.** 202 units dispatch through `mcp__cloud-hub__modal_*` /
   Databricks. Two hard rules: (a) **no credential may be forwarded into a unit prompt or a
   receipt** — the dispatcher passes a substrate handle, and the MCP server holds the credential;
   (b) a receipt returning from a sandbox is *more* untrusted than a local one, and it must go
   through the same 12-condition predicate with no waiver. Per AGENTS.md §9, `A5-R` never rotates,
   revokes, or edits any credential; a failing credential is reported by variable name and scope.
5. **Leases carry `{pid, host, expires_utc}` and nothing else.** No secrets, no tokens, no paths
   outside the receipt root. A lease file is world-readable by design; it must therefore never
   become a channel for anything but liveness.
6. **Prompt-injection surface.** A unit's `question_or_target` and `inputs` are catalog-authored, so
   they are trusted-ish; but a unit that *reads* a fetched artifact and writes a receipt that a
   later unit reads creates a transitive path from fetched content into a scheduling decision. The
   scheduler must therefore key **only** on `state`, `sentinel`, `unit_id`, and digests — never on
   free-text receipt fields. This is a real constraint on `state.py` and it is easy to violate.
7. **Path containment.** Every `output_path` must resolve under the repo root. The estate has
   already shipped a `StartsWith`-style containment bug (`ensure_within` sibling defect,
   2026-07-30); `A5-R` must use resolved-path `is_relative_to`, and its test must include the
   `../` and symlink cases.
8. **No new network listener, no new daemon, no new port.** `A5-R` adds zero attack surface of that
   kind. Contrast `A5-naive` (Temporal), which adds a server, a datastore, and a UI.

---

## 5. MIGRATION DESIGN FROM TODAY'S STATE

Five steps. Each is independently revertible by deleting files. **No step edits a Wave 1 file.**

**Step 1 — `plan` only, read-only, no dispatch (`state.py` + `schedule.py` + `cli.py plan`).**
Lands the frontier report: G1 acyclicity, 489-unit `t0` frontier, 19 levels, the 41-token refusal,
the 1,004-edge classification (795/141/68), the 601 promotions, the phase-16 funding gap, and the
2,048-vs-2,007 delta. **Value delivered with zero execution risk**, and it is the step that proves
or kills the rest. Revert = `rm -r platform/lib/runtime`.

**Step 2 — `run-manifest.schema.json` + `status`.** Adds the one schema (9 → 10) and a read-only
status view over the receipt tree. Wires `tools/monitorcore` as the view; monitorcore is unchanged.

**Step 3 — `lease.py` + `dispatch.py` restricted to `local-serialized` (565 units).** The safest
substrate first: one lane, no concurrency, no worktrees, no cloud. This is where F1/F2 get their
first real measurement.

**Step 4 — `worktree-isolated` (456) + the 601 promotions.** Introduces `git worktree add`. Gated on
step 3 producing clean receipts. This is the step that must not be rushed: it is the one that
touches git.

**Step 5 — `cloud-batch` (202) behind an owner decision.** Crosses the trust boundary and spends
external quota. Explicitly **owner-gated**, consistent with the 144 units already carrying
`owner_approval_required: true`.

**Release mode.** Binding owner decision: PR-ONLY. `A5-R` ships as PRs; program stopping condition
13 ("release/canary succeeds") is treated as *a merged PR plus a local rollback rehearsal*, and I
am saying so explicitly rather than claiming a canary. The rollback rehearsal for `A5-R` is trivial
and should be executed, not asserted: delete `platform/lib/runtime/`, delete
`platform/schema/run-manifest.schema.json`, re-run the 475-test baseline, confirm 475.

**What migration does NOT require:** no catalog rewrite, no schema edit, no receipt-format change,
no data migration (there is no prior run state to migrate), no change to
`hooks/_dispatch/manifest.json`, no new MCP server, no change to the 117 councilspecs.

---

## 6. TEST DESIGN

The estate's standard is the **both-states control**: a check that is silent in both states measures
nothing. Every row below names the broken state the test must fire on.

### 6.1 Both-states matrix

| # | claim | GOOD state (must be silent) | KNOWN-BROKEN state (must FIRE) |
|---|---|---|---|
| T1 | G1 is acyclic | real catalog → `acyclic: true` | inject a 3-cycle → detector reports `false` **(already run: control fires, `detector_fires_on_known_broken: true`)** |
| T2 | frontier is correct | 489 ready at `t0` | remove one satisfied receipt → its dependents leave the frontier |
| T3 | predicate gates completion | a valid receipt → satisfied | strip `spec_anchor` → rejected (`'spec_anchor' is a required property`) |
| T4 | invalid dep tokens refuse | 1,967 units plan | any of the 40 `ARC`/`WFA`/`CC`/`IMP` units in scope → `plan` exits non-zero naming the token |
| T5 | bucket classifier | 795/141/68 on real data | flip one `feeds_phases` entry → an edge moves class |
| T6 | promotion fires | 601 promoted | set a unit to `local-parallel` + `Edit` → promoted; remove `Edit` → not promoted |
| T7 | lease is exclusive | 1 holder | two processes race one unit → exactly one `O_EXCL` wins |
| T8 | lease expiry reaps | live lease survives | expire the clock → reaped, and the reap is *logged*, never silent |
| T9 | substrate table is total | all 8 enum values map | add a 9th value → `plan` refuses (no silent default) |
| T10 | path containment | in-repo path accepted | `../escape`, absolute, and symlink-out → all rejected |
| T11 | memo is content-keyed | rewrite receipt content → recompute | rewrite with identical bytes → memo hit |
| T12 | resume dispatches zero agents for done phases | re-run a completed phase → **0** dispatches (`13:519`'s own benchmark) | delete one receipt → exactly 1 dispatch |

### 6.2 Mutation battery

Wave 1's predicate shipped **12/12 mutations killed with an independent control**. `A5-R` must match
on its own surface: ≥12 mutations against `schedule.py`/`state.py` — invert a comparison in Kahn,
drop the cycle check, default an unknown substrate instead of refusing, treat `UNSATISFIED` as
satisfied, key the memo on path instead of digest, drop the promotion predicate, silence the lease
reap log, accept an out-of-repo path, widen the token pattern, treat `NOT-CHECKED` as a pass, skip
`c12`, and short-circuit the frontier on the first ready unit. **Every one must turn the suite red.**
A surviving mutant is a hole in the tests, not a pass.

### 6.3 Anti-vacuity controls

* **Non-empty-input control.** The estate has shipped two benchmarks that measured EMPTY inputs and
  returned a clean, meaningless green (2026-08-07/08). Every `A5-R` test asserts the input cardinality
  it consumed (`assert len(units) == 2007`) so a suite over an empty catalog cannot pass.
* **Baseline non-regression.** `475 tests collected` before, `475 + N` after; the 475 must all still
  pass. `receipt.schema.json` must remain **byte-identical** (59 tests + a 22-mutation battery are
  pinned to it, per `artifact-class-profiles.schema.json`'s own `$comment`).
* **Lint parity.** `ruff` from the repo root (running it from `platform/lib` makes it report a path
  error that reads like a lint failure — recorded in `CONFORMANCE-STATUS.json`).

---

## 7. THE STRONGEST ADVERSARIAL REFUTATION OF THIS ARCHITECTURE

This is the load-bearing section. Here is the argument that would kill `A5-R` if it were true, in
its strongest form — not a strawman.

### 7.1 The refutation

> **The 2,007-unit catalog is not a program. It is a wish list. Building a scheduler for it is the
> most expensive possible way to discover that.**
>
> Look at what `A5-R`'s own measurements say about its input. 41 dependency references resolve
> nowhere. 68 bucket edges *contradict* the phase order. 141 more carry ordering the phase graph
> cannot express, and `A5-R` drops them and calls the loss "disclosed". 1,735 of 2,007 units carry
> no bucket at all, so 876 of the 1,004 bucket edges cannot be expanded from the catalog even in
> principle. `PHASE-GRAPH` funds 2,048 units against a catalog of 2,007. Phase 16 — the
> self-improvement loop, the whole point of the program — is funded with zero buckets. 601 units
> declare a substrate that would destroy data if honoured. 128 completion sentinels do not name
> their own unit; 159 output-schema references were unloadable until a sibling shimmed them.
>
> A scheduler over that substrate will spend its entire life reporting that its input is malformed.
> `A5-R` is proud of this — it calls refusal "correct". But an orchestrator whose principal output
> is a list of its own input's defects is a **linter wearing a runtime's costume**, and the linter
> costs ~150 lines while the runtime costs ~2,600 plus a lease protocol, a worktree lifecycle, a
> cloud trust boundary, and F1-F11.
>
> And the economics do not rescue it. 2,291 declared hours is 5.2 days at 20-way concurrency —
> for a program whose release mode is **PR-ONLY**, meaning nothing ships automatically at the end.
> The estate has no measured instance of wanting to execute 2,007 units. It has a measured instance
> of a **1,000-agent / 147.6M-token / 12.1-hour** audit that *died at the agent cap before
> synthesis*, where **42% of the 225 findings actually checked were REFUTED** while the agents
> self-rated "high" confidence on 89%. More throughput was not the missing ingredient there. More
> throughput was the *problem*.
>
> Meanwhile, the two failure modes the corpus actually measures — **fan-in schema rejection (22.7%)**
> and **agents dying at the orchestrator boundary with no error in their own transcript** — are
> named in `13:475-479` as the reason A5 was suspect in the first place. A scheduler fixes neither.
> Schema rejection is fixed by the schema work Wave 1 and the substrate sibling already did. Boundary
> death is fixed by write-as-you-go, which is a *prompt convention* costing zero lines.
>
> `13:530-534` — A5's own strongest-argument-against, written by the prior design — says it solves a
> problem the owner hits **once per program, not once per turn**, while competing for attention with
> H-h (untyped silence), which fires every turn. `A5-R` claims to answer H-h via typed absence. But
> typed absence is a property of **the receipt contract**, which already exists at
> `platform/schema/receipt.schema.json` with a 12-condition predicate and 475 green tests. `A5-R`
> does not create typed absence. It *consumes* it. Delete `A5-R` and typed absence survives intact.
>
> So: the valuable half of this architecture is a read-only report, and the expensive half is a
> capability the estate has never been measured to need.

### 7.2 Does it kill the design? Plainly: **it kills half of it, and that half is the expensive half.**

I am not going to defend the whole design against that argument, because the argument is largely
correct and I can point at the measurements that make it correct — most of them are mine.

**What survives, and why.** The refutation's own force depends on facts that **only exist because
something walked the whole catalog**. Nobody knew G1 was acyclic. Nobody knew the frontier was 489
wide and 19 levels deep. Nobody knew 601 units declared a data-loss substrate, or that 68 bucket
edges contradicted the phase order, or that the obvious bucket-join produces a graph where 90% of
units cannot be ordered. `DEPENDENCY-GRAPH.json` has been sitting in the repo reporting `node_count:
103` while the real graph is 2,007 nodes and 3,689 edges, and no gate noticed, because no consumer
existed. **`state.py` + `schedule.py` are that consumer, and they are ~500 of the ~1,100 lines.**

**What I concede.** `dispatch.py`, `lease.py`, `substrate.py` and the cloud-batch boundary — roughly
460 production lines plus F2, F3, F7, F9 and the entire distributed-systems failure class — are
**not justified by any measurement I can produce**. There is no measured instance of the owner
wanting 2,007 units executed. The 2,291-hour budget is a *declaration*, not a demand. I asked
whether it was a demand and it is not: release mode is PR-ONLY.

**Therefore my recommendation as advocate is narrower than my architecture:**

* **ADOPT** step 1 and step 2 — `state.py`, `schedule.py`, `cli.py plan|status|explain`,
  `run-manifest.schema.json`. ~500 lines, read-only, no lease, no spawn, no cloud, no git write.
  It closes the "Wave 1 has no consumer" gap, makes 4 measured catalog defects blocking instead of
  decorative, and cannot lose data because it writes nothing but a report.
* **DEFER** steps 3-5 (`lease.py`, `dispatch.py`, `substrate.py`, cloud-batch) behind an explicit
  owner decision, with the falsifying experiment named below. Do not build a dispatcher on a
  catalog that a planner has not yet certified.

**The experiment that settles it, and what each outcome means.** Run step 1 against the real
catalog and read the frontier report. If `plan` refuses — 41 invalid tokens, 68 contradictions, an
unfunded phase 16 — then the catalog is not executable, the refutation is CONFIRMED, and steps 3-5
must not be built until those are fixed. If `plan` emits a clean 489-unit frontier after the known
defects are repaired, then the dispatcher has a certified input and steps 3-5 become a cost
question rather than a correctness one. My prediction, band **likely (55-80%)**, evidence = the
four defect classes measured above: **`plan` refuses on first contact.** An advocate who predicts
his own architecture will refuse to run should say so before it does, not after.

**One place I hold my ground.** The refutation calls the planner "a linter wearing a runtime's
costume". I accept the shape of that and reject the dismissal: a linter that can answer *"what is
runnable right now, and what is the longest chain to the end"* over 2,007 units and 3,689 edges is
not a lint pass — it is the scheduler's pure core, minus the impure shell. Shipping the core and
withholding the shell is not a retreat from the architecture. It is the architecture with its
unjustified half honestly amputated, which is what a tournament is for.

---

## RESIDUAL — what this document does NOT establish

* **UNVERIFIED: the per-tick `state.derive()` cost** at 2,007 units. I did not build it. Settling
  experiment in §2.3. If it is slow, the tick becomes incremental and §1.3's "derive everything
  every tick" simplicity is lost — that would be a material design change, not a tuning knob.
* **UNVERIFIED: whether `PHASE-GRAPH`'s 41-unit funding surplus (2,048 − 2,007) is the same 41 as
  the invalid dependency tokens.** The numbers coincide; I did not intersect the sets. Do not treat
  the coincidence as a finding (F11).
* **NOT-CHECKED: the 96 completion sentinels that do not name their own unit, and the 128
  non-canonical `assigned_model_vendor_role` shapes.** I confirmed the 128 independently
  (`vendor_model` shows 128 `<non-dict:str>`), which corroborates the brief and acts as a control
  that my probe works; I did not analyse either defect's effect on dispatch.
* **NOT-CHECKED: a live run of anything.** No unit was dispatched. Every claim here is about the
  catalog, the schemas, and the existing libraries as they sit on disk at `833fb1ea`.
* **Scope of every count:** `command-center/WORK-UNIT-CATALOG.json` `work_units[]` (2,007) only.
  The separate `items[]` (103) was never touched, merged, or counted.

## EVIDENCE — commands and probes, all re-runnable from the repo root

```
git rev-parse HEAD                                        -> 833fb1ea0886a87a562be539a02839f8c6e6a6e4
ls platform/schema/*.schema.json | wc -l                  -> 9
find platform/lib -maxdepth 2 -name '*.py' | wc -l         -> 50
find platform/council -name '*.councilspec.json' | wc -l   -> 117   (48 protocols + 69 presets)
find command-center/schema -type f | wc -l                 -> 233
cd platform/lib && python -m pytest -q --no-header --collect-only | tail -1
                                                          -> 475 tests collected in 2.34s
python platform/architecture/_probe_dr_catalog.py          -> SUCCESS:dr-catalog-probe
python platform/architecture/_probe_dr_scheduling.py       -> SUCCESS:dr-scheduling-probe
python platform/architecture/_probe_dr_acyclic.py          -> SUCCESS:dr-acyclic-probe
python platform/architecture/_probe_dr_bucketedge.py       -> SUCCESS:dr-bucketedge-probe
```

The four `_probe_dr_*.py` scripts are the durable evidence and are re-runnable from a clean
checkout. Their frozen JSON outputs (`_probe_dr_scheduling_out.json`, `_probe_dr_acyclic_out.json`,
`_probe_dr_bucketedge_out.json`) exist in this directory on the authoring machine but are
**gitignored** by repo policy — `.gitignore:65` matches `**/_*_out.json`, per commit `833fb1ea`
*"stop tracking agent probe scripts — they are scratch, not deliverables"*. So a reader of the
committed tree must re-run the probes rather than read the frozen files; every number in this
document is reproducible that way, and none of it depends on an artifact that only exists locally.

Anchors: `13-ARCHITECTURE-CANDIDATES.md:466-538` (A5), `:117-137` (anchor gate), `:100-116`
(hazards), `:74-78` (H-h) · `_USER-PROMPTS.md:10769-10796` (Phase 3) ·
`tools/command-center/catalog.py:131,153` · `tools/agentrail/agentrail/runner.py:1-19` ·
`platform/lib/completion_predicate.py:62` · `platform/schema/work-unit.normative.schema.json`
`$defs/execution_substrate`, `$defs/dependency_token` ·
`platform/schema/receipt.schema.json` `$defs/generic_report` ·
`command-center/PHASE-GRAPH.json` `critical_path`, `allocation_buckets.FINDING_unfunded_phase`.
