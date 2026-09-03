# Lens 02 — Frontier harness: reliability, memory, context, orchestration, evaluation, self-improvement

**Cutoff:** 29.08.2026  
**Mode:** discovery and deduplicated decision queue only; nothing installed or enabled.  
**Search lanes executed:** arXiv and its API, official paper artifacts, GitHub repositories/API,
vendor changelogs and documentation, PyPI, npm, and benchmark/project pages. This was not a
keyword-only GitHub search.

## Ground and dedup

Read before discovery:

- `.agents/CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`
- `docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md`
- `docs/agentic-perfection/OPEN-THREADS.md`
- `C:\Users\Prekzursil\AGENTS.md`
- Current-hunt lenses 05, 09, 11, and 12, to avoid cross-lens duplication

Not re-proposed: ACE, GEPA, G-Memory, MaAS, Agent-as-a-Judge, DGM/SEAL/ADAS, MAST, rubric-first
judging, verified-resume/provenance, eviction landmarks, typed episode eviction, per-hook ISR,
failure-to-rescue, variant archives, skill lifecycle, the event ledger, a second memory store,
another orchestrator, an observability SaaS, or an always-on collector.

The useful deltas are narrower:

1. preserve session constraints outside the compactor;
2. test compaction at the boundary where it happens;
3. verify harness edits only on behavior-relevant cases with attributable evidence;
4. add failure-layer and repair-owner fields to existing evidence;
5. evaluate memory as environment knowledge, not conversational recall;
6. inject and measure cascades instead of waiting for organic failures;
7. calibrate failure attribution on full traces;
8. consume native hook metrics where the runtime already emits them;
9. borrow diversity-aware failure sampling without accepting self-preference as truth.

## Ranked decision queue

| # | Finding | REC | Value × effort | NATIVE vs BUILD | Confidence |
|---|---|---|---|---|---|
| F1 | COMPINT session-constraint sidecar | ADOPT design + tests | **Very high × low–medium** | BUILD on existing pre/post-compact seam | High |
| F2 | HarnessLens attributable-evidence gate | ADOPT into variant archive | **Very high × medium** | BUILD; borrow algorithm, not runtime | High |
| F3 | TRACE boundary-local compaction evaluation | TRIAL protocol; no code copy yet | **High × medium** | BUILD evaluator | Medium-high |
| F4 | ERCA six-layer repair ownership | ADOPT schema delta | **High × low** | BUILD into ledger/rollup | High |
| F5 | LongMemEval-V2 environment-memory slice | ADOPT bounded benchmark slice | **High × medium** | BUILD adapter; no new store | High |
| F6 | OrchestraBench cascade drills | ADOPT metric + small fixture set | **High × low–medium** | BUILD into existing tracer/harness audit | Medium-high |
| F7 | TraceElephant who-and-when calibration | TRIAL fixture subset | **High × medium** | BUILD adapter | High on method; medium on license scope |
| F8 | Codex native hook telemetry | ENABLE/consume after local check | **High × low** | **NATIVE** Codex; BUILD only joins | High |
| F9 | RHO difficulty-diversity coreset | BORROW selector only | **Medium-high × low–medium** | BUILD into offline eval selector | Medium-high |
| F10 | Claude per-agent prompt-cache TTL | CONDITIONAL TRIAL | **Medium × trivial** | **NATIVE** Claude Code | High on feature; low applicability |

---

## F1 — Session constraints need an architectural sidecar, not a better summary prompt

**Sources**

- Paper: <https://arxiv.org/abs/2608.11242>
- Repository: <https://github.com/ZhiqiEliWang/compaction-integrity>
- Project page: <https://zhiqieliwang.github.io/compaction-integrity/>

**Evidence and concrete delta**

COMPINT reports that tested compactors retained only 17% of injected session constraints on
average. Its training-free extractor reads user turns, maintains a live set of session-lifetime
constraints, and appends that set after compaction; reported retention exceeds 90% in all three
scenarios. Targeted compactor prompting remained below 40% on WildChat, supporting architectural
separation rather than prompt polishing.

