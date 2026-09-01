# Grill Closure Research — Unresolved Decisions G-12 … G-21

**Date:** 29.08.2026
**Lane:** quick deep-research (targeted, non-repeating)
**Scope:** the ten unresolved items of the Cursor Automation Suite decision queue only (`AUTOMATION-SUITE-DECISIONS_2026-08-29.md` lines 85–94). G-1 … G-11 are RESOLVED and are not re-opened here.
**Mode:** read-only research. This is the only file written. No other file was created or modified. No commit.
**Output contract:** every item is classified **DERIVED** (answerable from existing evidence or current official documentation, with a recommended decision) or **OWNER-CHOICE** (no evidence can select between non-equivalent options; one concise question is formulated).

## Inputs read

- `AUTOMATION-SUITE-DECISIONS_2026-08-29.md` — decision queue, G-1 … G-11 resolutions, verified baseline.
- `LONG-HORIZON-CLOSURE_2026-08-29.md` — completion contract, lanes L1–L5, hard boundaries.
- `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md` — 20 graded sources [S1]–[S20], state model, evidence-record schema, bounded-parallelism limits.
- `PERPLEXITY-BLUEPRINT-REVIEW-FEASIBILITY_2026-08-29.md` — FAIL, 13 blockers, 15 improvements, 7 new NOT-CHECKED items.
- `PERPLEXITY-BLUEPRINT-REVIEW-COMPLETENESS_2026-08-29.md` — FAIL, 12 blockers, 9 majors, census OK 24 / ENUM 9 / SKELETON 7.
- `PERPLEXITY-BLUEPRINT-REVIEW-SCOPE_2026-08-29.md` — PASS, 0 blockers, 3 enhancements.
- `PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md` — targeted reads only (§5.2 budget/locality fields, §12.3 BR-1, §20 P5, §23 open-decision table, per-workflow budget lines). Not re-read in full; the two review gates above are the authority on its defects.
- Standing estate contract: `AGENTS.md` (verification doctrine, estate locks 27–28.08.2026), `CLAUDE.md`.

## Fresh probes measured today (29.08.2026)

| Probe | Result | Bears on |
|---|---|---|
| `acpx` on PATH | **Absent** (`Get-Command acpx` → no result) | G-12, G-20 |
| `acpx` npm registry | **Exists: 0.13.2**, MIT, `openclaw/acpx`, published 2026-02-17, updated 2026-08-28, ~930k weekly downloads, 38 dependents | G-12 |
| `acpx flow run` contract | Real. Executes a caller-supplied TypeScript workflow module through the `acpx/flows` runtime; **persists run artifacts under `~/.acpx/flows/runs/`**; per-step default timeout 15 min; flows declare permission requirements and fail fast before starting; no built-in flow registry | G-12, G-18 |
| `acpx` session semantics | Per-session **queue owner process** with local IPC, one-at-a-time drain, idle TTL 300 s; cooperative `session/cancel` via queue-owner IPC; auto-resume tries `session/resume` then `session/load` then falls back to `session/new` | G-12, G-17, G-18 |
| LangGraph durability modes | Current official docs (JS **and** Python) document `durability: "exit" \| "async" \| "sync"`; `sync` writes each checkpoint before the next step; `recursionLimit`, `interruptBefore/After`, `maxConcurrency`, SQLite/Postgres checkpointers | G-12 |
| Free physical RAM | **2.18 GB** of 31.63 GB | G-19, G-20 |

Two facts that change the G-12 analysis relative to the feasibility review: `acpx` is not a speculative dependency (it is a maintained, widely-used MIT package, merely not installed here), and it **already ships a checkpointing flow runtime** — which the blueprint never accounts for. Separately, LangGraph exists in **TypeScript** with the same durability API as Python, so a graph layer does not force a Python process boundary.

## Freshness of the source base

Only the `acpx` and LangGraph facts above were verified today. Everything cited as [S1]–[S20] is inherited from `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md`, where it was graded A/High and deep-read; it is reused, not re-verified, in line with the "do not repeat broad research" instruction. No claim below rests on a source graded below A- except the two multi-agent empirical papers [S19]/[S20], which are explicitly labelled Medium.

---

# Decision matrix

