# Lens 11 — Metrics and evaluation design

**Date:** 29.08.2026  
**Scope:** the local AI estate: Claude/Codex/Cursor and other runtimes, shared hooks and event
ledger, cloud agents, Fabric, basic-memory, and the People Analytics workflow.  
**Decision:** build no second observability platform. Extend the append-only event ledger, reuse
the existing hook terminal and Cursor lifecycle JSONL logs, use `ccusage --offline` for token/cost
facts, and present local rollups through AgentsView where it can consume them.

## 1. Dedup and current-state corrections

This lens does not re-propose the following items:

- The shared event ledger, typed verification receipts, mutation freshness floor, argv
  fingerprints, task/turn/subagent events, terminal hook records, and claim gate already exist.
- Wave B already created observe-mode Cursor hook logs. Enforcement remains gated on measured
  latency and false-positive evidence. One shell-guard smoke run took 4,806 ms against a 2 s hook
  timeout, so latency is a real gate, not a theoretical concern.
- Wave C already established that budget-aborted gates are never green, completion claims require
  disk evidence, and checkpoints are `disk-verified` or `agent-claimed`.
- `harness-audit.js` now emits the deterministic 12-category configuration score (107/120 on
  27.08.2026). That inventory/configuration score is not an operational effectiveness score and
  must not be averaged with the metrics below.
- Per-hook ISR telemetry and failure-to-rescue were already selected as planned/trial items in the
  27.08 decisions. This document supplies their event and evaluation specification.
- The statusline already exposes five-hour and weekly quota use. `ccusage --offline` was already
  the preferred deferred cost source. Do not add Prometheus, Langfuse, LangSmith, a second Sentry,
  an OTEL/Grafana stack, or another resident collector.
- Fabric has stock patterns and an opt-in shared-harness context, but prior reports disagree on
  the inventory count (255 versus 292) and report zero sessions. Pattern count is not a quality
  metric. Treat Fabric effectiveness as `NOT-CHECKED` until real invocations exist.
- The 27.08 OPEN-THREADS file is stale as a live-status source: several items it calls remaining
  were completed in Wave A–D. Metrics must use events and disk artifacts, not backlog prose, for
  completion state.

## 2. Measurement doctrine

1. **Quality is a gate; speed and cost are optimizers.** A cheaper or faster unverified outcome
   is not a win.
2. **Count attempts, not claims.** Timeouts, budget aborts, user-visible failures, and system
   cancellations remain in denominators.
3. **Use task-conditioned rates.** Compare the same task class, stake tier, model/runtime, and
   local/cloud surface. Estate-wide averages are descriptive only.
4. **No self-certification.** Agent prose can create a candidate label, never ground truth.
   Ground truth comes from typed receipts, artifact re-read/hash, deterministic checks, an
   independent held-out evaluation, or an explicit human correction.
5. **Preserve unknown.** `unknown`, `not-checkable`, `failed-to-run`, and missing telemetry are
   first-class states. Never coerce them to pass or silently drop them.
6. **Keep raw events append-only and redacted.** Rollups are reproducible views. Do not store raw
   prompts, tool output, employee-level People Analytics data, credentials, or absolute paths.
7. **Do not target activity.** More tool calls, agents, hooks, memories, Fabric patterns, or cloud
   jobs are not inherently better.

## 3. Units and denominator registry

Every dashboard metric must name one of these versioned populations:

| Unit | Inclusion rule | Required identity |
|---|---|---|
| Eligible session | A user task with a durable goal and at least one agent action; exclude pure Q&A only when the metric requires mutation or verification | `session_key`, `goal_id` |
| Work unit | A declared objective/DoD segment, including every dispatched local or cloud child | `work_unit_id`, `parent_work_unit_id` |
| Tool attempt | Every emitted tool start paired with success, failure, timeout, denial, cancel, or missing-result terminal state | `attempt_id`, `tool_name` |
| Hook opportunity | A host lifecycle event for which the hook is registered, whether or not the hook produced a terminal line | `host_event_id`, `hook_id` |
| Failure episode | First mechanically observed failure plus all attempts serving the same intent until rescue, abandonment, or 24 h expiry | `failure_episode_id`, `intent_fingerprint` |
| Verification claim | A claim family that requires evidence: fixed, tests pass, builds, type clean, coverage, healthy, or E2E pass | `claim_id`, `claim_family` |
| Correction episode | An explicit human correction, deterministic contradiction, failing held-out check, or supersession of a prior claim | `correction_id`, `corrected_event_id` |
| Memory candidate | One proposed durable fact/decision before promotion, including rejected candidates | `memory_candidate_id` |
| Workflow case | One People Analytics input snapshot through a declared deliverable | `case_id`, `input_snapshot_hash` |

