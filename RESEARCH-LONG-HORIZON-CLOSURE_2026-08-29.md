# Durable Long-Horizon Multi-Agent Software Work

**Research date:** 29.08.2026  
**Version:** 1.0  
**Applied target:** `C:\Users\Prekzursil\.agents\LONG-HORIZON-CLOSURE_2026-08-29.md`  
**Sources:** 20 authoritative or primary research sources  
**Overall confidence:** High for durability, provenance, idempotency, and gate design; Medium-High for the local application; Medium for quantitative multi-agent scaling limits.

## Executive conclusion

The closure program already has the correct top-level safety doctrine: completion is an AND-gate; missing artifacts, budget aborts, stale UI, and agent self-report are not completion; live behavior needs live verification; rollback and resume instructions are required. Its main remaining weakness is not policy intent but operational representation. The document is a human-readable status summary, not yet a replay-safe state machine.

The most defensible current practice is:

1. persist every lane and step as an explicit state transition in an append-only ledger;
2. separate deterministic orchestration state from retryable side effects;
3. give every attempt, mutation, artifact, and review a stable identity and content digest;
4. treat tool writes as prepare/commit/verify transactions, or as compensating sagas when atomicity is impossible;
5. allow parallel work only where subtasks are independent and read-only or have disjoint write sets;
6. invalidate reviews and test receipts whenever their exact subject digest changes;
7. treat browser/ACP session persistence as transport continuity, never as proof that a task or side effect completed;
8. stop at explicit human gates on ambiguity, privilege changes, irreversible effects, failed preconditions, or uncertain side-effect outcomes;
9. permit `COMPLETED` only from disk-verified evidence tied to the exact final state.

For this closure program, live mutations should be globally serialized. Read-only research and independent reviews may run with a maximum concurrency of two on this machine. A single `cursor-agent`, a single browser profile instance, and a single mutable target owner remain hard limits. No active lane is safely closeable merely from the narrative evidence currently recorded.

## Method and evidence labels

The research examined durable execution, checkpoint/replay, agent protocol lifecycle, software artifact provenance, protected delivery gates, secure software development, browser authentication persistence, idempotent retry design, and empirical multi-agent failure/scaling studies.

Nine key sources were deep-read rather than assessed from search snippets: Temporal workflow execution; LangGraph interrupts; ACP v1 schema; SLSA v1.2 provenance; NIST AI 600-1; NIST SP 800-218; OWASP Top 10 for Agentic Applications 2026; and the two principal empirical multi-agent papers [S1, S4, S6, S10-S13, S19-S20].

Evidence labels used below:

- **FACT — High:** directly stated in an official specification, standard, or vendor documentation.
- **FACT — Medium:** measured in primary empirical research, but external validity or publication maturity is limited.
- **INFERENCE — High:** a direct engineering implication supported by multiple independent authoritative sources.
- **INFERENCE — Medium:** a recommended adaptation to this exact local program; it has not yet been experimentally validated here.

Basic Memory preflight returned `Session not found`. No memory result was used, and the failure is not treated as a successful knowledge check. This matches the closure program's existing L5 status.

## 1. Durable orchestration must be a replayable state machine

### Findings

- **FACT — High:** Temporal persists workflow progress through an event history and reconstructs state by deterministic replay. After failure, execution continues from the latest recorded event. Failure-prone or non-deterministic I/O belongs in Activities, not deterministic workflow logic [S1-S3].
- **FACT — High:** Temporal Activities can execute more than once when a worker performs a side effect but fails before reporting completion. Temporal therefore recommends idempotent write Activities and stable idempotency keys [S2].
- **FACT — High:** LangGraph interrupts persist graph state through a checkpointer, but resumption restarts the interrupted node from its beginning. Code before the interrupt runs again, so preceding side effects must be idempotent. Production use requires a durable checkpointer and the same thread identity on resume [S4-S5].
- **FACT — High:** ACP provides lifecycle operations including `session/load`, optional `session/resume`, `session/cancel`, and optional `session/close`, with capability negotiation and permission requests. ACP does not itself guarantee durable task state or exactly-once external effects [S6].

### Implication for the closure program

- **INFERENCE — High:** The closure file should be the human projection of a durable transition ledger, not the only state store. Each transition must be independently reconstructable after process death or context loss.
- **INFERENCE — High:** Conversation transcript, ACP session ID, background-agent card, and process liveness are references to execution context; none is authoritative task state.
- **INFERENCE — Medium:** A heavyweight Temporal deployment is not necessary for the current program. The same invariants can be implemented with an append-only local ledger, atomic snapshot replacement, stable IDs, and deterministic transition rules. Adopting a workflow engine is justified only if the program becomes a recurring service rather than a finite closure effort.