This is not the already-planned eviction-landmark gem. Landmarks preserve factual trajectory
state. The net-new class is a typed, user-authored constraint whose lifetime is the session:
“show me the draft before sending,” “do not delete,” “do not touch X.” These must bypass lossy
summarization.

**Exact borrow line**

`SC_PIN := constraints extracted only from user-authored turns whose scope is the current session; after every compaction append SC_PIN unchanged, and verify behavioral compliance with forced-choice probes rather than text-presence alone.`

**Fit**

- Ride the existing `PreCompact`/`PostCompact` or precompact carrier; no new daemon or memory store.
- Store the pin set as non-semantic session control state, not in basic-memory.
- Treat extraction as candidate generation: explicit owner constraints may be pinned directly;
  inferred constraints require a conservative confidence gate.
- Pair text retention with behavior probes; a summary can contain a rule that the agent still ignores.

**Maturity audit**

- Maintenance: repository pushed 18.08.2026; not archived.
- License: MIT.
- Tests: no dedicated `tests/` tree found in the repository root; robustness/human-agreement
  evaluation exists, but that is not a unit-test suite.
- Examples: extensive reproducibility scripts for RQ1–RQ4, direct extractor command, resume-safe runs.
- Maturity: **arXiv v1 / pre-1.0 research artifact**.

**Risk:** false-positive pinning can silently elevate ordinary prose to a durable rule. Start with
explicit constraints and a shadow-mode extractor-diff corpus.  
**Confidence:** HIGH on the failure and intervention direction; MEDIUM on transfer to this harness
until tested on real compaction events.

---

## F2 — Harness evolution should verify the behavior touched by the edit

**Sources**

- Paper, published 27.08.2026: <https://arxiv.org/abs/2608.27311>
- Repository: <https://github.com/jhxu5214/HarnessLens>

**Evidence and concrete delta**

HarnessLens selects verification tasks related to a proposed harness modification and requires
attributable evidence rather than accepting an aggregate score increase. It reports 7.6–13.6%
average held-out improvement across OpenCode, Codex, and Pi under a 200-unit budget. Its ablation
is the useful part: fixed/random task batches waste verification on unrelated behavior, while a
metric-only gate accepts unsupported gains.

This directly sharpens the already-planned empirical variant archive. The archive says “test before
promotion”; HarnessLens supplies the missing test-selection and attribution rule. It also gives a
mechanical verdict for inert skills: if the candidate was never invoked, it produced no attributable
change and is rejected.

**Exact borrow line**

`Promote a harness candidate only on a frozen behavior-relevant task slice when the targeted behavior shows an attributable recovery, the candidate was actually exercised, and no attributable regression appears in two confirmation rounds.`

**Fit**

- Use the existing event-ledger lineage and Lens 11 denominator contract.
- Candidate, baseline, task slice, and verifier versions must be immutable artifacts.
- Keep private held-out tasks inaccessible to the proposer.
- A budget-aborted confirmation round is `FAILED-TO-RUN`, never promotion.

**Maturity audit**

- Maintenance: code pushed 27.08.2026, the paper’s publication day; not archived.
- License: MIT; third-party benchmark assets retain their own licenses.
- Tests: repository has `tests/`, end-to-end runners, and baseline/candidate runners.
- Examples: configs, benchmark docs, scripts, and worked evolution traces.
- Maturity: **arXiv v1 / pre-1.0 research code**, zero-star launch at inspection time; very new.

**Risk:** behavior similarity itself can leak test intent or overfit a narrow cluster. Freeze the
selector before outcomes and retain a broad negative-control slice.  
**Confidence:** HIGH on the actionable gate; MEDIUM-HIGH on reported effect-size transfer.

---

## F3 — Evaluate every compaction boundary with paired continuations

**Sources**

- Paper: <https://arxiv.org/abs/2608.06503>
- Repository: <https://github.com/nokia-applied-research/Trace>

**Evidence and concrete delta**

TRACE forks paired closed-loop continuations from the same environment state before and after a
compaction boundary. It measures blocked actions and repeated/refetch exploration instead of waiting
for terminal task accuracy to reveal damage. This is a precise evaluator for the already-planned
typed eviction policy and F1 pin set.