The denominator registry is release-versioned. Changes require a changelog and parallel reporting
under old/new definitions for one period.

## 4. Additive event contract

Keep ledger schema v1 readable. Add fields opportunistically; do not fork another event store.

### Common fields

```json
{
  "schema_version": 2,
  "event_id": "content-addressed-or-uuid",
  "kind": "tool_start|tool_result|hook_terminal|claim|artifact_check|...",
  "ts": "UTC ISO-8601",
  "duration_ms": 0,
  "provider": "cursor|claude|codex|fabric|cloud",
  "runtime_version": "string",
  "model_id": "reported model or unknown",
  "execution_surface": "local|cloud|fabric",
  "project_key": "existing project hash",
  "session_key": "salted hash",
  "turn_id": "attributable turn key",
  "work_unit_id": "stable task unit",
  "parent_event_id": "lineage edge",
  "attempt_id": "one execution attempt",
  "intent_fingerprint": "normalized non-content intent hash",
  "task_class": "code|research|document|re|ops|people_analytics|other",
  "stake_tier": "routine|multifile|irreversible",
  "outcome": "pass|fail|unknown|timeout|cancelled|aborted|denied|missing",
  "reason_code": "bounded enum",
  "provenance": "disk-verified|mechanically-verified|human-verified|agent-claimed|not-checkable",
  "source_event_id": "native transcript/log event when available"
}
```

`session_key` is a local salted hash, not a raw transcript/session ID. `intent_fingerprint` must
not contain prompt text. Existing `seq`, `receipt_*`, `result_hash`, `canonical_tree`,
`derived_from`, `parent_id`, and `output_hash` fields remain authoritative.

### Event-specific fields

| Kind | Additive fields |
|---|---|
| `session_start`, `session_end` | `goal_id`, `declared_dod_count`, `end_reason`, `user_wait_ms`, `active_compute_ms` |
| `tool_start`, `tool_result` | `tool_name`, `tool_family`, `server`, `attempt_ordinal`, `exit_code`, existing `receipt_class/status/fp`, `retry_of`, `precondition_changed` |
| `hook_opportunity`, `hook_terminal` | `host_event_id`, `hook_id`, `module_id`, `registered`, `mode=off|shadow|enforce`, `action`, `deadline_ms`, `timed_out`, `injection_chars`, `acted_on` |
| `claim` | `claim_family`, `claim_text_hash`, `required_receipt_classes`, `mutation_floor_seq` |
| `artifact_check` | `claim_id`, `artifact_type`, `artifact_hash`, `exists`, `read_back`, `grace_window_applied`, `check_ordinal` |
| `failure_opened`, `failure_closed` | `failure_episode_id`, `failure_class`, `rescue_eligible`, `exclusion_reason`, `rescue_event_id`, `time_to_rescue_ms` |
| `correction` | `correction_source=human|receipt|heldout|supersession`, `severity`, `corrected_event_id`, `root_cause`, `recurrence_key` |
| `cloud_job` | `cloud_job_id`, `queue_ms`, `startup_ms`, `run_ms`, `checkpoint_count`, `return_channel`, `artifact_manifest_hash`, `local_baseline_id` |
| `fabric_run` | `pattern_id`, `pattern_version_hash`, `context_loaded`, `format_valid`, `baseline_run_id` |
| `usage` | `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_value`, `cost_currency`, `cost_semantics`, `pricing_version`, `source=ccusage|native|invoice` |
| `memory_candidate`, `memory_promotion`, `memory_retrieval` | `candidate_source`, `promotion_basis`, `note_id_hash`, `confidence`, `last_verified`, `expires_at`, `retrieval_rank`, `used_in_event_id`, `superseded_by` |
| `workflow_case` | `workflow_version`, `input_snapshot_hash`, `row_count_in/out`, `lineage_manifest_hash`, `missingness_profile_hash`, `deliverable_hash`, `exception_count` |

Use a small bounded enum for reason codes. Free text belongs in separately redacted diagnostic
artifacts, not the metric stream.

## 5. Metric catalogue