### Required state model

Use a finite set of states with no free-text substitutes:

`PLANNED → READY → LEASED → RUNNING → VERIFYING → REVIEWING → READY_TO_APPLY → APPLYING → LIVE_VERIFYING → COMPLETED`

Exceptional states:

`WAITING_EXTERNAL`, `BLOCKED_HUMAN`, `FAILED`, `FAILED_TO_RUN`, `CANCELLED`, `STALE`, `ROLLING_BACK`, `ROLLED_BACK`, `REOPENED`.

Required transition rules:

1. Only `READY` work may be leased.
2. A lease has an owner, attempt ID, start time, expected heartbeat, and expiry.
3. `RUNNING` cannot transition directly to `COMPLETED`.
4. `VERIFYING` requires deterministic receipts.
5. `REVIEWING` requires a reviewer different from the producer and a subject digest.
6. Any subject change invalidates dependent test and review receipts and returns the step to `RUNNING` or `VERIFYING`.
7. `APPLYING` is globally exclusive for live or shared mutable state.
8. `COMPLETED` is immutable unless an explicit invalidation event creates `REOPENED`.
9. Budget exhaustion, timeout, cancellation, missing artifact, or tool unavailability maps to `FAILED_TO_RUN`, `CANCELLED`, or `WAITING_EXTERNAL`; never `PASS`.

## 2. Provenance must bind evidence to the exact artifact and execution

### Findings

- **FACT — High:** SLSA provenance binds subjects to digests and records build type, external parameters, resolved dependencies, builder identity, invocation ID, timestamps, and byproducts. Verification depends on recognizing the builder and checking expected parameters, not merely possessing a provenance file [S10].
- **FACT — High:** GitHub artifact attestations provide signed provenance and integrity guarantees for build artifacts. Verification is a separate consumer action [S9].
- **FACT — High:** NIST AI 600-1 calls for inventories containing provenance, version, known issues, access modes, and human oversight roles; ground-truth and human/automated evaluation; ongoing monitoring; incident records; override records; and prompt escalation when criteria are met [S11].
- **FACT — High:** NIST SSDF calls for documented requirements and roles, reproducible supporting toolchains, release-integrity verification, human-readable code review, executable testing, ongoing vulnerability identification/remediation, and root-cause analysis [S12].

### Implication for the closure program

- **INFERENCE — High:** The current `disk-verified` versus `agent-claimed` distinction is sound but too coarse. Each evidence item needs a provenance envelope.
- **INFERENCE — High:** A test count such as “322 tests” or “82 offline tests pass” is not durable completion evidence unless tied to the exact source digest, command, environment/tool versions, start/end time, exit status, and stored output digest.
- **INFERENCE — High:** “Review passed” becomes stale after any relevant edit. Reviews must name the exact artifact or tree digest reviewed.
- **INFERENCE — Medium:** SLSA's schema should be adapted, not copied literally, for work-unit receipts.

Minimum evidence record:

| Field | Requirement |
|---|---|
| `lane_id`, `step_id`, `attempt_id` | Stable identifiers |
| `subject_paths` | Exact files, stores, services, or UI state evaluated |
| `subject_digests` | SHA-256 or equivalent before and after |
| `inputs` | Requirement/spec revision and dependency digests |
| `executor` | Human, agent, CI app, or tool identity |
| `toolchain` | Tool and model versions; relevant configuration digest |
| `invocation` | Exact command or structured tool request, with secrets redacted |
| `started_at`, `finished_at` | UTC timestamps |
| `result` | `PASS`, `FAIL`, `FAILED_TO_RUN`, or `NOT_CHECKED` |
| `artifacts` | Output paths plus size and digest |
| `live_target` | Workspace/service/profile identity where applicable |
| `reviewer` | Independent reviewer identity and review artifact |
| `provenance` | `cryptographically-attested`, `disk-verified`, `externally-verified`, `agent-claimed`, `not-checked`, or `stale` |

Completion must re-read each promised artifact and recompute its digest. Exit code alone is insufficient. A missing artifact after the existing approximately 60-second write-lag grace remains a failure, not a pass.

## 3. Idempotency and transactional tool changes prevent duplicate or partial state

