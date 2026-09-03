# Lens 01 — Cross-domain mechanisms for the AI-agent estate

**Research date:** 2026-08-29  
**Scope:** aviation safety, medicine, control theory, intelligence analysis, law/evidence,
operations research, and human factors. Discovery only: no live configuration changes, installs,
secrets, or commits.

## Ground and dedup boundary

Read before external research:

- `.agents/CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`
- `docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md`
- `docs/agentic-perfection/OPEN-THREADS.md`
- `C:\Users\Prekzursil\AGENTS.md`

The following were excluded as already built, planned, absorbed, or explicitly skipped unless a
finding below states a concrete delta: MEL/degraded-mode dispatch; tracer rounds and GameDays;
observational-method trigger plans; alarm stewardship; ATC read-back/hear-back; sterile cockpit;
CCIR; ACH; direct/hearsay provenance tags; spoliation/adverse inference; verified resume and
`disk-verified` provenance; NEWS2; Western Electric rules; ANSI Z1.4 switching; Bühlmann gate
pricing; hysteresis; Smith predictors; circuit breakers; quiescence; andon/HALT; TMS retraction;
prospective memory/open loops; graded autonomy; shadow-mode champion/challenger; world-model
ledgers; cgroup-style memory governor; and generic safety checklists.

This lens therefore reports only mechanisms whose implementation changes the estate in a way not
already specified. “Confidence” separately reflects confidence in the source mechanism and in the
cross-domain transfer; a high score does not mean the item has been empirically validated in this
estate.

## Findings

### 1. LOSA/TEM normal-operations sampling

**Domain:** Aviation safety  
**Recommendation:** EXTEND

**Mechanism:** A Line Operations Safety Audit observes ordinary operations, not just incidents.
The Threat and Error Management model codes: external threats, operator errors, whether each error
was detected, how it was managed, and whether it progressed to an undesired state. The crucial
mechanism is a denominator of normal work and explicit observation of successful recovery.

**Why this estate:** Current telemetry and the closed failure-to-gem loop are heavily
incident-triggered. They can show that a guard fired, but not how often an agent encountered a
threat, recovered without a guard, or converted an innocuous error into a bad state. The estate's
high subagent cancellation rate and RAM pressure make recovery effectiveness more informative than
raw error counts.

**Exact action:** EXTEND the planned per-hook ISR telemetry with a small, periodic, stratified sample
of *completed ordinary runs*. Add a TEM record:
`{threat, error, detected_by, response, recovered, undesired_state, guard_involved}`. Sample by
runtime and task class; do not inspect every run and do not add an always-on process. Use aggregate
rates, not agent punishment. This is a concrete delta over ISR: ISR measures hook firing and
compliance; TEM measures the full threat→error→management→outcome path, including no-hook recovery.

**Sources:**

- FAA, active AC 120-90, *Line Operations Safety Audits*:  
  https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/22478
- ICAO, *Threat and Error Management in Air Traffic Control* (normal-operations monitoring and
  error management): https://skybrary.aero/sites/default/files/bookshelf/516.pdf

**Value × effort:** HIGH × MEDIUM  
**Novelty for this estate:** HIGH — normal-run denominator and recovery-path coding are absent.  
**NATIVE-vs-BUILD:** BUILD-light, by extending the existing event-ledger/ISR path; no new service.  
**Maturity:** Operational aviation method; FAA circular status is active, though the circular is
older because the method is stable.  
**Calibrated confidence:** 0.91 mechanism / 0.78 transfer. Main uncertainty: observer coding
consistency on heterogeneous agent tasks.

---

### 2. Global Trigger Tool for silent agent-caused harm

**Domain:** Medicine / patient safety  
**Recommendation:** WIRE

**Mechanism:** Trigger tools cheaply screen sampled closed records for clues that harm *may* have
occurred; a positive trigger initiates focused review but is not itself treated as proof. They were
created because voluntary incident reports miss substantial harm and full review is too expensive.

**Why this estate:** `tool-result-sentinel` detects immediate failure envelopes, while many estate
harms become visible only later: a revert, repeated repair, reopened task, user correction, missing
promised artifact, or downstream test failure. Those “antidote” events are analogous to clinical
triggers and can reveal silent green-but-broken work without reviewing every transcript.

