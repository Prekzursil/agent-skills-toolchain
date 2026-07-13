# Ingest — Axis-B Workflow-Orchestration ENGINE gems (for folding into Axis-C)

**Subsystem:** `axis-b-engine`
**Sources (UNTRUSTED DATA — extracted, never executed):**
- `C:/Users/Prekzursil/.claude/gem-hunt-2026-07-12/ULTRACODE-HARNESS-SOTA-DECISION-QUEUE.md` (117 findings, 11 lenses)
- `C:/Users/Prekzursil/.claude/gem-hunt-2026-07-12/ULTRACODE-HARNESS-SOTA-GRILL-LOG.md` (converged decision log, 2026-07-13)

**Extraction date:** 2026-07-13
**Anti-overfit anchor (carried from Axis-C brief):** ride the EXISTING native Workflow bus (`agent()`/`parallel()`/`pipeline()`/`budget`/`journal`/`monitor`) + the mounted `mcp__codex__codex` rail. Prefer "author a reusable helper over the native engine" and "enable a native feature" over "build new infra". No 2nd orchestration runtime, no vector-DB/KG, no durable-execution engine, no trained critic.

---

## 0. The classification key (ground truth from the grill)

The grill log froze a **BUILDABLE-vs-RUNTIME SPLIT** that IS the [PATTERN] vs [SDK-GAP] answer. Every gem below is tagged against it:

- **[PATTERN]** = *author-buildable now* as a reusable helper/lint/scorer over the native `agent()`/`parallel()`/`pipeline()` bus. No Anthropic change needed. (Grill "AUTHOR-BUILDABLE now".)
- **[SDK-GAP]** = *needs a native Workflow feature we lack*; file as a design-doc / feature-request; the queue is the spec. (Grill "NEEDS ANTHROPIC".)
- **[OWNER-DECISION]** = one of the 5 genuine forks (D1–D5) or G-7, already **resolved** in the grill.
- **[HYBRID]** = an author-side approximation exists ([PATTERN]) but full fidelity needs the SDK ([SDK-GAP]).

**Empirically-verified harness fact (2026-07-13, test wf_1677bd4a-b61):** PreToolUse `_dispatch` hooks do **NOT** fire for Workflow-subagent tool calls (goal-reanchor hook fired 129× in the main loop, **0×** across 14 subagent transcripts). ⟹ **The hook route for subagent-boundary enforcement is CONFIRMED CLOSED.** Anything that must gate/observe a subagent's *tool calls* (D3 interception; runtime endReason; hard timeout) is therefore SDK-gated, not author-buildable. This is the single most load-bearing constraint for Axis-C.

---

## 1. The 8 cross-lens-convergent gems (H1–H8) — classified

