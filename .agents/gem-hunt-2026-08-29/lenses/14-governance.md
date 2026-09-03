# Lens 14 — Governance / meta self-improvement

Date: 29.08.2026  
Mode: discovery and dedup only; no installation or live-policy change.

## Ground and dedup boundary

Read directly: `C:\Users\Prekzursil\AGENTS.md`,
`.agents/CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`,
`docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md`, `docs/agentic-perfection/OPEN-THREADS.md`,
the live dispatcher manifest, `.agents/mel.md`, and the current `gem-hunt`,
`forge-discipline`, `continuous-learning-v2`, `acceptance-review`, `agent-as-a-judge`, and
`writing-skills` contracts.

Already present, so **not findings**:

- generic one-in/one-out and monthly adoption limits;
- skill birth certificates, T+6-week leases, rent audits, active-surface caps, and family merges;
- shadow champion/challenger tests, reversible variant archives, and scripted rollback;
- fresh-context/cross-model review, advisory-until-calibrated judges, and “consensus != verification”;
- `[DISAGREE]` capture and resolution logging;
- project-to-global instinct promotion and active/deprecated/tombstoned skill states;
- the failure→gem→verify→retire loop, fail-closed completion provenance, MEL/tracer rounds,
  forge chaos tests, the six-active-hook principle, and the no-new-daemon/second-orchestrator wall.

The gaps below are narrower governance deltas that those mechanisms do not yet specify.

## Novel deltas

### G14-1 — Budget by active surface area, not item count

**Novel delta.** “At most K adoptions” and one-in/one-out can still approve one large always-on
gate in exchange for one tiny document. Budget the estate by operational surface:

| Surface | Initial weight |
|---|---:|
| Always-on blocking hook / per-tool model call | 8 |
| Always-on advisory hook | 5 |
| Scheduled task or resident process | 3 |
| Routed skill / command | 1 |
| Static policy/document | 0.25 |

Policy: each 30-day wave may add at most **+5 net points** against its measured starting baseline;
the self-improvement subsystem may consume at most **20% of the wave's gross added points**.
Weights are an initial reversible policy experiment, not universal constants. A missing baseline is
`NOT-CHECKED` and prevents promotion, but does not disable existing capability.

**Exact artifact changes.**

1. Add one declarative SSOT, `.agents/governance.yaml`, with `baseline_date`, `surface_inventory`,
   `wave_budget`, `gross_added`, `retired_or_folded`, and `net_points`.
2. Add a short pointer—not the table—to `AGENTS.md`: “Meta-changes must fit the weighted active-
   surface budget in `.agents/governance.yaml`; unknown cost cannot be promoted.”
3. Extend existing `.agents/scripts/harness-audit.js` with an on-demand `governance_budget` check;
   do not add a hook, daemon, or second scorer.

**Tests.** Fixtures must reject (a) an 8-point gate traded for a 1-point skill, (b) unknown
surface type, and (c) a wave over +5; they must accept a hook folded into an existing dispatcher
without an extra process at the correct lower measured delta.

**Value × effort:** Very High × Low-Medium. **Confidence:** High on the gap; Medium on initial weights.

### G14-2 — Lease clocks and rent must be class-aware

**Novel delta.** The existing T+6-week lease is underspecified and usage-count rent would wrongly
kill dormant safety controls. Start a lease only at `activated_at`, after a disk-verified wiring
receipt—not when proposed, generated, or merged. Pause the clock during a recorded MEL outage.
At expiry, move to `review_due`; never auto-remove or silently downgrade.

Rent evidence depends on class:

- safety gate: tracer recall and false-block rate, not organic firing frequency;
- advisory hook: acted-on / emitted ratio and latency;
- skill: qualified uses, success lift, and listing-token cost;
- scheduled task: useful outputs per run and resource cost;
- policy text: prevented contradiction or reduced injected tokens.

**Exact artifact changes.** Add `lease_class`, `activated_at`, `lease_days`, `lease_paused_reason`,
`rent_metric`, `rent_floor`, `review_due`, and `last_rent_receipt` to the same
`.agents/governance.yaml` record. Extend `writing-skills` lifecycle metadata with only
`governance_id`; keep detailed lease state out of every skill body.

**Tests.** A safety gate with zero organic fires but 5/5 tracer detections remains eligible; a
never-wired candidate's lease does not age; a MEL-deferral interval is excluded; expiry produces
`review_due`, not deletion or disablement.

**Value × effort:** Very High × Low. **Confidence:** High.

### G14-3 — Pre-registered, isolated reversible experiments

**Novel delta.** Shadow mode and rollback exist, but there is no rule preventing several policy
changes from sharing one trial and making attribution impossible. Every governance experiment must
pre-register exactly one treatment at one seam, a stable control, baseline artifact hashes,
primary metric, minimum sample, stop-loss, duration, and byte-exact rollback.