**Exact action:** WIRE a **retrospective sampled trigger review** into the existing ledger analysis,
not the request path. Candidate triggers:

- file reverted or rewritten within two subsequent turns;
- user correction followed by changed implementation;
- task reopened after a completion claim;
- same tool/action retried three or more times;
- promised artifact absent after the grace window;
- verification passes, then downstream golden journey fails;
- emergency handoff, rollback, or repair skill invoked.

For each positive trigger, review the bounded surrounding ledger slice and classify
`NO_HARM / NEAR_MISS / REWORK / USER_IMPACT / SECURITY_OR_DATA_IMPACT`. Keep trigger precision and
yield so weak triggers can be retired. This extends, rather than duplicates, claim-guard and
failure-to-rescue metrics.

**Sources:**

- Institute for Healthcare Improvement, *IHI Global Trigger Tool for Measuring Adverse Events*:  
  https://www.ihi.org/library/white-papers/ihi-global-trigger-tool-measuring-adverse-events
- AHRQ PSNet, *Triggers and Trigger Tools*:  
  https://psnet.ahrq.gov/primer/triggers-and-trigger-tools

**Value × effort:** VERY HIGH × LOW–MEDIUM  
**Novelty for this estate:** HIGH — detects delayed harm through downstream clues.  
**NATIVE-vs-BUILD:** BUILD-light, as an offline ledger query/report; no daemon.  
**Maturity:** Widely used healthcare-improvement method; transfer to agent traces is novel.  
**Calibrated confidence:** 0.94 mechanism / 0.84 transfer. Main risk is initially low trigger
precision; sampled focused review contains that cost.

---

### 3. Anti-windup for saturated executors

**Domain:** Control theory  
**Recommendation:** EXTEND

**Mechanism:** When an actuator saturates, an integral controller can continue accumulating error
that cannot be acted on, causing overshoot and slow recovery. Anti-windup either conditionally stops
integration or back-calculates the controller state toward what the constrained actuator actually
delivered.

**Why this estate:** Quota exhaustion, authorization denial, low RAM, unavailable MCPs, and a
single-agent cap are actuator saturation. The present circuit-breaker/abandon plans stop repeated
calls, but they do not explicitly unwind the growing queue of dependent intentions, retries, and
stale assumptions. When capacity returns, that backlog can produce a burst of obsolete work.

**Exact action:** EXTEND orchestrator/long-run state with
`SATURATED(resource, since, executable_output, queued_intent)`. On a definitive capacity limit:

1. freeze accumulation of retries and dependent work for that resource;
2. mark downstream queued actions `requires_replan`;
3. back-calculate the active plan to the subset actually completed;
4. when capacity returns, perform one fresh state reconciliation before releasing work;
5. discard superseded retries while preserving the original goal.

This is the missing state-correction layer after the already-planned circuit breaker; it must not
disable capabilities or silently downgrade models.

**Sources:**

- Grimm et al., IEEE Transactions on Automatic Control, *Antiwindup for stable linear systems with
  input saturation*: https://doi.org/10.1109/tac.2003.816965
- 2026 comparative review of clamping and back-calculation mechanisms:  
  https://arxiv.org/html/2606.01959v1

**Value × effort:** HIGH × MEDIUM  
**Novelty for this estate:** HIGH — circuit breaking exists; state unwinding after saturation does
not.  
**NATIVE-vs-BUILD:** BUILD, as a small extension to the existing execution-state schema.  
**Maturity:** Mature industrial-control mechanism; 2026 review confirms continued practice.  
**Calibrated confidence:** 0.96 mechanism / 0.80 transfer. The main design risk is defining which
queued intentions are safely superseded.

---

### 4. Bumpless transfer between models, agents, and tool backends

**Domain:** Control theory / aero-engine control  
**Recommendation:** WIRE

**Mechanism:** Before switching controllers, bumpless transfer aligns the incoming controller's
state and output with the active controller so the switchover does not create a discontinuity.
State/output tracking is especially important when the two controllers have mismatched models.