It also advances Lens 11: “task completed” can remain unchanged while compression increases the
interaction cost needed to reacquire dropped state. Compaction evaluation therefore needs retrieval
calls, repeated exploration, and blocked actions in addition to completion.

**Exact borrow line**

`For each candidate compaction change, fork baseline and compacted continuations from one frozen environment snapshot; compare blocked actions, state-refetch calls, repeated exploration, verified outcome, and context cost; promote only a non-inferior paired result.`

**Maturity audit**

- Maintenance: pushed 06.08.2026; not archived.
- License: **none**. The repository explicitly says it does not yet carry a license file.
- Tests: 24 core + 28 optimizer + 6 frozen-data reproduction tests are documented.
- Examples: frozen AppWorld data, protocol/data/reproduction docs, collection tooling.
- Maturity: **arXiv v1 / preliminary study / pre-1.0**.

**Decision:** borrow the independently described protocol, not repository code or data, until a
license is added.  
**Confidence:** MEDIUM-HIGH on the measurement design; MEDIUM on generality beyond the initial
AppWorld study.

---

## F4 — Record which reliability layer failed and who owns the repair

**Sources**

- Monograph: <https://arxiv.org/abs/2608.13867>
- Companion repository: <https://github.com/sjarmak/engineering-reliable-coding-agents>
- Minimum pass: <https://github.com/sjarmak/engineering-reliable-coding-agents/blob/main/protocols/minimum-reliability-pass.md>

**Evidence and concrete delta**

The 314-page review treats a coding agent as a dependency chain across measurement, grading,
containment/recovery, retrieval/context, review/accountability, and allocation/cost. The companion
contains 206 versioned reliability records, protocols, evidence links, and explicit “what this
cannot establish” boundaries.

Lens 11 already defines excellent event and metric schemas, but its failure records do not name the
failed layer, enforcement point, or repair owner. Those fields stop a model miss from being “fixed”
in prompts when the actual defect is telemetry, state, permissions, verification, or scheduling.

**Exact borrow line**

`Every reliability finding records failing_layer, enforcement_point, repair_owner, retained_artifact, evidence_strength, and cannot_establish; a fix is rejected when it targets a different layer without a causal bridge.`

**Fit**

- Add fields to the existing ledger/rollup, not another catalog database.
- Use the companion as a read-only reference; do not copy its five skills into the 358-skill SSOT.
- Map its minimum six records onto existing receipts and harness-audit outputs.

**Maturity audit**

- Maintenance: repository pushed 24.08.2026; release 1.1.0.
- License: scripts/protocols/skills Apache-2.0; manuscript/companion CC-BY-4.0, with explicit scope file.
- Tests: Python release-count test, Node protocol-scaffold test, checksums, and full release gate.
- Examples: six runnable protocols, generated `not-run` records, worked factory examples in sibling companion.
- Maturity: **1.1.0 but young**; coupling annotations are explicitly provisional.

**Confidence:** HIGH for the schema and ownership discipline; directional, not proof that its full
catalog transfers to this estate.

---

## F5 — Test memory for environment gotchas and premise awareness, not only recall

**Sources**

- Paper: <https://arxiv.org/abs/2605.12493>
- Repository: <https://github.com/xiaowu0162/LongMemEval-V2>
- Project/leaderboard: <https://xiaowu0162.github.io/longmemeval-v2/>

**Evidence and concrete delta**

LongMemEval-V2 evaluates static state, dynamic state, workflow knowledge, environment gotchas, and
premise awareness over web/enterprise trajectories, while scoring both accuracy and query latency.
The official repository contains 451 curated questions, histories up to 115M tokens, multiple
baselines, a privacy-tested backend API, and an August AgentRunbook-C V2 update.

This does not justify a new memory system. The useful borrow is a small estate-specific benchmark
for basic-memory and recall injection. The last two dimensions map directly to documented pain:
remembering local failure modes and rejecting assumptions that are valid elsewhere but false on
this machine.