### Findings

- **FACT — High:** Durable runtimes commonly provide at-least-once execution around failure boundaries. Replay or retry can execute a side effect more than once. AWS recommends idempotent writes, stable tokens generated once per logical operation, and semantics chosen to match the side effect [S17].
- **FACT — High:** A transactional outbox couples business state and intent publication in one local transaction; rollback removes both. Consumers must still tolerate duplicate delivery [S18].
- **FACT — High:** LangGraph explicitly warns that pre-interrupt side effects replay, and Temporal explains the “effect completed, acknowledgement lost” failure window [S2, S4].
- **FACT — High:** OWASP recommends action-level approval, task-scoped and time-bound permissions, independent policy enforcement, blast-radius controls, output validation, human gates, logging, and containment for agentic tool misuse and cascading failures [S13].

### Implication for the closure program

- **INFERENCE — High:** Every mutating step needs a logical operation ID that remains stable across retries. A new transport attempt must not create a new business operation.
- **INFERENCE — High:** A write is not complete until its postcondition is independently read from the target. “Tool returned success” is only an acknowledgement.
- **INFERENCE — High:** If it is unknown whether a non-idempotent side effect occurred, automatic retry is unsafe. The lane must enter `BLOCKED_HUMAN` or a reconciliation state.

Required mutation protocol:

1. **Prepare**
   - acquire an exclusive lease for the mutable target;
   - inventory and digest the current target;
   - create a backup or documented compensation path;
   - calculate the intended diff;
   - validate permissions and hard boundaries;
   - run dry-run/preflight checks;
   - record an idempotency key and expected pre/postconditions.
2. **Authorize**
   - require the appropriate human or independent policy gate for privilege, secret, external-access, or irreversible changes;
   - bind approval to the mutation-plan digest.
3. **Commit**
   - compare the current target digest with the prepared precondition;
   - abort on mismatch;
   - use atomic replace where the target supports it;
   - otherwise execute one compensated step at a time, persisting each result.
4. **Verify**
   - re-read the live target independently;
   - verify exact postconditions and absence of forbidden state;
   - run deterministic and live checks.
5. **Close or compensate**
   - mark complete only after verification;
   - on failure, run the recorded compensation if safe;
   - verify rollback and record residual state.

## 4. Bounded parallelism is a correctness control

### Findings

- **FACT — Medium:** The MAST study analyzed more than 150 traces across five multi-agent frameworks and identified 14 failure modes spanning specification/system design, inter-agent misalignment, and verification/termination. It found strong human-annotation agreement after taxonomy refinement and showed that prompt-level interventions did not consistently remove failures [S19].
- **FACT — Medium:** A controlled scaling study across 260 configurations, five architectures, three model families, and six benchmarks found large gains on decomposable tasks but degradation of 39%-70% on sequential planning tasks. Tool-heavy tasks incurred a statistically significant coordination penalty; turn count grew super-linearly; and centralized verification contained error propagation better than independent agents. The study reports a practical ceiling around three to four agents under fixed budgets, but it remains a research result rather than a universal constant [S20].
- **FACT — High:** GitHub concurrency controls can serialize workflows or deployments. Environment protection rules can require approval and withhold environment secrets until approval [S7-S8].

### Implication for the closure program

- **INFERENCE — High:** Parallelism should be admitted by dependency and write-set analysis, not by agent availability.
- **INFERENCE — High:** Sequential live changes, shared state, and cross-step constraints should remain under one orchestrator.
- **INFERENCE — Medium:** Because this machine has chronic memory pressure and a one-`cursor-agent` hard limit, the appropriate local bounds are stricter than the research ceiling:
  - live/shared mutations: **1 globally**;
  - `cursor-agent`: **1**;
  - browser profile instances: **1 per profile, and only one browser automation lane at a time**;
  - independent read-only research/review tasks: **2 total**;
  - same artifact or state-store writers: **1**;
  - final synthesis/assembly: **1**.

Parallel work is safe only if all are true:

1. inputs are pinned by digest;
2. tasks have disjoint write sets or are read-only;
3. each task has an independent result artifact;
4. cancellation of one task cannot invalidate another's side effect;
5. one owner serially reconciles outputs;
6. downstream work does not start from agent claims before disk verification.

## 5. Review gates must be fresh, independent, and fail-closed

### Findings