`M` = mechanically measurable, `S` = subjective, `H` = hybrid. Subjective metrics are advisory
unless a human explicitly makes them an acceptance criterion.

### Sessions and work units

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Verified completion rate | M | Eligible work units ending pass with required fresh receipt(s) and disk re-read / all eligible work units | Include aborts, timeouts, and missing artifacts; stratify by task/stake |
| False-green rate | H | Claimed passes later contradicted within 30 d / independently audited claimed passes | Randomly audit passes, not only reported failures |
| Goal fidelity | H | Blind rubric items satisfying declared goal and DoD / sampled completed work units | Judge from frozen goal/DoD, hide model/runtime |
| Reopen rate | M | Completed work units reopened for same recurrence key within 30 d / completed work units with 30 d exposure | Survival-cohort reporting; do not call young work “not reopened” |
| First useful action latency | H | Median time from user prompt to first action later retained in the final solution | Retention is judged after outcome; a fast discarded action earns nothing |
| Scope-drift incidence | M | Work units with out-of-scope mutation / work units with a declared scope | Missing scope is `NOT-CHECKED`, not clean |

### Tools, retries, and failure-to-rescue

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Tool terminal coverage | M | Tool starts with exactly one terminal outcome / all tool starts | Reconcile against native transcript/event source |
| Task-conditioned success | M | Passing attempts / terminal attempts, by tool × intent class | Never rank tools on an unstratified global success rate |
| Useful-tool yield | H | Attempts with a retained output lineage edge / all attempts | Random audit lineage; tool self-report is insufficient |
| Retry burden | M | Attempts after ordinal 1 / failure episodes | Show distribution and p95, not only mean |
| Redundant retry rate | M | Retries with same fingerprint and no changed precondition / all retries | A wait past documented settle time counts as changed precondition |
| Retry rescue yield | M | Failure episodes rescued by a retry / failure episodes receiving a retry | Also report cases where an alternative tool rescued the task |
| Two-strikes adherence | M | Episodes stopped/switched after second unchanged failure / episodes reaching a second unchanged failure | Do not reward abandonment: pair with rescue rate |
| Failure-to-rescue rate | M | Rescue-eligible failure episodes not rescued within session or 24 h / all rescue-eligible episodes | Exclusions limited to explicit user cancellation, definitive auth/entitlement denial, or superseded goal |
| Median time to rescue | M | Time from first failure to verified rescue | Report unresolved episodes separately; no survivor-only average |

“Rescued” means the same intent reaches a mechanically verified pass or a documented alternative
achieves the original DoD. A new error message or an agent saying “fixed” is not rescue.

### Hooks

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Hook opportunity coverage | M | Hook terminal records / host events where the hook was registered | Host events are the denominator; terminal logs cannot denominator themselves |
| Hook timeout/missing rate | M | Timeout or no terminal / hook opportunities | Missing is failure, never silently excluded |
| Hook latency | M | p50/p95/p99 `duration_ms` per event/hook | Keep tail percentiles and RAM-pressure stratum |
| ISR: acted-on rate | H | Hook injections followed by the prescribed action / visible injections | Safety blocks are scored separately; “acted on” needs event lineage |
| True-positive yield | H | Independently confirmed hazards / fired warnings or would-denies | Hidden tracer rounds plus sampled ordinary warnings |
| False-positive rate | H | Independently rejected warnings/would-denies / reviewed firings | Review a random sample; zero user complaints is not zero false positives |
| Miss rate | H | Hidden/synthetic hazards not detected / hazards planted | Tracers are versioned and held out from hook logic authors |
| Net task benefit | H | Difference in verified completion/defect rate versus matched shadow baseline | Safety constraints cannot be traded for latency |

Do not optimize “acted-on rate” alone: a hook can game it by firing only on obvious cases. Always
pair ISR with hidden miss rate and opportunity coverage.

### Cloud agents

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Dispatch acceptance | M | Jobs accepted with durable ID / all dispatch attempts | Include provider rejects and quota failures |
| Verified cloud completion | M | Returned jobs satisfying local DoD and artifact re-read / accepted jobs | Cloud “completed” status is agent-claimed until re-read locally |
| Return completeness | M | Jobs with complete manifest, logs, diff/artifacts, and provenance / returned jobs | Manifest hash checked after download |
| Queue/start/run latency | M | p50/p95 for each phase | Separate queue from compute and human waiting |
| Checkpoint recovery rate | M | Interrupted jobs resumed without lost accepted work / interrupted jobs with checkpoint contract | Chaos-test interruption; do not wait for organic incidents |
| Local non-inferiority | H | Cloud verified-completion difference versus matched local task set | Pair/match on task class, stake, model tier, and DoD |
| Cost per verified completion | M | Cloud invoice/usage cost / verified cloud completions | Failed and unverified jobs remain in cost numerator |