Promotion ladder: `proposed -> shadow -> canary -> active`. Evidence used to invent the treatment
cannot also promote it; promotion needs prospective observations collected after registration.
Unrelated edits to the same seam invalidate the comparison and restart the sample.

**Exact artifact changes.** Add an `experiments` section to `.agents/governance.yaml` with
`treatment`, `seam`, `control_hashes`, `primary_metric`, `minimum_n`, `stop_loss`, `started_at`,
`invalidating_changes`, `rollback_hashes`, and `state`. Fold validation into
`harness-audit.js --governance`; no experiment runner is needed.

**Tests.** Reject compound treatments, absent control hashes, missing stop-loss, and promotion from
pre-registration data. A rollback test must restore the exact normalized and raw Windows hashes
recorded at baseline.

**Value × effort:** High × Low-Medium. **Confidence:** High.

### G14-4 — Reviewer independence needs a lineage attestation

**Novel delta.** Different model and fresh context are useful proxies, not proof of independence.
A reviewer can still be contaminated by having authored an artifact, consumed the builder's
rationale, or seen an earlier verdict. First-pass review should receive only requirements/DoD,
the diff, and primary receipts—never the author's self-assessment or prior reviewer conclusions.

Independence classes:

- `independent`: different author/session and blind to prior verdict/rationale;
- `fresh-correlated`: fresh session but same vendor/model family;
- `non-independent`: authored reviewed paths or consumed a prior verdict;
- `unknown`: missing lineage; cannot satisfy an independence gate.

**Exact artifact changes.**

1. Extend `acceptance-review` evidence/verdict JSON and the plan-review rubric with
   `reviewer_runtime`, `vendor`, `model_family`, `session_id`, `authored_paths`,
   `context_sources`, `prior_verdict_seen`, `independence_class`, and `independence_reason`.
2. The convergence pass may see both verdicts only after each blind first pass is sealed.
3. Keep `agent-as-a-judge` advisory; this delta does not promote opinion to a gate.

**Tests.** Same-session review, review of a self-authored path, or prior-verdict exposure must be
`non-independent`; cross-vendor self-review must still fail; same-vendor fresh/blind review is
`fresh-correlated`, not falsely labeled independent.

**Value × effort:** Very High × Medium. **Confidence:** High.

### G14-5 — Disagreement is resolved by discriminator, not vote

**Novel delta.** Capturing `[DISAGREE]` is insufficient. Classify each disagreement as
`empirical`, `requirements`, `value/preference`, or `risk-tolerance`. Empirical disagreements need
a pre-named discriminating test or remain open; requirements ambiguities need source clarification;
value and risk disagreements go to the owner. Majority vote and averaging confidence are prohibited.
Models sharing vendor, prompt lineage, or evidence packet count as one correlation cluster, not
independent votes.