- **FACT — High:** GitHub protected branches can require reviews and status checks, dismiss approvals when the reviewed diff changes, require approval of the latest reviewable push by another person, and use a merge queue to re-test changes against the latest target state [S14].
- **FACT — High:** GitHub required status checks can accept `successful`, `skipped`, or `neutral` conclusions, depending on configuration. GitHub also permits pinning the expected source app for a required check [S14-S15].
- **FACT — High:** NIST AI 600-1 recommends risk-proportional independent evaluation, defined go/no-go thresholds, real-world testing, regular adversarial testing, ongoing monitoring, override logging, and escalation/deactivation criteria [S11].
- **FACT — High:** NIST SSDF separates review of human-readable code from executable testing and requires ongoing vulnerability response and root-cause prevention [S12].

### Implication for the closure program

- **INFERENCE — High:** The current code, language, security, feasibility, completeness, and scope gates are appropriate, but every gate must emit a receipt tied to one subject digest.
- **INFERENCE — High:** A producer cannot self-certify a gate. Independent review must be performed by a fresh reviewer or deterministic verifier with no ability to silently modify the subject.
- **INFERENCE — High:** A budget-aborted or timed-out gate is `FAILED_TO_RUN`, exactly as the existing doctrine states.
- **INFERENCE — High:** For load-bearing local gates, `skipped` and `neutral` must not be normalized to `PASS`, even though GitHub may allow them to satisfy branch protection.
- **INFERENCE — High:** A finding is closed only by a fix plus rerun, or a written disproof with evidence. Mere downgrading or acceptance is not closure under the program's current contract.

Recommended gate order:

1. requirements/scope;
2. deterministic tests and structural checks;
3. code/language review;
4. security review;
5. live wiring test, when claimed;
6. final acceptance review against the completion contract;
7. independent cross-lane audit after all lane subjects are stable.

Any change after gate 2 invalidates the relevant downstream gates. The final audit must verify receipts, not repeat agent summaries.

## 6. Browser and ACP session persistence are continuity mechanisms, not completion evidence

### Findings

- **FACT — High:** Playwright can persist authenticated state and reuse it, but its authentication-state files may contain sensitive cookies and headers and should not be committed. Persistent contexts store cookies and local storage in a dedicated user-data directory [S16].
- **FACT — High:** Playwright warns against automating the default Chrome user profile and states that browsers do not permit simultaneous use of the same user-data directory. A separate automation profile is required [S16].
- **FACT — High:** ACP session resume is capability-dependent and restores conversational/session context. Cancellation asks the agent to stop in-flight model and tool operations, but does not prove that an external side effect did not already occur [S6].
- **FACT — High:** OWASP identifies memory/context poisoning, privilege abuse, cascading failures, and human-agent trust exploitation as agentic risks; relevant mitigations include segmentation, provenance, task-scoped permissions, independent validation, logging, and containment [S13].

### Implication for the closure program

- **INFERENCE — High:** Preserve two separate durable objects:
  1. **task state**: step/attempt/transition/evidence ledger;
  2. **browser or ACP session state**: profile/session identifier and reauthentication status.

  Neither may substitute for the other.
- **INFERENCE — High:** The existing mandatory per-run browser profile choice must remain explicit:
  - owner/live profile only with a current-session explicit override;
  - agent-persistent profile as the default durable mode;
  - agent-ephemeral profile for isolated work.
- **INFERENCE — High:** The owner Chrome profile remains forbidden unless explicitly selected for that exact run. The current browser pause remains `BLOCKED_HUMAN`; research does not authorize resumption.
- **INFERENCE — High:** Persist only the profile directory or protected authentication state needed for continuity. Never record cookies, tokens, or credentials in task receipts. Receipts record profile mode, profile identifier/digest where safe, browser version, and a redacted authentication probe result.
- **INFERENCE — High:** Acquire a profile lock before launch, detect stale locks with process evidence, and never open two browser instances on the same profile.
- **INFERENCE — High:** After restart, first reconcile the last browser action from observable target state. Do not blindly replay a click, submission, invite, permission, or destructive action.

## 7. Human escalation should be a state, not an interruption failure

### Findings

- **FACT — High:** NIST recommends explicit human oversight roles, deployment approval thresholds, escalation and deactivation criteria, incident-response ownership, and logging of human overrides [S11].
- **FACT — High:** GitHub environments support manual approval and can prevent self-review; environment secrets remain unavailable until approval [S8].
- **FACT — High:** LangGraph and Temporal can durably wait for external human input rather than keeping a process alive [S1, S4].
- **FACT — High:** ACP supports structured permission requests and cancellation outcomes [S6].