**Why this estate:** The estate deliberately uses Claude, Codex, Cursor, cloud agents, and fallback
tool rails. Existing handoff and PACE concepts preserve a baton, but do not define a measurable
continuity check at the instant of transfer. A fallback can therefore reinterpret scope, repeat
completed work, or drop a safety constraint while still appearing to have “received context.”

**Exact action:** WIRE a **transfer invariant** into handoff/resume:

1. outgoing executor emits the canonical goal, completed effects, pending actions, constraints,
   artifact hashes, and last verified observation;
2. incoming executor restates the first intended action and predicted state change;
3. compare that action against the outgoing pending-action set and invariants;
4. authorize the switch only if the first action is continuous, or explicitly log and review the
   discontinuity.

Do this only at actual backend/model transfer. It is a concrete delta over read-back: it compares
the incoming *control output*, not merely its prose summary.

**Sources:**

- Shi et al., IEEE, *Bumpless Transfer Control for Switched Linear Systems and its Application to
  Aero-Engines*: https://doi.org/10.1109/tcsi.2021.3060745
- Zhang et al., IEEE Transactions on Industrial Informatics, practical hardware-tested transfer
  design: https://doi.org/10.1109/tii.2023.3254659

**Value × effort:** HIGH × LOW–MEDIUM  
**Novelty for this estate:** MEDIUM-HIGH — baton/read-back is planned, but output-continuity gating
is not.  
**NATIVE-vs-BUILD:** BUILD-light in existing handoff and execution-state contracts.  
**Maturity:** Mature control concept; recent aero-engine implementations are hardware-tested.
Agent transfer is an unvalidated analogy.  
**Calibrated confidence:** 0.94 mechanism / 0.75 transfer.

---

### 5. STPA unsafe-control-action taxonomy

**Domain:** Systems safety / control theory  
**Recommendation:** WIRE

**Mechanism:** Systems-Theoretic Process Analysis treats losses as control and feedback problems,
not merely failed components. It systematically asks whether a control action was: not provided
when required, provided when unsafe, provided too early/late or in the wrong order, or applied too
long/stopped too soon.

**Why this estate:** Many failures arise from interaction among individually “working” hooks,
agents, and time budgets. The verified Stop starvation case is a timing/order control failure, not
a broken check. Component-centric incident review will repeatedly miss that class.

**Exact action:** WIRE the four STPA questions into the existing incident/self-reflect template for
cross-component incidents only. Record controller, controlled process, expected feedback, actual
feedback, context, and unsafe-control-action type. Convert confirmed scenarios into constraints in
the existing world model or dispatcher tests. Do **not** add an always-on STPA engine or require a
full control diagram for ordinary tasks.

**Sources:**

- MIT Partnership for Systems Approaches to Safety and Security, *STPA Handbook*:  
  https://psas.scripts.mit.edu/home/get_file.php?name=STPA_handbook.pdf
- MIT OpenCourseWare, *System Safety: STPA Intro and Basic Components*:  
  https://ocw.mit.edu/courses/16-63j-system-safety-spring-2016/1da33a7bfcaa84de6bf13d874377625e_MIT16_63JS16_LecNotes10.pdf

**Value × effort:** HIGH × LOW  
**Novelty for this estate:** HIGH at the incident-analysis layer.  
**NATIVE-vs-BUILD:** BUILD-light, template/skill text plus later tests on confirmed scenarios.  
**Maturity:** Established system-safety analysis method with an authoritative handbook.  
**Calibrated confidence:** 0.95 mechanism / 0.86 transfer.

---

### 6. Key Assumptions Check, separate from factual TMS

**Domain:** Intelligence analysis  
**Recommendation:** EXTEND

**Mechanism:** A Key Assumptions Check writes down the current analytic line, surfaces stated and
unstated premises, challenges why each must be true, and retains only premises required to sustain
the judgment. It is most useful at project start and before final judgment.

**Why this estate:** The planned TMS retracts factual premises and the world model stores
invariants, but neither guarantees that hidden planning assumptions become first-class objects.
Examples include “the artifact path is stable,” “the provider's failure is transient,” or “these
two sources are independent.” Such assumptions can survive even when every recorded fact is true.