### Fabric

Fabric receives no adoption credit for pattern count. Once there are real runs:

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Context compliance | M | Runs loading the shared-harness context / Fabric runs where required | Verify from invocation record, not pattern text |
| Deterministic format compliance | M | Outputs passing declared schema/format check / evaluated runs | Freeze checker before run |
| Baseline win rate | S | Blind pairwise preference for Fabric output / comparable Fabric-vs-existing-skill pairs | Randomized order, hidden producer, ties allowed |
| Cost/time delta at equal quality | H | Difference from existing skill only among quality-gated pairs | No speed win when quality gate fails |
| Pattern portability | M | Held-out inputs passing without prompt-specific edits / held-out cases | Keep a private holdout set |
| Private-content escape | M | Outputs containing forbidden private markers / tested outputs | Zero-tolerance seeded canaries; never send real secrets |

With fewer than 10 real runs in 30 days, show `INSUFFICIENT-DATA`; do not generate synthetic
activity merely to justify a bridge.

### People Analytics workflow quality

Metrics assess workflow and deliverable quality, not employee performance or the desirability of
an HR decision.

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Input/output reconciliation | M | Cases where every input row is accounted for as retained, excluded-with-reason, or aggregated / all cases | Require signed count manifest; totals alone are insufficient |
| Lineage coverage | M | Published figures linked to source snapshot + transformation version / all published figures | Sample and re-execute links |
| Metric-definition completeness | M | Metrics declaring numerator, denominator, population, exclusions, time window, and unit / all reported metrics | Definitions frozen before result review |
| Reproducibility | M | Cases reproduced from frozen input within declared tolerance / rerun cases | Rerun in clean environment; record dependency versions |
| Missingness/exception disclosure | M | Material missingness and exceptions disclosed / mechanically detected material exceptions | Materiality threshold pre-registered |
| Privacy/disclosure safety | M | Cases with no forbidden direct identifiers or small-cell disclosure / all released cases | Seed canaries; inspect exports, charts, filenames, and metadata |
| Statistical validity | H | Claims passing pre-registered checks for denominator, uncertainty, multiplicity, and sample adequacy / inferential claims | No post-result threshold changes |
| Decision fitness | S | Blind reviewer score for correctness, clarity, actionability, and caveats / sampled deliverables | Reviewer sees input brief and evidence, not producer/model |
| Rework rate | M | Deliverables requiring substantive correction after review / reviewed deliverables | Style-only edits reported separately |
| Time to accepted deliverable | M | Prompt-to-human-accepted elapsed time | Pair with all quality gates; split active compute and waiting |

For protected-group comparisons, report uncertainty and minimum cell size; never optimize a
fairness scalar without the underlying counts and domain review. Employee-level source data must
not enter the general event ledger.

### Verification

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Evidence coverage | M | Evidence-requiring claims with an acceptable fresh typed receipt / all evidence-requiring claims | Claim detector is versioned and tested with paraphrase holdouts |
| Artifact reality rate | M | Claimed artifacts existing and successfully re-read after grace window / all artifact claims | Check twice when initially absent under known flush lag |
| Freshness validity | M | Pass receipts strictly after latest mutation / all receipts offered as proof | Existing mutation floor is authoritative |
| Exact-repro closure | M | Failed argv fingerprints followed by later pass of same fingerprint / “fixed” claims tied to a failed fingerprint | Alternative verification must be explicitly stronger, not merely different |
| Failed-to-run honesty | M | Budget/time/RAM-aborted gates reported failed-to-run / all aborted gates | Any green is a critical false-green |
| Quiescent completion | M | High-stakes completions with two consistent clean passes and no intervening mutation / eligible high-stakes completions | A flaky/changed second pass revokes completion |