### Implication for the closure program

- **INFERENCE — High:** Human waiting is a normal durable state (`BLOCKED_HUMAN`), not a timeout and not an excuse to abandon the lane.
- **INFERENCE — High:** Escalation must occur before:
  - destructive or irreversible action;
  - privilege expansion, secret access, authentication-mode change, or exposure change;
  - use of the owner browser profile;
  - a live write whose precondition changed;
  - retry after uncertain non-idempotent side-effect outcome;
  - conflict between independent reviewers;
  - unresolved critical/high finding;
  - lack of a safe compensation path;
  - two failed attempts on the same hypothesis;
  - lease expiry with ambiguous live mutation state;
  - reactivation of owner-paused automation.

The escalation packet should contain only:

1. lane/step/attempt and current state;
2. exact decision required;
3. evidence and artifact paths/digests;
4. impact and blast radius;
5. safe options, including “leave unchanged”;
6. rollback/compensation status;
7. recommended choice with confidence;
8. expiry or conditions under which the approval becomes stale.

Approval must be bound to the plan digest. Material plan changes require new approval.

## 8. Exact gap analysis of the current closure document

### What is already strong

- **FACT about the local document — High:** The completion contract is fail-closed and requires disk artifacts, deterministic checks, applicable reviews, live tests, finding closure, and resume/rollback instructions.
- **FACT about the local document — High:** It correctly rejects budget abort, interruption, missing output, stale UI, and agent self-report as completion.
- **FACT about the local document — High:** Hard boundaries forbid force push, hard reset, credential rotation, secret output, unauthorized live-browser access, premature MCP writes, Daria access to owner resources, and multiple local `cursor-agent` processes.
- **FACT about the local document — High:** Basic Memory's `Session not found` condition is explicitly deferred rather than called complete.

### Gaps that can still create unfinished or false-green state

1. **Narrative states are not executable states.** “Active,” “in progress,” “remaining,” and “await” have no transition preconditions, lease, heartbeat, or timeout.
2. **Agent identity is recorded without attempt provenance.** L1 names two agents but does not bind each to a step, input digest, expected output artifact, lease expiry, or last disk-verified heartbeat.
3. **Banked evidence is not bound to exact subjects.** Test counts, review passes, build verification, configuration, and live URLs lack command receipts, timestamps, artifact hashes, tool versions, and invalidation rules.
4. **Lane boundaries are too coarse.** “Update this file at every lane boundary” loses progress and side-effect ambiguity inside multi-step lanes.
5. **No mutation transaction record exists.** L1 and L2 include approval-store, service, container, auth, ACL, and exposure changes without an explicit prepare/commit/postcondition schema.
6. **No resource-lock inventory exists.** The one-`cursor-agent` rule is present, but shared state such as the MCP approval store, private SSOT projection, Codeg configuration, and browser profile also need exclusive ownership.
7. **Review freshness is implicit.** L3 correctly records failed gates, but subsequent review results need exact artifact hashes and automatic invalidation after every repair/reassembly.
8. **Waiting lacks escalation semantics.** “Await MCP repair agents” has no expected heartbeat, deadline, independent liveness checks, or recovery owner.
9. **Browser continuity is underspecified.** L4 identifies the missing persistent profile, but task-state recovery, profile locking, authentication expiry, secret handling, and replay reconciliation need separate receipts.
10. **Cross-lane closure order is implicit.** L5's final audit depends on stable outputs from L1-L4, yet no dependency edge prevents it from running against stale subjects.

## 9. Lane-by-lane application

### L1 — MCP manager and definition restoration

**Current defensible state:** `RUNNING` or `STALE_PENDING_RECONCILIATION`, not closeable. The two named agents are execution references, not evidence.

Required controls:

1. Re-read each agent's promised output artifact and current source state before deciding whether the attempt is alive, failed, or stale.
2. Give each repair attempt a lease and expected artifact manifest.
3. Bind all test and review receipts to the exact D: source tree digest and later to the private SSOT tree digest.
4. Selective synchronization is its own transaction: source manifest → intended destination diff → exclusive SSOT lease → apply → destination digest → both test suites.
5. Live MCP changes must be globally serialized:
   - freeze Cursor sessions;
   - snapshot and digest the approval store;
   - independently prove the store is core-only after pre-disable;
   - create a guarded attach plan and bind approval to its digest;
   - compare-and-swap against the original store digest;
   - perform one guarded write;
   - restart one workspace;
   - verify actual processes, tools, and IDs;
   - test one preset and one disable→enable refresh;
   - verify LinkedIn remains default-off.