**Exact action:** EXTEND plan review/world-model records with a bounded `key_assumptions` section:
`{assumption, must_be_true_for, basis, confidence, disconfirming_observation, owner}`. Require it
only for complex/high-stakes plans and recheck it before the final gate. On disconfirmation, route
to the existing TMS/lot-recall mechanism rather than inventing another retraction store.

**Sources:**

- CIA Center for the Study of Intelligence, *A Tradecraft Primer* — Key Assumptions Check:  
  https://www.cia.gov/resources/csi/static/Tradecraft-Primer-apr09.pdf
- US Government Publishing Office preservation record for the same government publication:  
  https://www.govinfo.gov/app/details/GOVPUB-PREX3-PURL-gpo587

**Value × effort:** HIGH × LOW  
**Novelty for this estate:** MEDIUM-HIGH — it fills the hidden-assumption gap between world-model
facts and TMS derivations.  
**NATIVE-vs-BUILD:** BUILD-light, schema and review-prompt extension.  
**Maturity:** Established intelligence tradecraft; not a new 2026 technique.  
**Calibrated confidence:** 0.93 mechanism / 0.88 transfer.

---

### 7. Separate source quality from claim credibility

**Domain:** Intelligence analysis  
**Recommendation:** EXTEND

**Mechanism:** Intelligence standards require insight into both the quality/credibility of
underlying sources and the uncertainty of analytic judgments. Sourcing rules also call for source
descriptors and a summary of the strengths, weaknesses, conflicts, and gaps in the source base.
These are distinct questions: a historically strong source can make a weak claim, while a novel
source can provide independently confirmed information.

**Why this estate:** The planned `VERIFIED-DIRECT / HEARSAY-n` tag measures transmission distance,
not whether a source has a good track record or whether this particular claim is independently
corroborated. Collapsing those dimensions can over-trust direct model output and under-trust a
well-corroborated secondary report.

**Exact action:** EXTEND research and agent-mail evidence metadata with two independent fields:

- `source_quality`: track record, access, expertise, currency, possible bias;
- `claim_credibility`: internal consistency, independent corroboration, conflict, and direct
  verification.

For consequential syntheses, add a 2–4 sentence `source_base_summary` naming strongest evidence,
material conflicts, and collection gaps. Keep `HEARSAY-n` as a lineage field; do not replace it.
Avoid a pseudo-precise 6×6 score until inter-rater consistency is tested.

**Sources:**

- ODNI Intelligence Community Directive 203, *Analytic Standards*:  
  https://www.odni.gov/files/documents/ICD/ICD-203.pdf
- ODNI Intelligence Community Directive 206, *Sourcing Requirements for Disseminated Analytic
  Products*: https://www.odni.gov/files/documents/ICD/ICD-206.pdf

**Value × effort:** HIGH × LOW  
**Novelty for this estate:** HIGH relative to the already-planned lineage-only hearsay tag.  
**NATIVE-vs-BUILD:** BUILD-light, result-contract and report-template fields.  
**Maturity:** Active official doctrine; exact estate vocabulary should remain simple until
calibrated.  
**Calibrated confidence:** 0.96 mechanism / 0.90 transfer.

---

### 8. Rule 901-style artifact authentication

**Domain:** Law / evidence  
**Recommendation:** EXTEND

**Mechanism:** Evidence authentication asks whether the item is what its proponent claims it is.
For electronic processes, the foundation includes evidence that the process or system produces an
accurate result. Mere existence is not authentication.

**Why this estate:** Wave C correctly requires promised artifacts to exist on disk, but a
`disk-verified` tag can still credit an empty, stale, wrong-format, unrelated, or partially written
file. This is a concrete gap in the current fail-closed doctrine, whose wording emphasizes
existence and re-reading but does not require claim-specific content validation.

**Exact action:** EXTEND provenance from:

- `agent-claimed`
- `disk-verified`

to include **`disk-authenticated`**, awarded only when a claim-specific predicate passes. Minimum
predicate: correct path, nonempty when expected, expected type parses, required marker/schema is
present, timestamp fits the run, and producer/result ID matches. Add a content hash only for
high-stakes or handoff artifacts; do not hash every edit. `disk-verified` remains useful for simple
existence claims, while completion claims that depend on content require `disk-authenticated`.

**Sources:**