### Corrections

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Correction capture | M | Explicit corrections linked to the corrected event and root-cause class / all explicit corrections | Random transcript audit for missed correction language |
| Correction closure | M | Corrections followed by independent verifying evidence / corrections requiring verification | Apology or edited prose is not closure |
| Time to correction | M | Detection-to-verified-fix latency | Keep unresolved corrections in survival analysis |
| Recurrence | M | Closed corrections recurring within 30 d / closed corrections with 30 d exposure | Match on normalized recurrence key |
| Hold-your-ground precision | H | Pushbacks correctly resisted or accepted based on new evidence / sampled pushback episodes | Blind reviewer sees evidence chronology, not outcome author |
| Latent defect rate | H | Defects found in random audits without user correction / audited outputs | Prevents gaming by avoiding questions or discouraging feedback |

### Cost and latency

Cost facts come from `ccusage --offline` JSON where supported, native cloud usage/invoices for
cloud jobs, and statusline rate-limit fields for pacing. Never merge unlike semantics.

| Metric | Type | Definition / denominator | Control |
|---|---|---|---|
| Token mix | M | Input/output/cache-read/cache-write tokens by task/model/runtime | Source and pricing version mandatory |
| Cache efficiency | M | Cache-read tokens / cache-eligible input tokens | Compare only stable-prefix-compatible sessions |
| Cost per verified completion | M | Estimated API-equivalent or actual cost / verified work units | Report semantics separately; failures stay in numerator |
| Cost per rescued episode | M | Cost incurred from first failure through rescue / rescued episodes | Also report unresolved-failure cost |
| Critical-path latency | M | Sum of non-overlapping events on the task critical path | Parallel time is not double-counted |
| User wait | M | Prompt-to-response wall time less explicitly backgrounded intervals | Show background completion separately |
| Hook overhead share | M | Hook critical-path ms / local active critical-path ms | Never reduce safety coverage to hit this target |

Raw spend and total tokens are capacity facts, not performance scores. Subscription quota use is
not dollar cost. Weekly consumption must not be maximized for its own sake.

### Memory promotion and use

| Metric | Type | Numerator / denominator | Anti-Goodhart control |
|---|---|---|---|
| Success-gated promotion | M | Promotions backed by a verified decision/fact/milestone / all promotions | No target for promotion volume |
| Promotion precision | H | Mature promotions later used without correction / promotions old enough for evaluation | Minimum 30 d exposure; unused is separate from wrong |
| Retrieval usefulness | H | Retrieved notes materially used in a retained decision/action / surfaced retrievals | Blind sample audit; rank position recorded |
| Stale-memory exposure | M | Retrievals of expired/superseded facts without warning / retrievals of expired/superseded facts | Zero-tolerance for silent exposure, not for warned historical retrieval |
| Correction propagation | M | Falsified facts whose known descendants were tainted/superseded / falsified facts with descendants | Existing `derived_from` edges define observable denominator |
| Promotion latency | M | Verified reusable learning to promotion time | Pair with precision; faster wrong promotion is worse |
| Memory availability | M | Intended writes durably readable after write/spool reconciliation / intended writes | Server “healthy” does not prove the note exists |

Do not use “facts added” as a success KPI. It is an inventory count and a bloat pressure signal.

## 6. Subjective evaluation protocol

Subjective evaluation is necessary for goal fidelity, decision fitness, clarity, and usefulness,
but it cannot silently become a mechanical gate.

- Use a frozen 4-point rubric with observable anchors: `0 harmful/wrong`, `1 major rework`,
  `2 minor rework`, `3 accepted as-is`.
- Blind model, runtime, tool path, and cost. Randomize pairwise output order.
- Include the original brief, declared constraints, and allowed evidence; exclude agent rationale.
- Use two independent raters for high-stakes samples. Report agreement and adjudicated score.
- Agent-as-a-Judge may prioritize samples or explain rubric misses, but remains advisory.
- Human corrections are high-value labels but selection-biased; pair them with random audits.
- Report sample size and Wilson confidence interval. Under 20 judged items per stratum is
  `INSUFFICIENT-DATA`, not a trend.

## 7. Evaluation programme

### Continuous mechanical evaluation

- Validate JSONL parseability, event joins, terminal coverage, clock sanity, and required fields
  daily.
- Run existing synthetic guard tracer rounds on a versioned hidden suite.
- Reconcile `ccusage` session totals to locally observed session keys without importing transcript
  content.
- Re-read promised artifacts after the existing grace window.
- Treat collector failure as a visible `METRICS-DEGRADED` event; metrics may not certify themselves.

### Weekly sampled evaluation