6. Any mismatch enters `BLOCKED_HUMAN` or rollback; never continue by broadening approval.

Completion evidence must include the source and SSOT digests, both test receipts, all review receipts, pre/post approval-store digests, process/tool inventory, preset/toggle evidence, and verified rollback instructions.

### L2 — Daria private AI workspace

**Current defensible state:** configuration work is `READY`; browser-dependent verification is `BLOCKED_HUMAN`; install completion is `WAITING_EXTERNAL` until independently read.

Required controls:

1. Reconcile Cursor installation from package/binary state and a functional ACP response, not an installer card.
2. Treat API-key auth configuration as a secret-bearing transaction. Record only redacted verification, never the key.
3. Pin sandbox, manual permission mode, host-tools setting, terminal lock, and enabled-agent inventory to configuration digests.
4. Verify workspace-only writes with negative tests against owner paths, browser profiles, global MCPs, and harness paths.
5. Session-resume testing must combine ACP resume with task-ledger reconciliation; session continuity alone is not completion.
6. Cancellation testing must inspect whether any tool side effect happened before cancellation acknowledgement.
7. Browser/photo/attachment tests remain blocked until the owner explicitly resumes browser automation and makes the mandatory profile choice.

Completion evidence must prove both positive functionality and negative isolation. A working chat response without the negative access tests is not completion.

### L3 — Workflow blueprint repair

**Current defensible state:** `RUNNING_REPAIR` with two explicit failed gates. This is correctly not green.

Required controls:

1. Hash the complete input set and assembled blueprint before repair.
2. Parallelize at most two genuinely disjoint part repairs; shared taxonomies, SourceRecord, capability enums, engine contracts, and canonical grammar require one owner.
3. Persist each part's output and digest before assembly.
4. Run assembly serially and pin all source-part hashes into the final artifact.
5. Run deterministic 40/320/source/citation/reconciliation checks on the exact assembled digest.
6. Run fresh feasibility, completeness, and scope/alignment reviewers on that same digest.
7. Any repair after a review invalidates all affected review receipts.

The lane closes only when all three reviews pass on the exact deterministic-check subject and all blockers/findings have fix-or-disproof evidence.

### L4 — Browser, Avante, diagnostics, and documentation

**Current defensible state:** mixed lane; browser items are `BLOCKED_HUMAN`, Playwright pinning/profile design is `READY`, diagnostics is `WAITING_EXTERNAL` for refresh/reboot, and Avante is `REVIEWING_PENDING`.

Required controls:

1. Pin Playwright by exact package/version and record the resolved artifact.
2. Create a dedicated agent-persistent profile, never the owner Chrome profile.
3. Enforce the per-run live/persistent/ephemeral decision before launch.
4. Protect profile material with owner-only access and exclude authentication state from source control and logs.
5. Add a per-profile instance lock and post-crash reconciliation.
6. Do not run the no-focus smoke while the owner pause remains active.
7. Diagnostics verification must be a fresh post-refresh/reboot UI and service-state observation, not reliance on earlier configuration intent.
8. Avante review must bind to the final ACL and wrapper digests.

### L5 — Independent evidence and governance

**Current defensible state:** `READY` for read-only reviews, `WAITING_EXTERNAL` for Basic Memory, and dependency-blocked for final audit.

Required controls:

1. Run at most two independent read-only reviews concurrently.
2. A canceled or budget-aborted security/DeepSource run is `FAILED_TO_RUN`; retry once as already planned, then escalate with the exact failure.
3. Record DeepSource repository identity, analyzed revision, issue/vulnerability snapshot, report-card timestamp, and raw evidence path.
4. Keep council and multi-model synthesis advisory unless their claims cite deterministic receipts.
5. Preserve Basic Memory semantics. `Session not found` remains `WAITING_EXTERNAL` or `FAILED_TO_RUN`; do not disable semantic search and do not silently substitute another writer.
6. Run self-reflection only after stable evidence exists and keep candidate learnings subject to owner approval.
7. Final completion audit starts only after L1-L4 are `COMPLETED` on stable digests.

## 10. Recommended closure sequence

This sequence minimizes dependency and live-state risk:

1. **Baseline:** snapshot the closure document, active artifacts, mutable targets, agent/process state, and current digests.
2. **Reconcile active attempts:** verify both L1 repair agents from disk and process/heartbeat evidence; after a missed heartbeat, allow the existing approximately 60-second artifact-lag grace and use a second independent liveness check.
3. **Install transition discipline:** assign lane/step/attempt IDs, leases, resource locks, and explicit states before further mutation.
4. **Finish offline repairs:** close L1 code repairs and L3 blueprint repairs with deterministic tests and fresh reviews.
5. **Project and retest L1 SSOT:** perform the selective sync transaction and verify both deployed and SSOT suites.
6. **Perform L1 live maintenance:** one mutation owner, prepared rollback, guarded attach, one-workspace restart, and live inventory.
7. **Finish non-browser L2 and L4 work:** Daria isolation/auth/configuration, Playwright pin/profile preparation, diagnostics post-reboot verification, and Avante review.
8. **Human browser gate:** keep all browser actions blocked until the owner resumes and chooses the per-run profile.
9. **Run L5 evidence wave:** bounded read-only reviews, one bounded retry for prior interrupted gates, then synthesize.
10. **Final audit:** independently recompute artifact digests, validate every completion predicate, verify no unresolved finding or stale gate, and confirm rollback/resume instructions.

No global “all complete” state is permitted while any required step is `WAITING_EXTERNAL`, `BLOCKED_HUMAN`, `FAILED_TO_RUN`, `STALE`, `NOT_CHECKED`, or supported only by `agent-claimed` evidence.

## 11. Minimum closure checklist

A lane may transition to `COMPLETED` only when all answers are yes:

- Is every promised artifact present and re-read from disk?
- Does each artifact digest match the subject used by tests and reviews?
- Are deterministic commands, versions, timings, exit status, and output receipts recorded?
- Did every required gate produce `PASS`, not skip, neutral, timeout, cancellation, or budget abort?
- Are reviewers independent, and are approvals bound to the latest subject digest?
- Are all critical/high findings resolved and all minor/optional findings fixed or disproven with evidence?
- If live behavior is claimed, was the exact deployed target tested after the final mutation?
- Were positive behavior and relevant negative boundaries both tested?
- Is every mutation idempotent or paired with reconciliation/compensation?
- Are resume and rollback instructions present and still valid for the final state?
- Are session/profile references protected and free of secret material?
- Is the next state after interruption mechanically derivable without transcript reconstruction?

## Confidence and limitations

| Conclusion | Confidence | Basis / limitation |
|---|---:|---|
| Durable work requires persisted state transitions plus deterministic replay semantics | High | Temporal and LangGraph independently converge on checkpoint/history and replay [S1-S5] |
| Side-effecting retries require idempotency or reconciliation | High | Temporal, LangGraph, and AWS agree [S2, S4, S17-S18] |
| Artifact existence without provenance is insufficient | High | SLSA, GitHub, and NIST [S9-S12] |
| Reviews must be invalidated when the subject changes | High | GitHub protected-branch semantics plus provenance logic [S10, S14] |
| Human approval must be durable and bound to the proposed action | High | NIST, GitHub environments, LangGraph, ACP [S4, S6, S8, S11] |
| Multi-agent parallelism should be bounded and task-structure dependent | Medium-High | Two empirical studies agree on coordination and verification failure, but benchmarks and model generations limit generalization [S19-S20] |
| Maximum two read-only concurrent tasks is right for this machine | Medium | Conservative local inference from measured memory pressure and empirical coordination costs; should be revised only from local telemetry |
| A local append-only ledger is sufficient without Temporal | Medium-High | Direct implementation inference; depends on disciplined atomic writes, locks, and validation |
| The present closure document is not yet interruption-safe by itself | High | Direct comparison of its fields with the sourced invariants |

The empirical studies do not prove that every multi-agent system fails above a fixed number of agents. Their strongest transferable result is conditional: decomposition helps only where work is genuinely parallelizable, while sequential constraint chains and tool-heavy environments amplify coordination cost and error propagation.

## Sources

1. **[S1] Temporal — Workflow Execution overview.** Official documentation; durable execution, event history, and replay. https://docs.temporal.io/workflow-execution  
   **Grade:** A / High.
2. **[S2] Temporal — Activity Definition.** Official documentation; retries, acknowledgement-loss window, idempotency, and stable keys. https://docs.temporal.io/activity-definition  
   **Grade:** A / High.