- Federal Rule of Evidence 901, current text and examples:  
  https://www.law.cornell.edu/rules/fre/rule_901
- Federal Rules of Evidence Article IX, including certified electronic-process records:  
  https://www.law.cornell.edu/uscode/text/28a/courtrules-Evid/article-IX

**Value × effort:** VERY HIGH × MEDIUM  
**Novelty for this estate:** VERY HIGH — directly tightens the estate's central completion
AND-gate.  
**NATIVE-vs-BUILD:** BUILD, as a provenance schema plus per-artifact predicates in existing
validators.  
**Maturity:** Current black-letter evidence rule; software transfer is straightforward but must
stay proportional.  
**Calibrated confidence:** 0.98 mechanism / 0.93 transfer.

---

### 9. Rule 702-style bounds on method-generated claims

**Domain:** Law / evidence  
**Recommendation:** EXTEND

**Mechanism:** Current Rule 702 requires sufficient facts/data, reliable principles and methods,
and reliable application to the case. The 2023 amendment emphasizes that each opinion must remain
within what the method and basis can support; methodological adequacy is a gate, not a caveat to
weigh later.

**Why this estate:** Rubric-first judging and calibrated confidence are planned, but a reviewer can
still extrapolate beyond its test: one smoke test becomes “works,” a sampled audit becomes “estate
wide,” or a model benchmark becomes a production guarantee. This is not source provenance; it is
claim-scope control.

**Exact action:** EXTEND `claim-guard` and research result contracts for load-bearing generated
claims with:
`{method, inputs/sample, version, known_error_or_limit, applicability_boundary}`. The final claim
must be mechanically narrowed when it exceeds the method's support—for example, “smoke-passed one
free slug on 2026-08-27,” not “OpenRouter is reliable.” Require this only for consequential
empirical/technical claims, not routine prose.

**Sources:**

- Federal Rule of Evidence 702 and 2023 amendment notes:  
  https://www.law.cornell.edu/rules/fre/rule_702
- Federal Rule of Evidence 901(b)(9), authenticating evidence about a process or system:  
  https://www.law.cornell.edu/rules/fre/rule_901

**Value × effort:** HIGH × LOW–MEDIUM  
**Novelty for this estate:** MEDIUM-HIGH — complements confidence labels with an enforceable
scope-of-inference boundary.  
**NATIVE-vs-BUILD:** BUILD-light in claim-guard/reviewer schemas.  
**Maturity:** Current legal reliability framework; not legal advice and used here only as an
engineering analogy.  
**Calibrated confidence:** 0.97 mechanism / 0.87 transfer.

---

### 10. Deficit Round Robin for bounded hook fairness

**Domain:** Operations research / scheduling  
**Recommendation:** EXTEND

**Mechanism:** Deficit Round Robin gives each queue a service quantum and carries unused entitlement
forward as a deficit. It approximates fair queuing with O(1) scheduling work and is applicable when
service units cannot be subdivided.

**Why this estate:** The Stop dispatcher has a 35-second ceiling while configured checks sum far
beyond it; static sequence means tail checks can be repeatedly starved. The planned one-time
rebalance moves two checks but does not prevent the next workload change from recreating permanent
tail starvation.

**Exact action:** EXTEND the existing dispatcher—after a small fixed set of mandatory fail-closed
checks—with persistent **deficit credits per optional check**:

1. estimate each check's service cost from observed runtime;
2. add weighted quanta each Stop event;
3. run eligible checks whose credit covers estimated cost, highest age/deficit first;
4. debit actual runtime and carry remaining credit forward;
5. retain per-check maximum-age deadlines for critical checks;
6. log `RAN / DEFERRED_BUDGET / FAILED_TO_RUN`; never call deferral a pass.

This does not replace the immediate Stop-event rebalance; it is the concrete long-term scheduler
delta. It preserves all checks and therefore complies with the no-silent-capability-downgrade rule.

**Sources:**

- Shreedhar and Varghese, IEEE/ACM Transactions on Networking, *Efficient fair queuing using
  deficit round-robin*: https://doi.org/10.1109/90.502236
- Original ACM SIGCOMM publication: https://doi.org/10.1145/217391.217453