**Exact borrow line**

`Memory evaluation vector := {static_state, dynamic_state, workflow, environment_gotcha, premise_awareness}; score answer accuracy plus p95 retrieval latency, and expose to the memory backend only the query plus an opaque invocation ID.`

**Fit**

- Implement a small private slice over existing notes and event-ledger facts.
- Keep gold answers and task metadata outside the retrieval process.
- Include stale/superseded and changed-premise cases from Lens 09.
- Report `NoMem` and current basic-memory as paired baselines; no benchmark win can authorize a
  second writer or graph store.

**Maturity audit**

- Maintenance: pushed 09.08.2026; repository activity through 28.08; not archived.
- License: Apache-2.0.
- Tests: `tests/` includes query-privacy and opaque-context checks.
- Examples: baseline scripts, backend interface, no-retrieval and indexed implementations, leaderboard packaging.
- Maturity: paper labels itself **Work in Progress / pre-1.0**, despite a strong public artifact.

**Risk:** the full benchmark is far too heavy for this RAM-constrained machine. Borrow the
capability taxonomy and privacy tests; do not run 115M-token tiers locally.  
**Confidence:** HIGH.

---

## F6 — Add cascade radius and retryability to the existing tracer programme

**Sources**

- Paper: <https://arxiv.org/abs/2608.05263>
- Closest prior fault-injection artifact: <https://arxiv.org/abs/2602.19843>
- MAS-FIRE data repository: <https://github.com/wxhhxn/MASFIRE>

**Evidence and concrete delta**

OrchestraBench measures per-failure-mode recovery, cascade radius, time to detection, and
decomposition fidelity. Its controlled probes found tool faults recoverable, ambiguous delegation
partly recoverable, and three latent/semantic faults unrecovered; unchanged retries reproduced the
latent fault and merely increased detection time. Cascade radius grew from 0.9 to 4.7 as pipeline
depth increased from 3 to 7.

Lens 11 already specifies failure-to-rescue and redundant retries. The new measurement is how many
downstream stages accept contaminated state before containment, plus whether the retry precondition
changed.

**Exact borrow line**

`Each seeded fault drill records injected_mode, injected_stage, retryable_class, precondition_changed, cascade_radius, time_to_detection, and recovery_completeness; blind retry is forbidden for latent/semantic faults.`

**Fit**

- Extend the existing guard tracer and harness-audit drills with 5–8 deterministic fault fixtures.
- Use trusted clean state only as an explicit oracle arm; do not report it as autonomous recovery.
- Keep arithmetic/file-state fixtures locally verifiable and seed-reproducible.

**Maturity audit**

- OrchestraBench: arXiv v1; paper reports Apache-2.0 code, committed artifacts, 151 offline tests,
  fixed seeds, and Python 3.10–3.12 support, but no discoverable repository URL was exposed by the
  arXiv metadata. Treat those quality claims as paper-reported, not independently inspected.
- MAS-FIRE: data repository, no detected license, no dedicated tests, examples are benchmark datasets;
  Zenodo 1.0 exists. It is evidence, not code to adopt.
- Maturity: **research artifact / pre-1.0**.

**Confidence:** MEDIUM-HIGH on the metrics and retry distinction; MEDIUM on reusable artifact quality.

---

## F7 — Failure attribution needs “who” plus the decisive “when”

**Sources**

- ACL 2026 paper: <https://aclanthology.org/2026.acl-long.912/>
- Repository: <https://github.com/TraceElephant/TraceElephant>
- Dataset: <https://huggingface.co/datasets/TraceElephant/TraceElephant>

**Evidence and concrete delta**

TraceElephant provides 220 annotated failure traces from three agentic systems and labels both the
responsible component and the decisive step where failure became inevitable. Full traces improved
attribution accuracy by up to 76.5% over partial observation.

This does not justify storing raw subordinate transcripts in the orchestrator; EPSS still holds.
Instead, the full trace belongs in the evidence plane, while the orchestrator receives a structured
attribution record. It also gives a calibration fixture for Lens 11’s `root_cause` field and Lens
12’s unread-alarm problem.