| ID | Item | Class | One-line disposition |
|---|---|---|---|
| G-12 | Workflow engine: acpx-only / LangGraph layer / LangGraph isolated leaf | **DERIVED** (High) + 1 residual | Isolated leaf behind a written engine interface; acpx owns ACP sessions/turns, orchestrator owns admission/budget/ledger. Residual: leaf implementation (LangGraph.js vs minimal in-house cyclic runner). |
| G-13 | Autoresearch boundary: which metrics and repositories qualify | **OWNER-CHOICE** | No evidence can pick the owner's target repos or optimization metrics. |
| G-14 | Local/cloud split | **DERIVED** (High) + 1 residual | Default `local-only`; egress only after classification + redaction; PHI/SECRET never leave. Residual: may cloud-PHI consent ever be granted at all? |
| G-15 | Security boundary: defensive-only unattended vs owner-present dual-use | **DERIVED** (High) | Already implied by G-6 + estate locks; codify as a two-class table with a per-run authorization record. |
| G-16 | Browser policy | **DERIVED — already locked** + 1 residual | The 28.08.2026 estate lock already decides it; record as CLOSED, not "open". Residual: one shared agent-persistent profile vs per-domain profiles. |
| G-17 | Hook policy: deterministic hot-path only vs LLM hooks | **DERIVED** (High) | No LLM in any hook, ever. Two deterministic hook classes: blocking hard-boundary interlocks, and non-blocking bounded telemetry. |
| G-18 | Artifact and checkpoint schema | **DERIVED** (High) + 1 residual | One run directory per `run_id`; append-only ledger; provenance envelope per evidence item; acpx flow state is transport state only. Residual: filesystem location of the runs root. |
| G-19 | Budget policy | **SPLIT** | Semantics derived (per-run caps exist, visible fallback, abort ≠ pass, add non-terminal `DEFERRED_RESOURCE`). The **daily cap value and unit are OWNER-CHOICE**. |
| G-20 | Rollout sequence | **DERIVED** (Medium-High) + 1 residual | Keep P0→P7 but prepend a bootstrap/doctor phase and gate P4 on provider-credential preflight. Residual: suite build vs long-horizon closure priority. |
| G-21 | Acceptance criteria vs invoking skills directly | **SPLIT** | Head-to-head blinded A/B protocol is derivable. The **pass bar is OWNER-CHOICE**. |

Totals: **7 derived** (G-12, G-14, G-15, G-16, G-17, G-18, G-20 — of which 5 carry a narrow residual question and 2, G-15 and G-17, need no owner input at all), **1 pure owner choice** (G-13), **2 split** (G-19, G-21). Sum 10. Eight owner questions are formulated in the final section: the 5 residuals plus G-13, G-19, G-21.

---

# DERIVED decisions

## G-12 — Workflow engine

**Recommended decision.** Adopt the **isolated optional leaf**, and write the boundary down. Three components, no overlapping ownership:

| Concern | Owner | Evidence |
|---|---|---|
| ACP session lifecycle, per-session prompt queue, turn cancellation, session resume/load, permission mode, JSON event stream | **acpx** | Measured today: acpx implements exactly these (queue owner + IPC, `session/cancel`, resume→load→new fallback, `--format json`). ACP itself provides `session/load`, optional `session/resume`, `session/cancel` [S6]. |
| Run admission, global FIFO serialization, RAM guard, budget breaker, run ledger, run-level checkpoints, approval gates, artifact manifest | **`core/orchestrator/`** | G-1 (serial queue is the control plane), blueprint §19; acpx's queue is **per-session**, not a global admission queue, so it cannot serve this role. Temporal/LangGraph both put durable orchestration state outside the agent turn [S1, S4]. |
| Cyclic graph evaluation for the ~8–9 `graph.engine: complex` workflows (re-research loops, bounded recursion, interrupt/resume by thread identity) | **Graph leaf**, behind the engine interface | LangGraph documents `recursionLimit`, `interruptBefore/After`, thread-scoped checkpointers, and `durability: sync` per-step writes; acpx flows document per-step checkpointing but no cycle, recursion-bound, or interrupt/resume-by-thread semantics. |

Why not the alternatives:

- **acpx-only fails.** Its flow runtime persists run state under `~/.acpx/flows/runs/` and executes caller-authored TS modules, which is close — but it has no documented cyclic/bounded-recursion semantics and no interrupt-resume identity contract, and its state store is outside the estate run directory. Committing the suite's durable state to a third-party path also violates the G-18 requirement that task state be mechanically derivable from the estate's own ledger.
- **A LangGraph *layer* (LangGraph owning all 40 workflows) fails.** It would put queue, cancellation, budget, and approvals inside the graph library, re-creating the two-writers defect the feasibility review flags as BLOCKER-11, and would make the ~32 `simple` workflows depend on a graph engine they do not need. `SH-ARCH-6` already forbids the graph engine from touching the run store, ledger, approvals, queue, or breaker.
- **Isolated leaf is what the blueprint already built on** (§1.2, `SH-ARCH-4/5/6`, fail-closed `engine_unavailable`), so ratifying it costs zero rework, whereas either alternative invalidates §1.1, §19, and §20.