**Value × effort:** VERY HIGH × MEDIUM  
**Novelty for this estate:** VERY HIGH — current scheduling is a fixed list under a hard ceiling.  
**NATIVE-vs-BUILD:** BUILD, inside the existing dispatcher; no new hook or resident process.  
**Maturity:** Mature, heavily cited O(1) scheduler; application to variable-cost hook checks needs
local runtime calibration.  
**Calibrated confidence:** 0.98 mechanism / 0.90 transfer.

---

### 11. Value-weighted Age of Information for refresh work

**Domain:** Operations research / queueing and scheduling  
**Recommendation:** EXTEND

**Mechanism:** Age of Information measures the freshness of the latest usable status, not simply
transport delay. Age-optimal scheduling balances update freshness against constrained service
capacity, often using an age-penalty function so high-consequence stale states receive service
first.

**Why this estate:** The backlog contains scheduled watchers, readiness refresh, source checks,
router re-embedding, and stale measured claims. Fixed cadences consume scarce RAM even when nothing
important has aged, while low-frequency but safety-relevant facts can remain stale. Existing
`last_verified/expires` memory fields establish age but not a resource-allocation rule.

**Exact action:** EXTEND planned scheduled tasks and memory hygiene with:
`{observed_at, last_verified, staleness_penalty(age), refresh_cost, periodic_floor}`. Within each
existing maintenance window, prioritize items by expected staleness harm per refresh cost. Preserve
a conservative periodic floor and explicit expiry for safety-critical facts; never silently turn a
required check off. Start with three sources only: MCP inventory health, external-tool versions,
and load-bearing “measured YYYY-MM-DD” rules.

**Sources:**

- Yates et al., IEEE Journal on Selected Areas in Communications, *Age of Information: An
  Introduction and Survey*: https://doi.org/10.1109/jsac.2021.3065072
- 2026 IEEE survey on AoI co-design in industrial cyber-physical systems:  
  https://doi.org/10.1109/ticps.2026.3700093

**Value × effort:** HIGH × MEDIUM  
**Novelty for this estate:** HIGH — expiry exists as an idea; value/cost-aware refresh scheduling
does not.  
**NATIVE-vs-BUILD:** BUILD-light in scheduled-task metadata and ordering.  
**Maturity:** Mature research metric with current industrial-system synthesis; local policy remains
experimental.  
**Calibrated confidence:** 0.93 mechanism / 0.79 transfer.

---

### 12. Safety-II positive-adaptation mining

**Domain:** Human factors / resilience engineering  
**Recommendation:** EXTEND

**Mechanism:** Safety-II studies why ordinary work succeeds under variable conditions, not only why
rare events fail. Everyday performance adjustments are treated as a source of resilience; the same
variability can contribute to success or failure depending on context.

**Why this estate:** The closed failure→gem→verify→retire loop is intentionally failure-driven. If
it only mines red outcomes, it can harden the harness around yesterday's incidents and accidentally
remove flexible behaviors that routinely rescue tasks under RAM, tool, or source variability.
LOSA/TEM supplies normal-run observations; Safety-II supplies the learning policy for successful
adaptations.

**Exact action:** EXTEND `/self-reflect` and the proposed TEM sample with a small
`successful_adaptation` record:
`{constraint, intended_workflow, actual_adjustment, why_it_worked, boundary_conditions,
repeat_count}`. Promote an adaptation only after recurrence or a held-out replay; otherwise keep it
as an observation. Review any new forcing function against these records so safety controls do not
erase proven recovery capacity. This is a positive-evidence complement to, not a replacement for,
the failure loop.

**Sources:**

- EUROCONTROL, *From Safety-I to Safety-II: A White Paper*:  
  https://skybrary.aero/sites/default/files/bookshelf/2437.pdf
- EUROCONTROL, *Systems Thinking for Safety: Ten Principles*:  
  https://skybrary.aero/sites/default/files/bookshelf/2882.pdf

**Value × effort:** HIGH × LOW  
**Novelty for this estate:** HIGH — current learning artifacts foreground failures and gems, not
repeatable successful adaptations.  
**NATIVE-vs-BUILD:** BUILD-light in existing reflection/ledger schemas.  
**Maturity:** Established resilience-engineering doctrine; measurement practice is less
standardized than incident review.  
**Calibrated confidence:** 0.92 mechanism / 0.84 transfer.