3. **[S3] Temporal — Retry Policies.** Official documentation; Activity versus Workflow retry semantics and deterministic replay. https://docs.temporal.io/encyclopedia/retry-policies  
   **Grade:** A / High.
4. **[S4] LangGraph — Interrupts.** Official documentation; durable checkpoints, node restart, idempotent pre-interrupt effects, and human gates. https://docs.langchain.com/oss/python/langgraph/interrupts  
   **Grade:** A / High.
5. **[S5] LangGraph — Persistence.** Official documentation; checkpointers, threads, recovery, and durable state. https://docs.langchain.com/oss/python/langgraph/persistence  
   **Grade:** A / High.
6. **[S6] Agent Client Protocol v1 — Schema.** Official protocol; session lifecycle, capability negotiation, permissions, cancellation, load, and resume. https://agentclientprotocol.com/protocol/v1/schema  
   **Grade:** A / High.
7. **[S7] GitHub Actions — Concurrency.** Official documentation; concurrency groups and serialization/queue behavior. https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency  
   **Grade:** A / High.
8. **[S8] GitHub Actions — Deployments and environments.** Official documentation; protection rules, required reviewers, self-review prevention, and gated secrets. https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments  
   **Grade:** A / High.
9. **[S9] GitHub — Artifact attestations.** Official documentation; signed provenance and integrity guarantees. https://docs.github.com/en/actions/concepts/security/artifact-attestations  
   **Grade:** A / High.
10. **[S10] SLSA v1.2 — Build Provenance.** Industry specification; subject digests, builder identity, invocation metadata, dependencies, and verification. https://slsa.dev/spec/v1.2/build-provenance  
    **Grade:** A / High.
11. **[S11] NIST AI 600-1 — Generative AI Profile.** Government standard/profile; provenance, TEVV, monitoring, oversight, incident response, overrides, and escalation. https://doi.org/10.6028/NIST.AI.600-1  
    **Grade:** A / High.
12. **[S12] NIST SP 800-218 — Secure Software Development Framework v1.1.** Government standard; requirements, toolchains, integrity, review, testing, remediation, and root cause. https://doi.org/10.6028/NIST.SP.800-218  
    **Grade:** A / High.
13. **[S13] OWASP — Top 10 for Agentic Applications 2026.** Peer-reviewed industry security guidance; tool misuse, privilege abuse, memory poisoning, cascading failure, human trust, logging, containment, and human gates. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/  
    **Grade:** A- / High.
14. **[S14] GitHub — About protected branches.** Official documentation; required reviews/checks, stale-review dismissal, expected check source, and merge queue. https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches  
    **Grade:** A / High.
15. **[S15] GitHub — Status checks.** Official documentation; check conclusions, required checks, and rerun implications. https://docs.github.com/en/pull-requests/reference/status-checks  
    **Grade:** A / High.
16. **[S16] Playwright — Authentication and persistent-context documentation.** Official documentation; protected authentication state, dedicated user-data directories, and default-profile/multiple-instance warnings. https://playwright.dev/docs/auth and https://playwright.dev/docs/api/class-browsertype#browser-type-launch-persistent-context  
    **Grade:** A / High.
17. **[S17] AWS Durable Execution SDK — Idempotency and retries.** Official documentation; at-least-once behavior, stable tokens, and side-effect semantics. https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/  
    **Grade:** A / High.
18. **[S18] AWS Prescriptive Guidance — Transactional outbox pattern.** Official documentation; atomic state-plus-intent and rollback behavior. https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html  
    **Grade:** A / High.
19. **[S19] Cemri et al. — “Why Do Multi-Agent LLM Systems Fail?”** Primary empirical research; MAST taxonomy, more than 150 traces, five frameworks, expert annotation, and verification/termination failures. NeurIPS 2025 Datasets and Benchmarks track / arXiv. https://openreview.net/forum?id=fAjbYBmonr and https://arxiv.org/abs/2503.13657  
    **Grade:** A- / Medium-High. The taxonomy is well validated; framework/model coverage limits generalization.
20. **[S20] Qian et al. — “Towards a Science of Scaling Agent Systems.”** Primary controlled empirical study; 260 configurations in v3, task-structure effects, coordination overhead, and centralized verification. https://arxiv.org/abs/2512.08296 and https://www.media.mit.edu/projects/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/overview/  
    **Grade:** B+ / Medium. Strong controlled evidence, but a preprint with version-dependent sample counts and evolving results.