- Randomly select at least 10 completed work units or 10%, whichever is larger.
- Oversample high-stakes, cloud-returned, corrected, and memory-assisted work, but publish weighted
  estate estimates and the oversampled strata separately.
- Audit false greens, goal fidelity, scope drift, tool usefulness, correction capture, and memory
  usefulness.
- Review every safety-hook firing until volume exceeds 50/week; then review all denies plus a
  random sample of warnings and non-firings.

### Release/model-change evaluation

- Maintain a private, versioned held-out suite stratified across code, research, documents,
  operations, People Analytics, and long-running rescue cases.
- Run champion/challenger in shadow or paired mode. Freeze tasks, rubric, and acceptance thresholds
  before seeing results.
- Include negative controls: zero-test runs, exit-code laundering, absent promised artifacts,
  budget-aborted gates, stale receipts after mutation, prompt-injection canaries, tool timeouts,
  cloud interruption, and falsified memory descendants.
- Rebaseline after a model, hook, routing, or workflow-version change. Never splice unlike versions
  into one trend line.

## 8. Anti-Goodhart controls

1. No single estate “quality score.” Publish a small scorecard with hard red gates.
2. Freeze definitions and thresholds before each evaluation window.
3. Keep failures, unknowns, cancellations, and missing telemetry visible.
4. Cap manual exclusions at 2% of a denominator; list every exclusion reason.
5. Stratify by task class, stake, model, runtime, and local/cloud surface.
6. Use quality-adjusted cost/latency; never speed-only or cost-only leaderboards.
7. Maintain hidden holdouts and synthetic negative controls.
8. Audit a random sample of passes and non-firings, not only failures.
9. Require external evidence for labels; model confidence and self-reported success are features,
   not outcomes.
10. Report distributions and p95/p99 tails. Means conceal hangs and memory-pressure failures.
11. Use confidence intervals and minimum sample sizes; do not rank noise.
12. Preserve the immutable raw event and rubric version behind every rollup.
13. Track denominator drift, telemetry gaps, and label-source mix on every dashboard.
14. Never pay agents, route work, or prune tools from one metric. Require a balanced review of
   verified quality, rescue, latency, cost, and task coverage.

## 9. Dashboards using existing surfaces

AgentsView should be a read-only presentation layer over locally generated rollups. If it cannot
consume a view, generate a static local JSON/CSV report; do not add a SaaS.

1. **Estate health:** eligible work units, verified completion, false-green, unrescued failures,
   correction recurrence, telemetry completeness, cost per verified completion.
2. **Reliability funnel:** goal → work unit → mutation → claim → fresh receipt → artifact re-read →
   accepted; show loss at every step.
3. **Tools and rescue:** failure episodes by reason, redundant retries, tool-switch rescues,
   unresolved age, time/cost to rescue.
4. **Hook stewardship:** opportunities, terminal coverage, p95/p99 latency, timeout/missing,
   would-denies/denies, false-positive review, hidden-tracer miss rate, acted-on rate.
5. **Cloud and Fabric:** queue/run/return, artifact completeness, local non-inferiority, checkpoint
   recovery, Fabric sample sufficiency and blind win rate.
6. **People Analytics:** case reconciliation, lineage, reproducibility, privacy gates, exceptions,
   reviewer score, substantive rework, accepted-deliverable latency.
7. **Cost/latency:** `ccusage` token/cache/cost facts by task mix, user wait, critical path, hook
   share, unresolved-failure cost. Keep estimated API-equivalent and actual invoice views separate.
8. **Memory/corrections:** candidates/promotions, success-gating, retrieval usefulness, stale
   exposure, supersession/taint propagation, repeated correction keys.

Every panel shows period, denominator, missing-data rate, sample size, confidence interval where
applicable, schema/rubric version, and last successful refresh.

## 10. Acceptance thresholds

These are rollout gates, not permanent targets. Revisit after a 30-day baseline without weakening
the hard safety/verification invariants.

### Hard invariants — immediate

- **0** budget/time/RAM-aborted gates recorded as pass.
- **100%** of artifact-requiring completion claims have a successful disk re-read after any grace
  window; otherwise the outcome is unverified.
- **100%** of high-stakes claims have fresh acceptable evidence.
- **0** known credential/private People Analytics data values in telemetry or released artifacts.
- **0** silent stale-memory exposures; expired/superseded facts must be flagged.
- **0** cloud jobs credited complete from provider status alone.