**Exact borrow line**

`Root-cause record := {responsible_component, decisive_step, upstream_evidence_ids, counterfactual_fix, observability_complete}; if the decisive step cannot be located from retained evidence, report OBSERVABILITY-GAP, not a guessed cause.`

**Maturity audit**

- Maintenance: repository pushed 27.04.2026, metadata updated 23.08; not archived.
- License: top-level CC-BY-4.0 clearly covers traces/data; the paper promises a permissive code
  license, but the repository does not clearly separate code license scope. Treat code reuse as ambiguous.
- Tests: no conventional unit-test suite identified; one-click `run_test.sh` evaluation exists.
- Examples: public annotated traces, collection scripts, reproducible environments.
- Maturity: ACL 2026 benchmark, but **research code / pre-1.0**.

**Decision:** use a fixture subset and schema concepts; do not copy code until license scope is clear.  
**Confidence:** HIGH on benchmark findings, MEDIUM on integration readiness.

---

## F8 — Codex already emits the first half of per-hook ISR telemetry

**Sources**

- Official configuration/metrics catalog: <https://developers.openai.com/codex/config-advanced>
- Official hooks guide: <https://developers.openai.com/codex/hooks>
- Changelog: <https://developers.openai.com/codex/changelog>
- Source: <https://github.com/openai/codex>

**Evidence and concrete delta**

Codex exposes native OpenTelemetry counters and histograms:
`codex.hooks.run{hook_name,source,status}` and
`codex.hooks.run.duration_ms{hook_name,source,status}`. Its current hooks surface also includes
trust-by-definition-hash, output spill handling, lifecycle events, and TUI warnings.

The 27.08 queue and Lens 11 correctly call per-hook ISR “planned-unbuilt,” but that is only true
cross-runtime. On Codex, opportunity/terminal status and latency should come from native metrics;
building a second timer/logger would create double accounting.

**Exact borrow line**

`For Codex hook opportunity, terminal status, and latency, consume native codex.hooks.run and codex.hooks.run.duration_ms; join their bounded labels to the event-ledger hook_id, and build only acted_on, true_positive, and miss-rate enrichment.`

**Maturity audit**

- Maintenance: OpenAI Codex is actively maintained, Apache-2.0, with extensive source tests and docs.
- License: Apache-2.0.
- Tests/examples: source test suite plus official `hooks.json`, inline TOML, Windows command, and OTel examples.
- Maturity: Codex remains **pre-1.0**; hooks/related history features are feature-flagged and moving.

**Preflight:** confirm the installed Codex version emits metrics for the actual entry point in use;
do not infer CLI behavior for `codex exec` or `codex mcp-server`.  
**Confidence:** HIGH on official capability; MEDIUM until the local entry point is measured.

---

## F9 — Borrow RHO’s coreset selection, reject its truth source

**Sources**

- Paper: <https://arxiv.org/abs/2606.05922>
- Repository: <https://github.com/wbopan/retro-harness>

**Evidence and concrete delta**

RHO selects a small coreset of difficult, diverse historical tasks with a DPP, re-solves them in
parallel, and proposes harness changes. Its public v0.1.0 package includes hermetic and real-agent
tests, Codex and Claude workflow examples, and reports substantial held-out gains.

The selection mechanism is useful; the acceptance mechanism conflicts with this estate’s
load-bearing self-calibration law. RHO promotes via the same agent’s pairwise self-preference
without external grading. Here, self-preference may rank candidates but cannot certify them.
HarnessLens’s attributable external gate must remain final.

**Exact borrow line**

`Choose the offline failure corpus by difficulty × diversity (DPP/greedy-MAP), but treat self-validation, self-consistency, and pairwise self-preference as proposal signals only; promotion still requires frozen external held-out checks and disk-verified artifacts.`

**Maturity audit**

- Maintenance: last code push 12.06.2026; repository metadata active 28.08, but no recent code push.
- License: MIT.
- Tests: hermetic pytest suite plus opt-in Codex and benchmark integrations.
- Examples: Claude dynamic workflow, stdlib Codex script, configs, CLI, and web run browser.
- Maturity: package **0.1.0 / pre-1.0**.