| # | Gem | Lenses | Class | Rationale for the class |
|---|-----|--------|-------|--------------------------|
| **H1** | `budget.reserve()` scoped sub-pools + graceful **soft-exhaustion** (fence tokens for terminal synth/verify; stop the hard-throw that kills a run mid-fan-out) | 9–10/11 | **[HYBRID]** → [SDK-GAP] core + [PATTERN] approx | *Author-side* "budget-aware soft-reserve" (hold back a fraction in a closure, refuse dispatch, return your own sentinel) is buildable. But the gem's spec — **atomic pre-dispatch deduction** (closes the check-then-spend overshoot race in a 16-wide wave) and a true `{__status:'budget_exhausted'}` sentinel *replacing the harness hard-throw* — is harness-internal. Governed by **D2**. |
| **H2** | **HITL checkpoint / suspend-and-resume** — fixes "the harness cannot AskUserQuestion mid-workflow" | 6/11 | **[SDK-GAP]** | `WorkflowSuspend` must be a runtime-intercepted **sentinel above user code** (never a catchable Error, or a `try/catch` silently continues); needs a first-class `suspended` run state + label-keyed resume-with-input injection. Not author-buildable. Governed by **D3**. |
| **H3** | **Typed `endReason` / drop-receipt on every null** (`ok`/`threw`/`schema_invalid`/`budget_exhausted`/`stalled_timeout`/`empty_output`/`killed` + full error object) | 4–6/11 | **[SDK-GAP]** | The harness collapses threw/hung/schema-fail/budget-exhausted into one opaque `null` **before the author sees it**. Cannot be recovered author-side. (The `{envelope:true}` accessor is a pattern, but it only reads a reason H3 must first write.) |
| **H4** | `gather()` / **settled** `parallel()` — make the mandatory `.filter(Boolean)` drop visible | 4/11 | **[HYBRID]** → [PATTERN] best-effort + [SDK-GAP] fidelity | A best-effort `gather(thunks)->{ok,failed}` helper over `parallel()` (drop-count) is buildable **now**. The *reason-rich* `failed:[{label,reason}]` depends on H3; the **always-on barrier record** that even legacy `.filter(Boolean)` sites emit needs the harness. |
| **H5** | **Role-tiered model/effort routing defaults** — stop copying the session (top-tier) model to every fan-out worker | 2 direct / 4 w/ cascade | **[HYBRID]** → [PATTERN] per-call + [SDK-GAP] defaults | A `defaults({lead,worker})` + `route(role)->{model,effort}` helper threaded per-call is buildable now (this is also the **cross-vendor selector**, §5). Only the *automatic inheritance* (agent inherits its phase/role tier when the author omits it) is SDK-gated. "The single largest avoidable cost." |
| **H6** | **Per-agent timeout + native stall heartbeat** — escape the barrier-deadlock (a hung, not-thrown agent stalls the whole `parallel`) | 2 direct; most-cited footgun | **[SDK-GAP]** | No author-side way to race a hard timeout against an in-flight subagent **and cancel it** (nesting `parallel`/`agent` inside a thunk is a one-level violation; orphaned subagents keep burning tokens; `Date.now`/timers banned for determinism). The native `{type:'stall',idleMs}` heartbeat needs the runtime (wfmon only INFERS stall from mtime today). |
| **H7** | `workflow_lint.py` **stage-0 (SHADOW, exit 0)** — mechanically enforce the honor-system checklist before a token is spent | 3/11 | **[PATTERN]** | Stdlib AST/regex lint of the `.js`, modeled on `plan_lint_stage0.py`. Flags: `parallel(` not `.filter(Boolean)`'d, schema-less fan-in, `additionalProperties:false` drift, `Date.now()`/`Math.random()`, mutator lacking `isolation:'worktree'`, nesting>1, **ungated irreversible verb** (the buildable half of D3). Fully author-side; optional pre-save hook. |
| **H8** | **Bounded `loop()` / `refineUntil()`** convergence primitive (cap + stall + external-signal check) | 3/11 | **[PATTERN]** | `loop(stepFn,{until,maxIters=5})` / `refineUntil(produce,check,{maxRounds=3,repair,onExhaust})` — a plain JS loop over sequential `agent()` calls; count tracked in a local var (replay-stable). Helper **enforces** that `check()` is a separate agent/tool external signal (a prose "are you sure?" is a proven placebo); budget is the backstop. |

**Class tally:** pure [PATTERN] = **H7, H8**; pure [SDK-GAP] = **H2, H3, H6**; [HYBRID] = **H1, H4, H5**.

---

## 2. The 5 owner decisions (D1–D5 + G-7) — RESOLVED verdicts

All are **[OWNER-DECISION]**, and the grill resolved every one. Scope frozen at **G-1: MAXIMAL** (T0 + T1 + T2 + the self-improvement layer). The *thing each decision selects* carries its own downstream class:

| Dec | Verdict (frozen 2026-07-13) | Underlying artifact class | Guardrail |
|-----|------------------------------|----------------------------|-----------|
| **D1** resume cache | **FULL content-addressed + run-scoped dependency-graph.** `hash(prompt+schema+model+effort+agentType)` foundation; surgical resume (edit call #3 → re-run only #3 and its real descendants). Fall back to hash-key + opt-in `cacheKey` if the dep-graph balloons. | **[SDK-GAP]** (highest-complexity item) | dep-graph is **run-scoped**, NEVER a persistent cross-run workflow-state DB; gate on WORKFLOW_REPLAY stale-cache golden tests. |
| **D2** budget exhaustion | **SOFT-SENTINEL default** — starved `agent()` → journaled `{__status:'budget_exhausted'}`; completed work kept; reserved terminal synth/verify still runs. Hard-throw stays opt-in. | governs **H1** ([SDK-GAP] core) | MANDATORY loud `truncated:true` at top level + monitor RED banner + lint flags consuming a truncated result unchecked. |
| **D3** HITL depth | **BOTH** — checkpoint()/suspend queue **AND** branch-aware irreversibility interception (auto-suspend `push`/`merge`/`gh-release`/`deploy` to **PROTECTED refs only** — main/master/release — never local commits or scratch/feature branches). Closes the §6/§9 autonomous-push-to-main hole. | interception = **[SDK-GAP]** (canUseTool in the BACKGROUND runtime; **hook route CONFIRMED CLOSED**) | verb set tight + branch-aware to avoid approval fatigue. Author-buildable partial mitigations: (1) `workflow_lint.py` static-flags an ungated irreversible verb in a subagent thunk; (2) convention — background workflows **PROPOSE**, the hook-covered main loop **DISPOSES**. |
| **D4** verification | **HYBRID** — DEFAULT: receipt-typed `gate()` (control-flow gates require external receipts, not LLM opinion) + de-biased `panel()` (position-counterbalance + self-preference exclusion, ~free). OPT-IN: cross-vendor independence + N-sample consensus (force provisioning + K× cost). | mostly **[PATTERN]** (panel/gate/bestOfN are buildable helpers) + convention | SHADOW lint flags any gate on a single-sample/non-receipt/self-preferring verdict. |
| **D5** patterns surface | **INJECTED `patterns` global namespace** (thin, leaky-proof pass-throughs over `agent`/`parallel`/`pipeline`/`budget`) + `/new-workflow` scaffolder + `usesPatterns` auto-telemetry. Kills the ~80% plan-gate/design-gate duplication. | injected global = **[SDK-GAP]**; template/scaffolder = **[PATTERN]** substitute | keep helpers THIN so they don't leak `agent()` semantics. |
| **G-7** self-improve timing | **BOTH NOW (concurrent)** — `workflow_fitness.py` + `WORKFLOW_REPLAY` built alongside the primitives. | both **[PATTERN]** | WORKFLOW_REPLAY fixtures REGENERATABLE (`--update-fixtures`); `workflow_fitness` fail-open on schema drift; WORKFLOW_REPLAY stays a thin resume extension, never a production durable-execution engine. |

---

## 3. The tiered items (~50, deduped) by theme — with class tags

Tiers: **T0** cheap+high (just-do-it) · **T1** top gems · **T2** strong/nice-to-have · **PRUNE** rejected. Class = [P]attern / [S]DK-gap / [H]ybrid.

### (A) External-signal verification & quality
- **[T1][P]** Advisory-vs-receipt type split + `gate()` that only accepts receipts (evidence field required; monitor flags control-flow gated on non-receipt).
- **[T1][H]** `agent(){evidence}` journal-checked execution proof — inspects the agent's OWN journal toolCalls; demote if the required tool never ran. *(Reads harness journal → richest form is [S]; a best-effort convention is [P].)*
- **[T1][P]** `bestOfN()` / `selectByConsensus()` execution-consensus selector — executors emit typed receipts, **harness/helper** clusters by fingerprint, picks the largest **cross-vendor-agreeing** cluster. No LLM judge. *(cross-vendor engine — §5)*
- **[T1][P]** `consensus()` self-consistency w/ deterministic tie-break (needs the seeded RNG global).
- **[T1][P]** `panel()` diverse judge w/ position-counterbalance + self-preference guard (warn/reject if all judges share vendor+tier). *(cross-vendor engine — §5)*
- **[T1][P]** `verify()`/`adversarialVerify()` skeptic-panel (fresh refuters per claim; high-stakes-only).
- **[T1][P]** **Cross-vendor independence knob + correlated-verifier lint** — record author model+vendor+tier per result; warn/block when verifier shares vendor+tier. *(cross-vendor engine keystone — §5)*
- **[T1][P]** `redProof` + golden-oracle terminal pipeline stages (assert new tests FAIL on merge-base; deterministic postcondition probe).
- **[T2][P]** `synthesize(guard)` rubber-stamp / fidelity guard on fan-in (set-diff of dropped dissent).
- **[T2][P]** `assertNoRewardHack` diff-scan stage (net-new coverage-evasion on changed main-path files).
- **[T2][P]** Blind-verify gate-workflow (spec-derived tests, diff withheld).
- **[T2][H]** Resume-safe verification (revalidate-on-resume oracle; cache key carries content-hash). *(depends on the resume engine → [S] for the clean form.)*
- **[T2][P]** Judge-vs-receipt κ calibration ledger + auto-demote (a **statistic** over the journal, explicitly not a trained critic).
- **[T2][P]** Pairwise/pointwise protocol default + counterbalancing.
- **[PRUNE]** `debate()` primitive — dominated by consensus/bestOfN at equal budget.

### (B) API primitives & control flow
- **[T0][P]** Seeded deterministic `rng()` global (mulberry32/splitmix64, seeded by runId+call-index; replay-stable). *Unlocks consensus tie-breaks, judge-order de-bias, backoff jitter.*
- **[T1][P]** `mapReduce()` tree-reduce fan-in — kill the `JSON.stringify(...).slice(0,240000)` reducer corruption footgun; pass whole objects, hierarchical fold.
- **[T1][P]** Typed retry policy + typed `Result` (`{ok,value,error,attempts}`; **escalate effort/model, don't blind-repeat** — two-strikes).
- **[T1][P]** Assertion-driven self-refinement on schema/guard fail (re-invoke with the validator error appended; hard-capped).
- **[T2][H]** STOP/DONE per-item early-exit + `gate()` short-circuit *(exit condition restricted to external/mechanical signals; the clean sentinel is [S]).*
- **[T2][P]** Cap-aware auto-chunking for dynamic fan-out (auto-batch above `min(16,cpus-2)` / ≤4096 cap).
- **[T2][S]** `race()`/`firstSuccess()` early-cancellation — the biggest token lever ultracode lacks; **crux = clean cancellation of in-flight subagents (no orphans)**, unclear the runtime can do it today (§5 of the queue).
- **[T2][H]** Saga / compensation for worktree agents (rides existing worktree; compensations idempotent).
- **[T2][P]** Typed shared-state channel (blackboard) w/ **pure** reducer — ⚠ OK only if reducers are pure `(acc,delta)` and never persist across runs (else it's a KV store → reject).
- **[T2][P]** Supervisor progress-ledger + stall→replan (operationalizes two-strikes; cap total replans).
- **[T2][P]** Artifact handles + per-agent output-size cap — ⚠ run-scoped keyed scratch only; **reject any similarity-search/embedding version**.

### (C) Cost / budget / model-routing
- **[T1][H]** `budget.reserve()` sub-pools + soft-exhaustion **(H1)**.
- **[T1][H]** Role-tiered routing defaults **(H5)** — Anthropic multi-agent Opus-lead/Sonnet-worker = +90.2%.
- **[T1][S]** Resume × budget accounting semantics — cached-prefix replay charges 0 marginal, but `spent()` must report cumulative real spend from a persisted tally (reset-to-0 doubles the ceiling; count-cached refuses live work). Undocumented landmine.
- **[T1][P]** `cascade()` cheap-first escalation (FrugalGPT; `accept` should be an executable/typed check, not an LLM self-judge).
- **[T1][P]** `ladder(stages)` staged escalation (home for cheap-lint-before-N-Opus-reviewers).
- **[T2][P]** Triage-driven adaptive fan-out width (`scaleFanout`, Anthropic 1 / 2–4 / 10+ bands, clamp by budget/cap).
- **[T2][P]** Pre-flight cost preview at `parallel()` (additive telemetry).
- **[T2][P]** Cache-cliff detection telemetry (hash leading-K bytes of the shared prefix; SHADOW-warn the first diverging agent).

### (D) Observability & debugging
- **[T1][S]** Typed `endReason` + full error object on every null **(H3)**.
- **[T1][H]** `gather()`/settled `parallel()` + barrier record **(H4)**.
- **[T1][S]** Native per-phase token + cost + **cache-split** attribution (input/output/cacheRead/cacheCreation; obviates the bespoke transcript parser).
- **[T1][S]** Run status `degraded` + terminal close-out summary (a run that lost 1/8 agents is not "done").
- **[T1][S]** Capture schema-validation failure payload (`schemaErrors[]` + redacted `rejectedOutputPreview`) — makes the Codex `--output-schema`+MCP landmine VISIBLE.
- **[T0][S]** Stamp `label` + `phaseTitle` into journal/meta (journal keys agents by opaque hash today → O(1) recall). *Trivial but a harness field.*
- **[T1][S]** Native stall heartbeat event **(part of H6)**.
- **[T1][S]** `budget_exhausted` typed + `budget.byPhase()`/burn-rate/`projectedExhaustionPhase()`.
- **[T2][S]** Resume replay ledger (`replay:'cache_hit'|'reran'` per progress entry).
- **[T2][S]** Fan-out DAG edges (`parentAgentId`) + pipeline lineage breadcrumb (`lineage[]`, `droppedAtStage`) — "item 7 died at stage 3" is invisible today; also makes `criticalPathMs` exact.
- **[T2][P]** Opt-in OTel `gen_ai` span exporter — ⚠ pure SINK behind `WF_OTLP_ENDPOINT`; must no-op when unset; reject if it becomes the primary bus.

### (E) Human-in-the-loop & steering
- **[T1][S]** HITL checkpoint / suspend-and-resume keystone **(H2)**.
- **[T1][S]** First-class `suspended` run state (journal + manifest + wfmon "AWAITING YOU" lane).
- **[T1][S]** Deterministic resume-with-input channel (data, **label-keyed**; reject duplicate human-node labels at load time).
- **[T0][P]** Push notification + one-command resume link on suspend (existing `PushNotification` + /workflows; empty resume = idempotent re-suspend). *Author-buildable rail once suspend exists.*
- **[T0][P]** Schema-typed decision node (a human decision is a fan-in → obeys schema-on-every-fan-in).
- **[T2][S]** **Harness-default irreversibility interception → auto-suspend (D3)** — `canUseTool` parity at the per-agent tool gate; **hook route CONFIRMED CLOSED**.
- **[T2][P]** `askAll()` batched HITL barrier (independent decisions only; batch the human's scarce attention).
- **[T2][H]** Deterministic timeout/default policy (in-script literal default = replay-safe; wall-clock rides CronCreate/PushNotification OUTSIDE the sandbox; forbid a non-hold/escalate default on approval-class nodes).
- **[T2][P]** `flagForReview()` async adjudication queue (headless-safe substitute for AskUserQuestion; blocks PROMOTION to "done", not run progress).
- **[T2][S]** Restore shared budget + phase from journal on resume (depends on per-agent cost being journaled).

### (F) Authoring ergonomics & footguns  *(the T0 quick-win batch — ship first PR)*
- **[T1][P]** `workflow_lint.py` stage-0 (SHADOW) **(H7)**.
- **[T0][P]** Load-time HARD-FAIL on `Date.now()`/`Math.random()`/argless `new Date()` (AST-scan; foundation invariant for resume determinism + cache stability; near-zero false positives).
- **[T0][P]** Schema-builder global `S` (auto `additionalProperties:false`, derive `required[]`) — makes the two silent schema footguns impossible by construction.
- **[T0][P]** Ambient `.d.ts` + `//@ts-check` for the injected globals ("typed JS, no build"; flags `effort:'ultra'`, `isolation:'worktreee'` in-editor).
- **[T0][H]** Surface the null reason inline (auto-log + `{envelope:true}`) — the accessor is [P] but the *reason* it surfaces is H3 [S].
- **[T1][P]** Per-agent tool allowlist + **auto-strip MCP on schema'd agents (Codex landmine)** — schema-bearing calls DEFAULT to `disallowedTools:['mcp__*']`; at Codex+schema+MCP dispatch, disable MCP or force a Claude-side validate/repair. *(cross-vendor engine — §5)*
- **[T0][P]** Typed `args` accessor (`args.text`/`args.json(schema)`/`args.tokens`; named error on bad JSON).
- **[T2][P]** `--dry-run` simulator (stub `agent()`/`workflow()`; preview graph, cost, cap, nesting — the `terraform plan` of workflows).
- **[T2][P]** Structured delegation-prompt `task()` helper (4 delegation elements + goal re-anchor + mandatory "list gaps" self-critique; pass handles not blobs).

### (G) Patterns library & composability
- **[T1][S]** Inject a `patterns` global namespace **(D5)** — the no-import sandbox makes a namespace the ONLY real de-dup fix; template/scaffolder is the [P] substitute.
- **[T1][S]** `emit(channel,record)` deterministic journal global (append-only into harness-owned channels; harness stamps the replay-safe ts the sandbox bans). *Replaces prose-prompting an Opus agent to append JSON with Get-Date.*
- **[T1][P]** `panel()` collapses the duplicate gates (plan-gate/design-gate ARE the same code modulo the reviewer array).
- **[T1][P]** Refactor gates onto `panel()`+`gate()` + ship the missing post-impl adversarial review-gate (gates stay leaf-composable; parents call gates; gates never call gates).
- **[T2][P]** `tournament(candidates,compare)` bracket selection (`compare` REQUIRED execution-grounded).
- **[T2][H]** Typed sub-workflow contracts + **cached** composable sub-workflows (ship the caching = clearly good; depth>1 gated on manifest legibility). *(the caching/resume-boundary form touches the resume engine → [S].)*
- **[T2][S]** Propagate `WorkflowSuspend` through the `workflow()` nesting boundary (namespaced `<child>/<label>`; else HITL is unavailable in composed gates).
- **[T2][P]** Discovery: reach-for table + `usesPatterns` auto-telemetry + `/new-workflow` scaffolder.

### (H) Harness self-improvement
- **[T1][P]** `workflow_fitness.py` — per-`workflowName` roll-up + regression net over the `wf_*.json` manifests already on disk (run-count, success-rate, median/p95 tokens & duration, null-rate; ratchet a baseline; emit one PROPOSE line on regression). **G-7.**
- **[T2][P]** `WORKFLOW_REPLAY` deterministic bench (golden scenarios; serve every `agent()` from a fixture; assert invariants offline, zero tokens) — ⚠ thin resume extension, **reject** if it grows into a production durable-execution engine. **G-7.**
- **[T2][P]** `/workflow-shape` recommender (task text → typed shape + skeleton; bias with fitness history; advisory).
- **[T2][P]** Learn better defaults (effort/model/concurrency) — **SHADOW PROPOSE only**; ⚠ a statistic a human applies, **reject** an online trained router/critic.

---

## 4. CROSS-VENDOR ENGINE — which gems form it (integration_points)

Axis-C's core is: *any agent = Claude OR Codex, mingled, scoped per-call, one engine, uniform monitoring.* The gems that compose that engine (dispatch → route → observe → verify), all riding `agent()` + the `mcp__codex__codex` rail:

1. **H5 role-tiered routing = the vendor/model/effort selector.** The engine IS a `route(role)->{vendor,model,effort}` table; a Codex `agentType` routes the `agent()` call through the mounted `mcp__codex__codex` rail, a Claude role stays native. This is the per-call Claude-or-Codex scoping knob. **[PATTERN] now; [SDK-GAP] for inherited defaults.**
2. **Cross-vendor independence knob + correlated-verifier lint (A/T1)** = records `author.{model,vendor,tier}` on every result and warns/blocks when a verifier shares the author's vendor+tier. The keystone that makes cross-vendor *mean* independent-failures. **[PATTERN].**
3. **`bestOfN()` / execution-consensus (A/T1)** = selection by *cross-vendor-agreeing* cluster (an independent Claude candidate + an independent Codex candidate agreeing IS the signal; JudgeBench: model-opinion rerank ≈ chance). **[PATTERN].**
4. **`panel()` de-biasing (A/G, T1)** = cross-vendor judge diversity — exclude a judge from grading its own family, counterbalance order, surface disagreement. De-dupes plan-gate/design-gate. **[PATTERN].**
5. **Per-agent tool allowlist + Codex MCP-schema landmine guard (F/T1)** = the mingled-dispatch footgun handler — on Codex+schema+MCP dispatch, strip MCP for that call or force a Claude-side validate/repair (Codex #15451). The engine must *know the vendor* to apply it. **[PATTERN].**
6. **H3 endReason + H4 barrier record + H6 timeout/heartbeat = the uniform monitor substrate** that renders BOTH vendors identically and, folded with wfmon's manifest reads + the native `/workflows` UX, gives the "native-vs-ours-clearly-distinguished" monitor. **[SDK-GAP] core.**
7. **`emit()` + `label`/`phaseTitle` stamping = the single uniform journal channel** both vendors write into (append-only, harness-stamped ts). Uniform observability across the mingle. **[SDK-GAP] for the native global; [PATTERN] as an author helper.**

*Dispatch mechanism note:* the engine reuses the native `parallel()` barrier for fan-out and the `mcp__codex__codex` MCP tool as the Codex arm — **no new orchestration runtime**. Routing (H5) + the Codex-guard (5) are the only vendor-aware surfaces; everything else is vendor-agnostic and already on the bus.

---

## 5. GAPS — what native Workflow cannot express today

The SDK-gated residual (file as a design-doc / feature-request; the queue is the spec):

1. **Opaque null (H3).** `agent()` collapses `threw` / `hung` / `schema_invalid` / `budget_exhausted` / `killed` into one `null` before the author sees it — no typed `endReason` or error object; cannot be author-recovered.
2. **Barrier-deadlock: no per-agent timeout + no stall heartbeat (H6).** A hung (not-thrown) agent stalls the whole `parallel()`; no author-side race-and-cancel (nesting a thunk violates one-level; orphans keep burning tokens; timers banned); wfmon only INFERS stall from mtime.
3. **No HITL mid-workflow (H2).** No runtime-intercepted `WorkflowSuspend` sentinel, no first-class `suspended` run state, no label-keyed resume-with-input. The harness "cannot AskUserQuestion mid-workflow" today.
4. **Subagent tool boundary is unreachable by author code (D3).** **EMPIRICALLY VERIFIED:** PreToolUse hooks do NOT fire for Workflow-subagent tool calls → branch-aware irreversibility interception needs Anthropic's `canUseTool` in the BACKGROUND runtime. A background workflow can `push`/`merge` to main unattended today (a §6/§9 hole). *(Also gates any "observe/gate a subagent's tool calls" feature.)*
5. **Coarse positional resume cache (D1).** Native resume is longest-unchanged-prefix; a one-line edit to an early agent busts everything downstream — no content-addressed hash, no surgical re-run of only real descendants.
6. **No harness-inherited role/tier defaults (H5).** Per-call routing is buildable, but agents cannot *inherit* a phase/role tier automatically — the session (top-tier) model silently copies to every fan-out worker.
7. **No injected stdlib in the no-import sandbox (D5).** A maintained `patterns.*` namespace can only be a real de-dup fix if the harness injects it; the author's substitute (template/scaffolder) is copy-paste and drift-prone.
8. **Budget internals (H1 + resume accounting).** No atomic pre-dispatch deduction (check-then-spend overshoot race in a wide wave); no soft-exhaustion sentinel replacing the hard-throw; cached-prefix replay's `spent()` semantics (0 marginal but cumulative real) are undocumented and broken (reset-to-0 doubles the ceiling).
9. **No native per-phase / cache-split attribution.** Flat `tokens` only — no input/output/cacheRead/cacheCreation split (high cacheCreation = busted cliff), no per-phase cost, no `label`/`phaseTitle` on journal records (opaque-hash keying).
10. **No `degraded` run status or terminal close-out summary.** A run that lost 1/8 agents still reports "done"; no golden-signals rollup.
11. **No clean in-flight cancellation.** Blocks `race()`/`firstSuccess()` (the biggest token lever) and clean timeout-reclaim — orphan subagents are the open question.

---

## 6. Anti-overfit guardrails carried forward (maximal scope = highest sneak-in risk)

- dep-graph (D1) **run-scoped only** — never a cross-run workflow-state DB.
- learned-defaults (H-tier) **PROPOSE-only** — no online trained router/critic; the declarative stage-role default (H5) is the on-bus substitute.
- artifact-store / blackboard-channel **run-scoped, no embeddings, pure reducers** — the moment either persists across runs or adds similarity search, it's the KV/vector-DB line → reject.
- OTel exporter = **passive opt-in sink** — no-op when unset; never the primary bus.
- WORKFLOW_REPLAY = **thin resume extension** — never a production durable-execution engine authors depend on.
- `patterns` helpers stay **leaky-proof thin** — forward raw opts, return typed objects, don't leak `agent()` semantics.
- `debate()` **PRUNED** (dominated by consensus/bestOfN at equal budget).

**Next step (from the grill, not part of this ingest):** turn the [PATTERN] layer into a real implementation plan (WU decomposition, per-item design + tests) → plan-review gate → build; AND package the [SDK-GAP] residual as a design-doc/feature-request to Anthropic. A grill is not a build; this ingest is not a build.