**Required repairs this decision unblocks (do not treat as separate decisions).**
1. Write **§1.4 Engine interface** with a concrete contract — `plan(definition, context) → NodePlan`, `step(context) → NodeResult`, `checkpoint() → Checkpoint`, `cancel(reason)`, an `abort_reason` enum — and the invariant that the engine may not touch run store, ledger, approvals, queue, or breaker. This closes **BLOCKER-11**.
2. Restore the word **LangGraph** to blueprint §23 (it appears zero times today; §23's own preamble forbids silent decision) and record the resolution.
3. Add to P1 exit criteria: `acpx` installed at a pinned version, `cursor-agent acp` handshake proven, Node ≥ 22.13 present.
4. Mark every `graph.engine: complex` workflow `blocked_until: DEC-G-12` until the leaf is delivered — this closes completeness **M9** item 3 and census item 5.
5. Rename the decision-log namespace to `DEC-G-nn` to end the collision with estate-lock `G-nn` (feasibility **I-04**): estate `G-12` is "Goose extensions HTTP-only", decision `G-12` is the engine. Both are cited as binding in the same document set.

**Confidence:** High for the boundary. **Residual owner question Q1** below covers the leaf implementation.

## G-14 — Local/cloud split

**Recommended decision.** Locality is a per-workflow declared field with a restrictive default, enforced at the capability boundary rather than by convention:

1. `execution.locality` defaults to **`local-only`**; `remote-allowed` must be declared in the definition and shown in the pre-run distribution preview (`SH-INT-5`).
2. **Data-class egress table** (one enum, see the interlock below): `PUBLIC`/`INTERNAL` may egress; `PII` egresses only after field-level redaction with a recorded redaction receipt; `PHI`/`FINANCIAL` and anything classed `SECRET` **never** egress and never appear in the run directory, ledger, or prompt.
3. **Credentials are never prompt material.** Environment-variable *names* may be referenced; values never. Adapters hold their own secrets. This is already `SH-TOOL-6` plus the estate NEVER-ROTATE lock.
4. **Memory is local by construction.** basic-memory is the sole semantic writer over `127.0.0.1:8765`; estate lock G-82 forbids cloud memory sync. Research/agent memory goes to `D:\Research` + basic-memory only.
5. **Browsers are a local lane.** Profile material stays owner-ACL'd and out of source control; authentication state is never written into receipts — only profile mode, browser version, and a redacted auth-probe result [S16].
6. **Files:** a workflow may read only its declared input paths and write only under its run directory plus the explicitly declared output destination. Negative tests (attempt owner paths, browser profiles, global MCPs, harness paths) are part of acceptance, exactly as L2 requires.

Evidence: `execution.locality` is already a required field (blueprint line 423); §11 classification exists; OWASP prescribes task-scoped, time-bound permissions and blast-radius controls for agentic tool use [S13]; NIST AI 600-1 requires access-mode inventories [S11]; estate locks pin memory locality and credential handling.

**Interlock:** this decision is unimplementable until the **single** data-classification enum is chosen — the blueprint currently carries two live taxonomies (`PUBLIC|INTERNAL|PII|PHI|FINANCIAL|SECRET` in §11.1 versus `P0–P6` in the source-risk matrix), which is feasibility **BLOCKER-06** and completeness **B1/B2**. Recommend adopting the source-risk matrix as the machine-readable SSOT and publishing a one-way mapping table in §11.1, because the catalog already uses matrix semantics in the workflow bodies.

**Confidence:** High. **Residual owner question Q2** covers cloud PHI consent.

## G-15 — Security boundary

**Recommended decision.** Two classes, declared per recipe, with an authorization record for the second:

| Class | Contents | Execution mode | Record required |
|---|---|---|---|
| **Defensive, unattended-eligible** | SAST/secret/dependency scanning of the owner's own code (`semgrep`, `bandit`, `trivy`, `gitleaks`, `lizard -C 15`), read-only static review, CI status monitoring, provider health probes, RAM/process guard | background via the single serial queue, or scheduled lightweight | run receipt only |
| **Dual-use, owner-present only** | Anything that can act against a system: `hexstrike`, `frida`, network scanning/enumeration, `ghidra`/`ida`/`binja` on third-party binaries, credential-bearing flows, live-profile browser, `git` writes/resets, autoresearch | interactive, owner present, never scheduled, never background | per-run authorization record naming the exact target, the owner's relationship to it, the time bound, and the requesting run_id |

This is not a new policy — it is the codification of G-6 ("owner-present only: autoresearch, git writes/resets, credential-bearing flows, live-profile browser, and dual-use security tooling"), blueprint §13 ("anything dual-use is owner-present-only"), the HOME behaviour floor (estate-local work authorized by default; refuse only hard-ban sub-parts — third-party attacks, stealer/C2, force-push, committing live secrets), and OWASP's action-level approval plus containment guidance [S13]. NIST SSDF's separation of human-readable review from executable testing supports keeping the defensive class fully automated [S12].

**Interlock:** the three declared-but-undefined safety controls `SH-SEC-PHI`, `SH-SEC-FIN`, `SH-SEC-IDENTITY` (feasibility **BLOCKER-03**, completeness **B8**) must be written as rule bodies with a trigger, an enforcement node boundary, the `SafetyDecision.control` value, and a deterministic gate ID. They are the enforcement points for the dual-use class in the health/finance/identity half of the catalog; without them this decision has nothing to bind to.

**Confidence:** High.

## G-16 — Browser policy

**Recommended decision.** **Record G-16 as CLOSED, not open.** The 28.08.2026 estate lock already decides it verbatim: mandatory per-run 3-way profile choice — (a) live/owner profile only as an explicit per-run override of G-90, (b) agent-persistent as the **default**, (c) agent-ephemeral — never silently pick (a). Blueprint `SH-SEC-BROWSER` BR-1 encodes it and the scope review confirms enforcement across every `browser.*` workflow. Playwright's official guidance independently requires a dedicated user-data directory, forbids automating the default Chrome profile, and forbids two instances on one profile directory [S16].

Two documentation defects worth fixing, neither a decision:

1. **G-16 is absent from blueprint §23 entirely.** So are G-18 and G-20. §23's preamble states these items "MUST NOT be silently decided", yet §16/§6 and §20 encode answers to G-18 and G-20 while the table omits them. Add all three rows with status CLOSED and a pointer to the deciding authority.
2. The remaining L4 items — pin Playwright MCP to an exact version, create the dedicated persistent headless profile, add a per-profile instance lock with stale-lock detection by process evidence, re-run the no-focus smoke — are implementation work, not decisions. The owner pause on browser automation stays `BLOCKED_HUMAN`; nothing in this research authorizes resumption.

**Confidence:** High (already locked). **Residual owner question Q3** covers profile granularity.

## G-17 — Hook policy

**Recommended decision.** **No LLM in any hook, in any class, ever.** Two deterministic hook classes:

| Class | Purpose | Blocking? | Budget | On failure |
|---|---|---|---|---|
| **Hard-boundary interlock** | Deny the estate's hard bans: committing secrets, `push --force`, credential rotation, CDP attach to the owner 1Password Chrome profile, writes outside declared scope, `agent worker start` under the RAM floor | **Yes, fail-closed** | ≤ 500 ms p95, pure local computation, no network, no model | the action is **denied**; the hook cannot "time out into permission" |
| **Observe / telemetry** | Ledger transitions, invocation records, digest capture, cost accumulation, drift notes | No | ≤ 200 ms p95, append-only write | log `FAILED_TO_RUN` for that telemetry item and continue; never fabricate a PASS |

All expensive reasoning — judges, councils, adversarial reviewers, evidence scouts — runs as **workflow nodes**, advisory, inside the graph, never as a hook. A model-based finding acquires blocking authority only through the G-11 route: an independent execute-to-confirm step that records a disk-verified receipt.

Evidence: blueprint §17.4 step 2 already assumes deterministic gates only and treats no LLM hook as a gate; `SH-APR-2` keeps LLM reviewers advisory; `CLAUDE.md` states the converged design ("deterministic safeguards as hooks/scripts and expensive reasoning as on-demand workflows"); the AGENTS.md Wave C doctrine gates enforcement hooks on Wave B's observe-mode latency evidence, i.e. latency is already the accepted deciding criterion; NIST SSDF separates automated checks from human-readable review [S12]; the MAST taxonomy and the scaling study both find that centralized deterministic verification contains error propagation better than distributed agent judgement [S19, S20]. The local RAM measurement (2.18 GB free) independently rules out a model call on any hot path.

**Confidence:** High. This item needs no owner input.

## G-18 — Artifact and checkpoint schema

**Recommended decision.** One run directory per run, one append-only ledger, one provenance envelope per evidence item. Concretely, per `run_id` (ULID):

```
<runs_root>/<YYYY-MM-DD>/<run_id>/
  manifest.json        # workflow id+digest, definition digest, resolved model/provider IDs,
                       #   intensity preset, locality, risk tier, idempotency key, final state
  ledger.jsonl         # append-only state transitions; one line per transition; atomic append
  invocations.jsonl    # two-phase: invocation.started before the call, invocation.finished after,
                       #   joined by invocation_id (closes feasibility I-05)
  sources/             # one SourceRecord per retained source
  verify/              # gate receipts: command, tool+model versions, exit status, output digest
  artifacts/           # outputs, each with size + SHA-256
  checkpoints/         # engine checkpoints, subject digest per checkpoint
  budget.json          # caps, consumed, breaker_state
```

Rules:

1. **Every evidence item carries the provenance envelope** from `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md` §2: `lane_id/step_id/attempt_id`, `subject_paths`, `subject_digests` (before/after), `inputs`, `executor`, `toolchain`, `invocation` (secrets redacted), `started_at/finished_at`, `result ∈ {PASS, FAIL, FAILED_TO_RUN, NOT_CHECKED}`, `artifacts`, `live_target`, `reviewer`, `provenance ∈ {cryptographically-attested, disk-verified, externally-verified, agent-claimed, not-checked, stale}`. Adapted from SLSA's subject/digest/builder/invocation model rather than copied [S10]; required by NIST's inventory and TEVV expectations [S11].
2. **State is a finite enum**, not prose: `PLANNED → READY → LEASED → RUNNING → VERIFYING → REVIEWING → READY_TO_APPLY → APPLYING → LIVE_VERIFYING → COMPLETED`, plus `WAITING_EXTERNAL`, `BLOCKED_HUMAN`, `FAILED`, `FAILED_TO_RUN`, `CANCELLED`, `STALE`, `ROLLING_BACK`, `ROLLED_BACK`, `REOPENED`.
3. **Review and test receipts are invalidated by subject-digest change** — the GitHub protected-branch stale-dismissal semantics, applied locally [S14].
4. **acpx flow/session state is transport state, referenced but never authoritative.** Measured: acpx writes its own run state to `~/.acpx/flows/runs/` and its own session records; the manifest may record those identifiers, but resume decisions are made from the estate ledger. ACP session resume restores conversation context and proves nothing about external side effects [S6].
5. **Resume is mechanically derivable**: reading `ledger.jsonl` plus `checkpoints/` must be sufficient to compute the next state without transcript reconstruction. Every mutating step carries a logical operation ID stable across retries; a new transport attempt must not create a new business operation [S2, S17].
6. **Deterministic render mode** for reproducibility: frozen clock injected via `RunContext.created_at`, seeded `run_id` derivation in test mode, and a normalization filter masking `run_id`, timestamps, durations, retry/fallback counters, and absolute paths before diffing. This closes feasibility **BLOCKER-08**: acceptance rows A4 ("byte-identical") and A11 ("same final artifact hash") are restated as byte-identical **after normalization**, and identical **substantive-payload** hash with the interruption recorded in the manifest. Without this, no workflow can ever reach `implemented`.
7. `idempotency.key_fields` is **derived** from `SH-RUN-10` rather than hand-declared, and a `--fresh` flag bypasses auto-resume (closes **I-07**).

**Confidence:** High. **Residual owner question Q4** covers the runs-root location.

## G-20 — Rollout sequence

**Recommended decision.** The G-20 framing — foundations, then research/decision lanes, then build lanes, then optimization — is **correct and already implemented** as blueprint §20 P0→P7 with per-phase exit criteria and `SH-ROAD-2` ("no phase before the previous exit is disk-verified"). Ratify it with four amendments, all evidence-driven:

1. **Prepend P-0 "bootstrap / doctor".** Measured absences: `acpx`, `pandoc` (rank-1 adapter for `doc.convert`), `magick` (rank-1 for `image.transform`). Deliverable: a required-binary inventory with versions and install commands, plus a `wf doctor` receipt. Closes **I-14**.
2. **Gate P4 on a provider-credential preflight.** The verified baseline records **all four provider probes failing** (OpenRouter 402, Anthropic 401, OpenAI 401, Gemini 404), yet `SH-INT-1` requires ≥3 genuinely independent voices in every multi-model step and §17.4 requires a core panel from different provider families. No phase currently contains a credential preflight and no workflow declares a precondition on provider auth. Until this passes, the entire approval panel is unimplementable and the wall-clock budgets (e.g. 1,800–3,600 s at `medium`/`high`) are unvalidated.
3. **Replace approximate phase counts with an explicit enabled-workflow list plus a dependency DAG.** "~6 / ~14 / ~24 / ~34" makes `SH-ROAD-2`'s exit set unverifiable, and the owner-creation chains are real ordering constraints: WF-21→22/23, WF-35→36–40, WF-08→09, WF-06→07, WF-25 profile→27/33. Closes **I-08**.
4. **Do not start P4/P5 before the R2 clearance policy is settled** (see the adjacent decision below); otherwise P4 and P5 deliver ~24 and ~34 cumulative workflows that terminate in `ESCALATED` and can never reach `COMPLETED`.

Sequencing evidence: `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md` §10 independently derives the same shape (baseline → reconcile attempts → transition discipline → offline repairs → projection/retest → live maintenance → human gates → evidence wave → final audit), and bounded parallelism is a correctness control, not a throughput knob [S19, S20].

**Confidence:** Medium-High (the shape is High; the phase-boundary detail depends on the explicit workflow lists that do not yet exist). **Residual owner question Q5** covers priority against the long-horizon closure lanes.

---

# SPLIT decisions — derived semantics, owner-set values

## G-19 — Budget policy

**Derived (no owner input needed):**

1. **Per-run caps already exist and are correct**: `budget.max_invocations`, `budget.max_wall_clock_s`, `budget.max_cost_units` are required schema fields, per-intensity-preset values are declared per workflow, and `SH-RUN-1` refuses a retry that would exceed a cap.
2. **A budget abort is never green.** Breaker trip → `FAILED_TO_RUN`, never a shortened or degraded result (`SH-INT-3`, AGENTS.md Wave C verification doctrine, and the closure completion contract all agree).
3. **Provider fallback is visible, logged, and policy-controlled**; never a silent downgrade and never a silent model-family change (G-8, `SH-INT-6`/`SH-INT-10`, and the 28.08.2026 no-silent-downgrade lock).
4. **Resource refusal must not be terminal.** The blueprint contradicts itself: `SH-ARCH-9` calls a RAM-refused run "re-queueable" while §4.1 lists `FAILED_TO_RUN` as terminal. Fix by adding a non-terminal state **`DEFERRED_RESOURCE`** with `VALIDATING → DEFERRED_RESOURCE → QUEUED`, bounded wait and backoff, and an owner-visible message; reserve `FAILED_TO_RUN`/`resource_guard` for wait-budget expiry. Closes feasibility **BLOCKER-10** part 1.
5. **The single 8 GB RAM floor must become a per-mode table.** Estate lock G-26 binds `agent worker start` (background workers) at 8 GB; the blueprint applies 8 GB at admission to *interactive* runs too. Measured free RAM today is **2.18 GB**, so as written **zero of the 40 workflows are admissible** and the failure is terminal. Recommended table: background/fan-out ≥ 8 GB (verbatim G-26), browser-using ≥ 6 GB, interactive non-browser ≥ 2 GB, re-evaluated before each fan-out batch. Closes **BLOCKER-10** parts 2–3.
6. **Cost accounting is per-run in `budget.json` and aggregated by a Layer-0 accumulator**, so the daily cap is a single trip point rather than per-recipe bookkeeping (scope-review **F-02**).

**Owner-choice residue:** the daily cap's **value, unit, and scope**. Nothing in the evidence base fixes a number. See **Q6**.

## G-21 — Acceptance criteria

**Derived (no owner input needed).** The right test is a **blinded head-to-head**, because G-2 already fixed the objective (research/evidence quality first, even when delivery is slower) and the blueprint already has the rubric (§18.5, rows A1–A19). Protocol:

1. Fix a task set spanning the domain families (clinical, finance-legal, careers, content, web).
2. Run each task twice: **(a)** direct invocation of the existing skill, **(b)** the registry recipe. Same intensity budget for both.
3. Blind the outputs and score with the G-2 metric set: source authority, independent corroboration count, full-text-read ratio, citation reproducibility, uncertainty disclosure, claim-to-source coverage.
4. Add the properties a direct skill invocation structurally **cannot** produce, scored as pass/fail rather than graded — these are the suite's actual thesis:
   - a complete gate-receipt set bound to one subject digest;
   - kill-and-resume with no lost work and no duplicated side effect;
   - reproducible re-run (byte-identical after normalization);
   - `FAILED_TO_RUN` correctly distinguished from `FAIL` and from `NOT-CHECKED`;
   - duplicate-prevention: no second owner created for an existing capability;
   - a recorded, resolved model/provider distribution preview per run.
5. Record wall-clock and cost as secondary telemetry, not objectives.

The pass/fail properties in step 4 are the honest answer to "why not just call the skill": every one of them is a property of the *control plane*, not of the prompt. If the suite cannot demonstrate them, it has no justification.

**Owner-choice residue:** the **pass bar** — what margin on evidence quality counts as "better", how many tasks, and how much wall-clock regression is tolerable. See **Q7**.

**Interlock:** acceptance rows A4/A11 are currently unsatisfiable (feasibility **BLOCKER-08**) and A15 is satisfiable only by proving R2 workflows are unusable (**BLOCKER-12**). G-21 cannot be measured until the G-18 normalization decision and the R2 policy land.

---

# OWNER-CHOICE questions

Each question is answerable in one line. Options are non-equivalent — they lead to materially different implementations, not different wordings of the same one.

## Q0 (G-13) — Autoresearch boundary

**Question:** Which repositories may the metric-driven autoresearch loop optimize, and against which metric?

- **(a) Not in v1.** Keep recipe #14 visibly planned but non-invocable. *Consequence:* zero risk; the "optimization" stage of the rollout ships empty.
- **(b) `source\qzp-lean` only**, metric = the lean-CI wall-clock plus coverage floor from its `.coverage-thresholds.json`. *Consequence:* one repo, a real existing numeric target, the canonical reference harness improves itself.
- **(c) `qzp-lean` + `D:\tools\mcp-manager`**, metric = coverage + static-gate finding count. *Consequence:* two mutable targets, and mcp-manager is currently mid-repair in lane L1 — autoresearch would race the repair agents.
- **(d) Any repo containing `.coverage-thresholds.json`**, metric read from that file. *Consequence:* self-extending scope; needs a per-repo opt-in file or it will eventually touch something unintended.

*Why this cannot be derived:* the choice is about what the owner wants improved and what he is willing to let an automated loop mutate. Blueprint §23 already records that no workflow uses autoresearch without an owner decision, and G-6 puts autoresearch in the owner-present class. Recommendation if you want one: **(b)** — smallest blast radius with a genuine metric.

## Q1 (G-12 residual) — Graph-leaf implementation

**Question:** Implement the complex-engine leaf as **LangGraph.js**, or as a minimal in-house cyclic runner?

- **(a) LangGraph.js** behind the engine interface. *Consequence:* documented `durability: sync` per-step checkpointing, `recursionLimit`, `interrupt`/`Command` resume, SQLite checkpointer — but a large dependency tree on a RAM-constrained box and an external supply-chain surface.
- **(b) Minimal in-house cyclic runner** (~a few hundred lines: bounded recursion, node dispatch, checkpoint-before-step, resume-from-checkpoint). *Consequence:* no new dependency, full control of the checkpoint format so it lands directly in the G-18 run directory — but you own the replay-hazard correctness that Temporal [S2] and LangGraph [S4] both document as subtle (pre-interrupt side effects replay; "effect completed, acknowledgement lost").
- **(c) acpx flows as the leaf.** *Consequence:* zero new dependency and checkpointing already exists — but no documented cycle or bounded-recursion semantics, and run state lives under `~/.acpx/flows/runs/` outside the estate ledger.

## Q2 (G-14 residual) — Cloud PHI

**Question:** May `cloud_phi_consent` ever be granted, or is PHI permanently local-only?

- **(a) Permanently local-only.** Delete the `cloud_phi_consent` flag; PHI-touching workflows (WF-35–40, WF-04/06/07) are hard-restricted to local models and local adapters. *Consequence:* health workflows lose frontier-model quality; some may be infeasible at useful quality.
- **(b) Consent possible per run**, recorded as an `INTERNAL` decision record (not `SECRET` — see feasibility **I-11**), with a named minimization step: only derived/aggregated features egress, never raw records. *Consequence:* keeps quality, adds a real consent-UX and a redaction-receipt gate.
- **(c) Consent possible per run for raw records** to one named provider only. *Consequence:* maximum quality, largest exposure; requires a provider-specific data-handling determination.

## Q3 (G-16 residual) — Agent-persistent profile granularity

**Question:** One shared agent-persistent browser profile, or one per domain group?

- **(a) One shared profile.** *Consequence:* logins persist broadly and conveniently (the owner's stated priority: never lose sessions); one compromise or one corrupt profile affects every authenticated lane, and the single-instance lock serializes all browser work.
- **(b) Per-domain-group profiles** (e.g. institutional/academic, careers/portals, general public web). *Consequence:* smaller blast radius per lane and independent locks; three profiles to back up and re-authenticate, more places for a session to silently expire.

## Q4 (G-18 residual) — Runs-root location

**Question:** Where does `<runs_root>` live?

- **(a) `C:\Users\Prekzursil\.agents\runs\`** — next to the harness. *Consequence:* co-located with skills and decisions; must be gitignored in the private `agent-skills-toolchain` repo or run receipts get committed; grows on the C: drive.
- **(b) `D:\Research\runs\`** — with the research estate. *Consequence:* off the pressured system drive, alongside the existing research/memory locations, naturally outside any git repo; a second root to remember when reconciling.
- **(c) `%LOCALAPPDATA%\cursor-automation\runs\`** — OS-conventional. *Consequence:* clean separation from both repos and research; least discoverable when the owner wants to read a receipt by hand.

## Q5 (G-20 residual) — Suite build vs long-horizon closure

**Question:** Does automation-suite implementation start before the L1–L5 closure lanes reach `COMPLETED`?

- **(a) Closure first.** No suite code until L1–L5 close. *Consequence:* respects the one-`cursor-agent` limit and 2.18 GB free RAM; the suite slips by the full closure duration.
- **(b) Interleave P-0/P0 only** (bootstrap inventory, JSON Schemas, disclaimer registry, taxonomy reconciliation) — all read-only or new-file work with disjoint write sets, so it is admissible under the bounded-parallelism rule. *Consequence:* the blueprint's blocking repairs progress while closure runs; nothing touches the mutable targets that L1/L2 own.
- **(c) Full parallel.** *Consequence:* directly violates the measured local bounds (max two read-only lanes, one mutation owner) and the empirical coordination-penalty finding [S20]; expect exactly the stalled/killed-subagent pattern already recorded as a workspace fact.

## Q6 (G-19 residual) — Daily cap

**Question:** What is the daily budget cap, in what unit, and at what scope?

- **(a) No daily cap in v1**; per-run caps only. *Consequence:* simplest; a bad day of many small runs is unbounded, and scope-review **F-02** stays open.
- **(b) Abstract cost units, estate-wide** (e.g. 200 units/day across all recipes, where the existing per-workflow budgets are 4–34 units per run). *Consequence:* unit already exists in the schema, no currency mapping needed, breaker is one accumulator; units are not directly auditable against a bill.
- **(c) Currency, per provider** (e.g. a monthly OpenRouter cap divided by days; Claude Max and ChatGPT are subscriptions, so their cap is the rate-limit window, not money). *Consequence:* directly auditable and matches the existing OpenRouter spend-cap policy; needs a per-provider unit→currency table that must be maintained as prices change.
- **(d) Wall-clock and invocation count only**, no monetary dimension. *Consequence:* aligns with the fact that the two frontier lanes are flat-rate subscriptions where the real scarce resource is the 5-hour rate cap and the weekly quota already visible in the statusline.

## Q7 (G-21 residual) — Acceptance pass bar

**Question:** What margin makes the suite "better than invoking the skill directly"?

- **(a) Strict:** all six control-plane properties pass **and** the suite scores strictly higher on every G-2 evidence metric, with no wall-clock limit. *Consequence:* an unambiguous, defensible claim; likely several iterations before it is met.
- **(b) Balanced:** all six control-plane properties pass **and** the suite is at least equal on every evidence metric and strictly better on at least two, with wall-clock allowed to regress up to ~2× on the same intensity preset. *Consequence:* achievable in one or two iterations, still a real claim.
- **(c) Control-plane only:** the six pass/fail properties are the whole bar; evidence-quality parity is sufficient. *Consequence:* fastest to green, but abandons G-2's stated primary success metric.

---

# Adjacent owner decision this set depends on (not part of G-12…G-21)

**R2 clearance on a single-owner estate** (feasibility **BLOCKER-12**). §17.4 step 6 requires a second independent human for R2; `SH-VER-2` returns `ESCALATE` when only one human is available; §13.2 sets an R2 *minimum* for medical advice, personal health data, legal advice, financial advice, financial personal data, image identity, authenticated browser, and irreversible local action — covering at minimum WF-04, 06, 07, 17, 20, 21, 22, 23, 28, 35, 36, 37, 38, 39, 40.

As written those runs terminate in `ESCALATED`, a terminal state, and can never reach `COMPLETED`. This structurally blocks roughly 15+ workflows and makes acceptance row A15 satisfiable only by proving the workflow is unusable. It gates **G-20** (do not build P4/P5 first) and **G-21** (A15 is unmeasurable). It is listed here rather than answered because it is a policy choice, and because the one option that must **not** be taken is derivable: do not relabel a model panel as human independence — `SH-VER-2` and `RESEARCH-APPROVAL-GATES_2026-08-29.md` both forbid it, correctly, and G-11 already settled that extra voices cannot manufacture confidence through voting.

The defensible shape, if the owner wants a recommendation: a **single-owner R2 mode** — deterministic gates plus a time-separated owner second pass performed in an explicitly different role against the final revision hash, recorded honestly as `human_approvals.two_party_certification: not_achieved` with the compensating deterministic control set named per risk factor, and an explicit list of which R2 workflows are cleared under it versus which remain permanently `planned`.

---

# What this research does not claim

- **No decision here is enacted.** This file records recommendations and questions; the decision log (`AUTOMATION-SUITE-DECISIONS_2026-08-29.md`) is unmodified, and so is the blueprint.
- **acpx is not installed.** Its capabilities above are from current official documentation and the npm registry, not from local execution. Local behaviour on Windows with `cursor-agent acp` is **NOT-CHECKED**.
- **LangGraph is not installed** and no version was pinned. Its durability semantics are from current official docs; no local benchmark was run.
- **[S1]–[S20] were not re-verified today.** They are inherited at their original A/High grades from `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md` (SHA-256 `815330B6EAB375CA8F7E8307F35212C5FE8047649022739DE39F223393B70E72`).
- **Basic Memory was not queried.** It has repeatedly returned `Session not found` (lane L5), and that condition remains `WAITING_EXTERNAL`, not a successful knowledge check. No memory write was attempted.
- **The blueprint was not re-read in full.** Only the targeted sections named above. The two FAIL gates remain the authority on its 25 blocking defects; nothing here reduces that count.

# Sources

**Verified today (29.08.2026):**

1. **acpx — npm package registry.** Version 0.13.2, MIT, `openclaw/acpx`, updated 2026-08-28. https://www.npmjs.com/package/acpx — Grade A (primary registry metadata) / High.
2. **acpx — CLI reference (`docs/CLI.md`, upstream `main`).** `flow run` semantics, run-state path `~/.acpx/flows/runs/`, per-session queue owner + IPC, TTL, cancellation, auto-resume order (`session/resume` → `session/load` → `session/new`), permission modes, output formats. https://github.com/openclaw/acpx and https://acpx.sh/ — Grade A (official project documentation) / High.
3. **LangGraph — Checkpointers (JavaScript and Python).** Durability modes `exit` / `async` / `sync`; checkpointer implementations; thread identity. https://docs.langchain.com/oss/javascript/langgraph/checkpointers and https://docs.langchain.com/oss/python/langgraph/checkpointers — Grade A / High.
4. **LangGraph.js API reference — `PregelOptions`.** `durability`, `recursionLimit`, `interruptBefore/After`, `maxConcurrency`, `signal`. https://langchain-ai.github.io/langgraphjs/reference/interfaces/langgraph.PregelOptions.html — Grade A / High.
5. **Local estate probes.** `Get-Command acpx` (absent), `npm view acpx version` (0.13.2), `Win32_OperatingSystem.FreePhysicalMemory` (2.18 GB free of 31.63 GB). Grade: direct measurement / High.

**Inherited at original grade from `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md` (not re-verified today):** [S1]–[S3] Temporal durable execution, activity idempotency, retry policies (A/High) · [S4]–[S5] LangGraph interrupts and persistence (A/High) · [S6] Agent Client Protocol v1 schema (A/High) · [S7]–[S9] GitHub concurrency, environments, artifact attestations (A/High) · [S10] SLSA v1.2 build provenance (A/High) · [S11] NIST AI 600-1 (A/High) · [S12] NIST SP 800-218 SSDF (A/High) · [S13] OWASP Top 10 for Agentic Applications 2026 (A-/High) · [S14]–[S15] GitHub protected branches and status checks (A/High) · [S16] Playwright authentication and persistent context (A/High) · [S17]–[S18] AWS idempotency and transactional outbox (A/High) · [S19] Cemri et al., MAST (A-/Medium-High) · [S20] Qian et al., scaling agent systems (B+/Medium).

**Estate-internal normative inputs:** `AUTOMATION-SUITE-DECISIONS_2026-08-29.md` · `LONG-HORIZON-CLOSURE_2026-08-29.md` · `RESEARCH-LONG-HORIZON-CLOSURE_2026-08-29.md` · `RESEARCH-APPROVAL-GATES_2026-08-29.md` · `PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md` · the three `PERPLEXITY-BLUEPRINT-REVIEW-*_2026-08-29.md` gates · `AGENTS.md` · `CLAUDE.md`.

*Produced read-only on 29.08.2026. This file is the only artifact written by this lane.*