---

### 13. FRAM-lite for variability resonance across hooks and agents

**Domain:** Human factors / complex socio-technical systems  
**Recommendation:** WIRE selectively

**Mechanism:** The Functional Resonance Analysis Method represents functions through input, output,
precondition, resources, control, and time. It examines how ordinary variability in coupled
functions can combine nonlinearly, rather than looking for one failed component.

**Why this estate:** Chronic RAM pressure, transcript-flush lag, hook timeouts, background task
duration, and agent handoffs each vary within “normal” bounds. Their combination can produce
cancellation, stale artifacts, or starvation even when no component violates its own threshold.
STPA identifies unsafe control actions; FRAM explains how normal timing/resource variability
resonated to create them.

**Exact action:** WIRE a **FRAM-lite table** into postmortems only when at least three components
participated or no single cause explains the incident. For each function record
`I/O/P/R/C/T`, expected range, observed variability, and downstream coupling. Limit analysis to the
critical path and turn one confirmed coupling into a deterministic test or dispatcher constraint.
PRUNE the analysis after the incident; do not maintain a live FRAM model or add software.

**Sources:**

- EUROCONTROL, *Systems Thinking for Safety: Ten Principles* (interactions, flows, trade-offs,
  performance variability): https://skybrary.aero/sites/default/files/bookshelf/2882.pdf
- Systematic review of FRAM in aviation safety:  
  https://doi.org/10.1155/2020/8898903

**Value × effort:** MEDIUM-HIGH × MEDIUM  
**Novelty for this estate:** HIGH, but deliberately narrow to avoid process bloat.  
**NATIVE-vs-BUILD:** NATIVE-to-process — add a postmortem template only; no code or service.  
**Maturity:** Established analysis method; evidence base is largely case-study based.  
**Calibrated confidence:** 0.88 mechanism / 0.70 transfer. Use only after complex incidents, not as
a routine gate.

## Ranked decision queue

### Tier 0 — highest-confidence deltas

1. **Rule 901 artifact authentication** — strengthens the estate's existing completion AND-gate.
2. **Deficit Round Robin hook scheduling** — permanent fix for repeat starvation while preserving
   every check.
3. **Global Trigger Tool** — finds delayed, silent harm that immediate tool-status guards miss.
4. **Key Assumptions Check** — cheap missing layer between world-model facts and TMS retraction.
5. **Dual-axis source/claim grading** — upgrades the planned hearsay lineage without replacing it.

### Tier 1 — high-value measured trials

6. **Anti-windup execution state** for quota/RAM/tool saturation.
7. **LOSA/TEM normal-run sampling**, sharing the future ISR ledger.
8. **Safety-II positive-adaptation mining**, fed by the same sample.
9. **Bumpless transfer invariant** at actual model/backend handoffs.
10. **Rule 702 claim boundaries** in consequential empirical claims.

### Tier 2 — selective tools, not default gates

11. **STPA questions** for cross-component incidents.
12. **Value-weighted Age of Information** for three maintenance sources before broader use.
13. **FRAM-lite** only when a multi-component incident lacks a single adequate cause.

## Convergence and sequencing

- **Normal-work evidence stack:** LOSA/TEM supplies the sample; Safety-II captures successful
  adaptation; the medical Trigger Tool catches delayed harm in closed runs. One sample can support
  all three, avoiding three telemetry systems.
- **Evidence stack:** hearsay lineage → source/claim grading → Rule 901 artifact authentication →
  Rule 702 claim-boundary control. These are separate gates and should share one result contract.
- **Control stack:** circuit breaker detects saturation → anti-windup reconciles accumulated plan
  state → bumpless transfer constrains any backend switch.
- **Dispatcher stack:** perform the already-decided static Stop rebalance first; add DRR only after
  per-check runtime telemetry exists. A budget-deferred check remains `FAILED_TO_RUN`, never PASS.

No finding requires a new MCP, database, orchestration runtime, resident daemon, cloud memory,
credential change, or weakening of an existing capability.

UNIT-COMPLETE: lens-01