**Risk:** its default Claude cycle uses roughly 40 agents, directly conflicting with this box’s RAM
constraint and one-cursor-agent rule. Borrow the selector, not the fan-out implementation.  
**Confidence:** MEDIUM-HIGH.

---

## F10 — Per-agent cache TTL is now native, but may be irrelevant on this subscription

**Sources**

- Claude Code changelog: <https://docs.anthropic.com/en/release-notes/claude-code>
- Subagent configuration: <https://docs.anthropic.com/en/docs/claude-code/sub-agents>

**Evidence and concrete delta**

Claude Code v2.1.248+ accepts `experimental.cacheTtl: 5m|1h` in subagent frontmatter and separate
main/subagent TTL settings. Official docs say `1h` is ignored while a Claude subscription uses
usage credits. This is a native refinement of the already-adopted KV-cache hygiene audit, not a new
cache layer.

**Exact borrow line**

`Set experimental.cacheTtl: 1h only on repeated, stable-prefix audit/research agents whose measured cache reuse exceeds the higher write cost; leave high-churn and one-shot agents at 5m, and make no change when subscription usage credits cause 1h to be ignored.`

**Maturity audit**

- Maintenance: official current Claude Code docs/changelog.
- License: vendor feature; no standalone reusable package license.
- Tests: vendor tests are not independently inspectable.
- Examples: official frontmatter example and explicit applicability limits.
- Maturity: **experimental/RFC-like field**, requires v2.1.248+.

**Decision:** conditional native trial only after checking local version, billing mode, and cache-hit
telemetry.  
**Confidence:** HIGH on feature semantics; LOW-MEDIUM on value for this estate.

---

## Cross-finding synthesis

### Recommended build shape

The findings compose into one bounded reliability loop, not nine products:

1. **Before compaction:** extract explicit session constraints into `SC_PIN`.
2. **At compaction:** run TRACE-style paired boundary tests on a small fixture suite.
3. **During execution:** retain full evidence locally, emit structured who/when attribution.
4. **During fault drills:** inject typed faults and measure cascade radius, not only terminal pass.
5. **During memory eval:** test gotchas and premise awareness with an opaque-query boundary.
6. **During improvement:** choose diverse historical failures, propose candidates, then apply the
   HarnessLens attributable-evidence gate.
7. **During analysis:** label failed layer, enforcement point, and repair owner.
8. **On Codex:** source basic hook opportunity/latency facts from native metrics.

### Cross-lens convergence

- F1/F3 independently strengthen Lens 09’s compaction/poison/supersession work: preserve constraints
  separately, then test the exact boundary.
- F4/F6/F7 strengthen Lens 11’s schema: add layer ownership, cascade radius, and decisive-step attribution.
- F8 materially reduces Lens 11’s ISR build scope on Codex.
- F6 corroborates Lens 12’s finding that alarms without attribution/reader ownership are not a
  functioning reliability system.
- F5 aligns with Lens 09’s premise/retraction focus and keeps basic-memory as the sole writer.
- F2 + F9 reconcile self-improvement: diversity-aware proposal generation, externally grounded promotion.

## Registry, vendor, and benchmark near-misses