**Exact artifact changes.** Add bounded `disagreements` records to `.agents/governance.yaml` (or
the active project's existing execution-state file) with `claim_a`, `claim_b`, `class`,
`correlation_clusters`, `decisive_receipt`, and terminal state
`resolved_by_receipt | resolved_by_owner | incommensurable`. Add this compact protocol to the
existing council/agent-mail guidance; do not create a disagreement hook.

**Tests.** Two same-vendor agents do not become “2 votes”; an empirical dispute cannot close
without a cited executed receipt; a preference dispute cannot be closed by a benchmark; a timeout
remains unresolved rather than becoming consensus.

**Value × effort:** High × Low. **Confidence:** High.

### G14-6 — Promotion needs two axes and prospective evidence

**Novel delta.** `continuous-learning-v2` can promote the same instinct seen in 2+ projects at
average confidence >=0.8. That conflates reliability with portability and can reuse the same
retrospective evidence that created the candidate.

Track two axes:

- **reliability maturity:** `candidate -> shadowed -> canaried -> proven`;
- **scope maturity:** `project -> project-family -> global`.

Project-to-global advisory promotion requires, after candidate creation, at least three qualifying
outcomes across two genuinely distinct project families, one held-out pressure scenario, and no
owner correction. Global advisory behavior may **never** auto-promote to an enforced hook.
Advisory-to-enforced additionally requires Discipline-Forge chaos proof, canary evidence, and an
explicit owner decision. “Core” requires one completed lease review.

**Exact artifact changes.** Replace the auto-promotion rule in `continuous-learning-v2` with
candidate generation plus the two-axis fields; add `evidence_after`, `project_family`,
`held_out_receipt`, and `owner_decision`. Add those maturity fields to the Forge queue's
`INSTALL.md`; do not alter live settings automatically.

**Tests.** Historical observations cannot count; two clones of one upstream are one project
family; confidence 0.9 alone cannot promote; a proven project behavior remains project-scoped if
portability evidence is absent; an instinct cannot jump directly to enforced.

**Value × effort:** Very High × Medium. **Confidence:** High.

### G14-7 — Consumer-safe deprecation and quarantine

**Novel delta.** `active/deprecated/tombstoned` lacks consumer discovery and replacement-parity
requirements. Add a reversible `quarantined` state: omitted from normal surfacing but still
explicitly invokable. No state transition may silently remove a capability.

Required path:

`active -> deprecated (warn) -> quarantined (owner-approved) -> tombstoned (owner-approved)`

`deprecated` requires a named successor. `quarantined` requires a scoped consumer scan and
replacement-parity receipts. `tombstoned` retains a short file forever and is forbidden while a
live consumer remains. Reversal to `active` must be one metadata edit.

**Exact artifact changes.** Extend `writing-skills` lifecycle metadata with `superseded_by`,
`deprecated_at`, `consumer_scan_receipt`, `parity_receipts`, and `owner_approval`; add
`quarantined` to its state definitions. Reuse `harness-audit.js` for scoped reference checks.

**Tests.** Block quarantine without owner approval, successor, or parity receipt; block tombstone
with any live reference; verify explicit invocation still resolves in quarantine; verify the
tombstone names the successor and cannot be recreated as a duplicate.

**Value × effort:** High × Low-Medium. **Confidence:** High.

### G14-8 — A reflexive SLO and adoption freeze for the improvement system

**Novel delta.** The estate has hook ceilings, but no portfolio rule says the improvement system
must stop adding governance when governance itself becomes the failure source. Give it an error
budget:

- a candidate cannot promote if it increases its event seam's p95 latency by more than 10% or
  250 ms per-tool, whichever is stricter;
- advisory controls need false-positive / ignored-alarm rate <=5% over at least 20 emissions;
- any control that loses receipts, exceeds its timeout, or cannot be measured is `NOT-CHECKED`;
- while the governance SLO is red, only repair, consolidation, rollback, and measurement work may
  enter the next wave—new governance adoption freezes.

This freeze does **not** disable existing features. Any capability/reliability trade-off is
presented to the owner, preserving the standing no-silent-downgrade rule.

**Exact artifact changes.** Add `governance_slo` and `freeze_state` to
`.agents/governance.yaml`; derive metrics from existing ledger/shadow sinks and dispatcher timing.
Extend `harness-audit.js`; do not add telemetry hooks. Put one short normative sentence in
`AGENTS.md`, with details remaining out of the injected prompt.

**Tests.** Synthetic timing and emission fixtures trip each threshold; missing data yields
`NOT-CHECKED`, never green; a red SLO rejects a new candidate but accepts a consolidation change;
the test must assert that no existing feature is automatically disabled.

**Value × effort:** Very High × Medium. **Confidence:** High on the governance rule; Medium on the
initial numeric thresholds pending one baseline month.

### G14-9 — Fail-open controls must enter degraded mode visibly

**Novel delta.** Discipline-Forge deliberately makes generated hooks fail open on garbage to avoid
locking the operator out. That is operationally sensible, but an invisible fail-open can turn a
dead guard into a false assurance. Every control must declare one of:
`advisory`, `fail-closed`, or `fail-open-with-degraded-event`. Plain silent fail-open is not an
allowed production maturity state.

For Forge gates, garbage/error still exits 0, but must append a bounded degraded-mode receipt and
mark its governance record `degraded`; promotion/rent credit pauses until a subsequent tracer round
proves recovery. This composes with MEL rather than replacing it.

**Exact artifact changes.** Add `failure_semantics` and `degraded_receipt` to the Forge pattern
spec and `.agents/governance.yaml`; extend Forge chaos tests to assert both exit 0 and the degraded
receipt. Add a MEL row template reference rather than another liveness mechanism.

**Tests.** Garbage input allows the tool call, creates exactly one bounded degraded receipt, and
does not claim the guard fired; the next passing tracer clears degraded state with a cited receipt;
receipt-write failure remains visible as `FAILED-TO-RUN`, never PASS.

**Value × effort:** Very High × Low-Medium. **Confidence:** High.

## Minimal packaging recommendation

If adopted later, package these deltas as **one declarative registry plus extensions to existing
tools**, not nine mechanisms:

1. `.agents/governance.yaml` — portfolio state, leases, experiments, disagreements, maturity, SLO;
2. `.agents/scripts/harness-audit.js --governance` — deterministic validator;
3. small schema/protocol edits to `writing-skills`, `continuous-learning-v2`,
   `forge-discipline`, `acceptance-review`, and the plan-review rubric;
4. at most four short normative lines in `AGENTS.md`.

No new daemon, MCP, orchestration layer, always-on hook, semantic store, reviewer service, or
automatic installer is warranted.

## Priority by net value

1. **G14-4 reviewer lineage** and **G14-6 two-axis promotion** — close the largest epistemic holes.
2. **G14-2 class-aware rent**, **G14-8 reflexive SLO**, and **G14-9 visible degraded mode** —
   prevent safety and governance controls from becoming false assurance.
3. **G14-1 weighted budget**, **G14-3 isolated experiments**, **G14-5 disagreement protocol**, and
   **G14-7 consumer-safe deprecation** — make the portfolio governable without another runtime.

UNIT-COMPLETE: lens-14