### Telemetry integrity

- JSONL parse success **>=99.9%**.
- Tool terminal coverage **>=99.5%**.
- Hook opportunity coverage **>=99.5%** before any shadow hook moves to enforcement.
- Joinability across session/work-unit/attempt IDs **>=99%**; unknown identity **<=1%**.
- Cost-source attribution and `cost_semantics` present on **100%** of cost records.

### Verification and outcome quality

- Routine/multifile fresh-evidence coverage **>=95% / >=98%**; high-stakes **100%**.
- Audited false-green rate **<=1%** overall and **0 critical false greens**.
- Exact-repro closure on “fixed” claims tied to a failed fingerprint **>=95%**.
- Quiescent two-pass completion for eligible high-stakes work **100%**.
- 30-day substantive reopen rate: establish baseline first; alert on **>5 percentage-point** or
  **>25% relative** deterioration with adequate sample size.

### Rescue, retries, and corrections

- Rescue-eligible failure rescue rate **>=80%** overall and **>=95%** for critical infrastructure
  failures.
- Redundant retry rate **<=10%**.
- Two-strikes adherence **>=95%**.
- Correction closure with independent evidence **100%** where mechanically verifiable.
- 30-day correction recurrence **<=10%** after at least 20 exposed corrections.

### Hook promotion from shadow to enforce

- At least **500** observed opportunities across at least **7 days**.
- Timeout/missing terminal rate **<=0.1%**.
- Pre-action safety hook p95 **<=750 ms**, p99 **<1,500 ms**, and no deadline exceedance in the
  latest 200 opportunities. Given the observed 4,806 ms run, the current shell guard does not meet
  this gate.
- Zero confirmed false-positive would-denies in the sample; with zero in 300 reviewed cases, note
  that the statistical upper bound is still about 1%, not “proven zero.”
- Hidden tracer detection **100%** for critical cases and **>=99%** overall.
- Promotion cannot reduce host-event coverage or disable a feature to buy latency.

### Cloud/Fabric

- Cloud return completeness **>=99%** and interrupted-job checkpoint recovery **>=95%** in chaos
  tests.
- Cloud verified completion is non-inferior to matched local work by no more than **5 percentage
  points**, with no critical safety regression.
- Cost per verified cloud completion may regress no more than **20%** versus its frozen matched
  baseline unless quality improves by a pre-declared amount.
- Fabric stays `INSUFFICIENT-DATA` below 10 real runs/30 d. Promotion over an existing skill
  requires at least 20 blinded pairs, format compliance **>=95%**, no private-canary escape, and a
  pairwise win rate **>=60%** with the confidence interval reported.

### People Analytics

- Input/output reconciliation, published-figure lineage, and reproducibility: **100%**.
- Privacy/direct-identifier/small-cell disclosure violations: **0**.
- Metric-definition completeness: **100%** for published metrics.
- Material missingness/exception disclosure: **100%**.
- Inferential claims failing pre-registered validity checks: **0 released**.
- Substantive rework: baseline for 30 days, then alert above **10%** or a 5-point deterioration.
- Blind decision-fitness median **>=2/3**, with no sampled deliverable scored `0`.

### Cost and memory

- No absolute token-spend target until task-mix baseline exists.
- Quality-gated cost per verified completion must not deteriorate by **>20%** release-over-release
  without a documented task-mix or quality explanation.
- Success-gated memory promotions **100%**.
- Silent expired/superseded retrievals **0**.
- Correction propagation to all known `derived_from` descendants **100%**.
- No target for number of memories promoted; a rising count without measured use is a warning.

## 11. Minimal implementation sequence

1. Add only the identity/outcome fields needed to join existing ledger, terminal, Cursor lifecycle,
   and `ccusage` records. Start in observe mode.
2. Build a local deterministic rollup command that emits versioned JSON. It reads, never rewrites,
   raw JSONL.
3. Add denominator and telemetry-integrity tests before publishing any rate.
4. Populate AgentsView from the rollup if supported; otherwise publish static local reports.
5. Run 30 days of baseline plus the hidden negative-control suite.
6. Only then use thresholds for hook promotion, cloud routing, Fabric adoption, or memory lifecycle
   decisions.

The first useful dashboard is not a grand score. It is the reliability funnel plus three red
signals: false green, unrescued failure, and missing telemetry.

UNIT-COMPLETE: lens-11