| Candidate | Evidence checked | Verdict |
|---|---|---|
| OpenAI Agents SDK sandbox memory v0.14 | Official changelog, docs, repository; beta, Apache-2.0, many tests/examples | **NO ADOPT.** It is a second writable memory plane, violating G-81. Progressive disclosure is already present conceptually; no net-new borrow worth the conflict. |
| OpenAI Trace Evals / Prompt Optimization | Official August 2026 API changelog | **NO BUILD.** Cloud eval/optimization duplicates the local evidence and variant gates; can be used only inside a future OpenAI API project with an explicit data-egress decision. |
| `Harness the Memory` (arXiv:2608.15008) | Paper and project search | **WATCH.** Useful finding—retrieval breadth helps QA and can harm sequential control—but code is promised only upon acceptance, so maintenance/license/tests/examples cannot yet pass. |
| Princeton reliability profile / HAL | ICML paper and `princeton-pli/hal-harness` | **BORROWED BY LENS 11 ALREADY.** Twelve-metric reliability profile is relevant, but the public harness is archived. No duplicate framework. |
| AgentEval DAG root-cause framework | Paper and repository search | **WATCH.** Strong reported DAG attribution, but the surfaced GitHub repository identity collides with an unrelated skill-benchmark project; provenance is insufficient for adoption. |
| Self-Harness | Paper, GitHub, PyPI search | **NO ADOPT.** Official-looking repo has no license and no test tree; method is subsumed by F2/F9 with a stronger external gate. |
| TTHE | Paper/repo; MIT, examples, no visible test tree | **SKIP live adaptation.** Test-time unlabeled harness mutation is too close to live self-modification and uses proxy judges; conflicts with frozen held-out gates. |
| MOSS | Paper/repo; Apache-2.0, container examples, no root test tree | **SKIP runtime.** Adds a host daemon, trial workers, in-place container swap, and second evolution runtime. Its health-gated rollback is already represented in existing variant/rollback doctrine. |
| MAS-FIRE | Paper, GitHub, Zenodo | **EVIDENCE ONLY.** Useful taxonomy, but repository is data-heavy, unlicensed, and lacks tests; F6 borrows the measurable delta through existing tracers. |
| MemHarness / AMA-Bench | Papers/repos | **NO NEW STORE.** AMA-Bench is MIT and maintained, but LongMemEval-V2 better matches environment gotchas/premise awareness. MemHarness requires training and a new memory architecture. |
| PyPI `rubra` 0.1.1, `treval` 0.2.3, `agent-xray` beta, `agentprobe-framework` 1.1.0, MLflow 3.15 | Registry pages, licenses, examples | **SKIP.** Each creates another trace/eval/observability plane. Lens 11’s ledger and AgentsView decision already own this surface. Rubra is also two-day-old pre-1.0; MLflow is far too heavy. |
| npm MemoryLens, `@khoralabs/memories-otel`, agent-memory packages | Registry pages | **SKIP.** New dashboard/collector/memory services and, in several cases, another semantic store. Native Codex metrics in F8 are the only telemetry adoption with positive incremental value. |
| Claude Managed Agents memory stores | Official API release notes | **NO ADOPT.** Public beta but a second cloud memory writer/sync plane. It conflicts with local-only basic-memory ownership. |
| Codex paginated history/memories | Official changelog/app-server docs | **WATCH.** Experimental app-server documentation still contains fail-closed unsupported paths for paginated creation/full-history resume. Do not turn it on as a reliability fix yet. |

## Final recommendation

**Top build bundle:** F1 + F2 + F4 + F8. It closes constraint loss, makes harness promotion
attributable, routes fixes to the correct layer, and avoids rebuilding telemetry Codex already
emits.

**Second bounded evaluation bundle:** F3 + F5 + F6 + F7, each as a small fixture/protocol adapter,
not an imported platform.

**Borrow only:** F9’s difficulty-diversity selector.  
**Conditional native trial:** F10.  
**No new daemon, memory store, vector/KG layer, orchestrator, observability SaaS, or live self-modifier.**

## Search and evidence limits

- GitHub API suffered intermittent TLS timeouts. Load-bearing repository facts were corroborated
  through raw files, API metadata, paper links, or official project pages; unresolved fields are
  marked rather than inferred.
- `bd prime --work-type ...` was incompatible with the installed CLI. A read-only `bd prime --full`
  completed successfully but returned no project knowledge, so the named disk documents were the
  effective knowledge ground.
- “Maintenance” uses `pushed_at` where available, not GitHub’s looser `updated_at`, which can change
  from non-code activity.
- Paper effect sizes are workload-specific. Recommendations borrow mechanisms and local tests, not
  universal numerical claims.
- This lens is exhaustive across the specified source lanes to the cutoff, not a claim that every
  repository or paper on the public internet was indexed.

UNIT-COMPLETE: lens-02
