# Lens 15 — Wildcard / gold-gem hunt

**Date:** 29.08.2026  
**Scope:** mechanisms borrowed from operating systems, distributed systems, runtime garbage
collection, medication safety, Unicode security, and oracle-free software testing.  
**Decision:** five candidates survive dedup. The strongest is an adaptive phi-accrual stall
detector. All five fold into existing buses; none needs a resident service, second orchestrator,
new memory store, or new MCP.

## 1. Ground and dedup

Read in full before searching:

- `C:\Users\Prekzursil\AGENTS.md`
- `.agents/CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`, including its recovery addendum
- `docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md`
- `docs/agentic-perfection/OPEN-THREADS.md`
- the only sibling lens present during this run, `11-metrics-evals.md`

Targeted literal searches found none of the five mechanisms below in those decision/plan/lens
documents. Conceptual dedup was stricter than literal dedup:

- **Built:** shared dispatch seams, event ledger, background registry, long-run heartbeat,
  agent-mail, claim guard, typed receipts, artifact re-read, Cursor lifecycle logs, basic-memory
  supervision, project-key fields, and the static `<8 GB` worker ban.
- **Planned/unbuilt:** fixed-time parallel-barrier watchdog, cgroup-style fleet governor/OOM
  killer, resource guard, subagent apoptosis and fencing, project identity resolver, typed
  episode eviction, eviction landmarks, verified resume, and per-hook ISR telemetry.
- **Explicitly excluded:** MEL, Andon, quiescence, TMS, Smith predictor, alarm stewardship,
  provenance, Discipline-Forge, tracer rounds, PACE/circuit-breaker fallback chains, memory decay,
  and ordinary retry/two-strikes doctrine.
- **Sibling-lens exclusion:** lens 11 already specifies denominators, lifecycle events,
  failure-to-rescue, false-green, latency, and identity joinability. Findings below may emit those
  events but do not repackage the metrics.

## 2. Ranked findings

| Rank | Mechanism | Primary pain | Bus | Maturity | Value × effort | Confidence |
|---|---|---|---|---|---|---|
| 1 | Phi-accrual suspicion | false stall/cancel decisions | agent-mail + lifecycle/heartbeat ledger | production-proven | very high × medium | **0.91** |
| 2 | Banker's safe-state admission | RAM-pressure cancellations | consolidated launch dispatcher | canonical OS method; estate transfer experimental | very high × low-medium | **0.74** |
| 3 | Metamorphic MCP contracts | fragile tools with weak oracles | existing MCP runtime test/liveness path | established testing method | high × low-medium | **0.86** |
| 4 | Generational context tenure | session-history waste/prompt drift | precompact + event ledger | production-proven runtime mechanism; transfer experimental | high × medium | **0.69** |
| 5 | Tall-Man identity labels + confusable rejection | project/agent identity mixing | agent-mail identity/display templates | deployed safety practice; outcome evidence mixed | medium-high × low | **0.61** |

## 3. GOLD — phi-accrual stall suspicion

### Borrow line

Borrow **only** the accrual-failure-detector calculation: retain a bounded history of each
agent's heartbeat/status inter-arrival times and compute
`phi = -log10(P(next heartbeat arrives later than the current delay))`. Emit a continuous
`stall_suspicion` value. Do not borrow Akka, Cassandra, a cluster runtime, or a new daemon.

This is not the planned fixed `quiet > 25 min` watchdog. A fixed timeout interprets a 90-second
pause the same way on an idle and a RAM-thrashing machine. Phi learns the observed delay
distribution per execution surface and separates **observation** from **policy**. It directly fits
the estate's transcript-flush lag and agents that look canceled while artifacts are still landing.

### Estate fit

- Input: existing timestamped long-run heartbeats, `[STATUS]` agent-mail messages, and
  Cursor/Claude subagent lifecycle events.
- Output: one additive ledger field/event: `stall_suspicion_phi`, sample count, and last-heartbeat
  age.
- Policy: shadow-only first. A high phi requests the already-required independent process/artifact
  probe; it never cancels an agent by itself.
- Cold start: retain the current conservative fixed grace window until enough samples exist.
- Cost: bounded arithmetic at lifecycle/status events; no polling service and no new hook family.

### Test and kill criterion

Replay historical lifecycle traces and inject three labeled cases: clean completion, RAM/GC pause,
and hard process death. Then shadow for at least **500 heartbeat opportunities over 14 days**.

Promote only if it detects true hard stalls at least **20% earlier** than the fixed watchdog at an
equal or lower false-stop rate. **Kill/revert** if verified-live agents cross the action threshold
in more than **0.5%** of opportunities, if median detection lead is under **10%**, or if p95 event
cost exceeds **10 ms**. Keep phi as telemetry if useful; never auto-stop without the second probe.

### Sources and maturity

- Hayashibara et al., *The Phi Accrual Failure Detector* (2004): continuous suspicion derived from
  sampled heartbeat arrival distributions; evaluated on nearly six million heartbeats.  
  https://dspace.jaist.ac.jp/dspace/bitstream/10119/4784/1/IS-RR-2004-010.pdf
- Akka current documentation: Remote DeathWatch uses phi accrual and exposes the
  sensitivity/false-positive trade-off.  
  https://doc.akka.io/libraries/akka-core/current/typed/failure-detector.html
- Akka production implementation, including minimum deviation, acceptable pause, and cold-start
  estimate.  
  https://github.com/akka/akka/blob/master/akka-remote/src/main/scala/akka/remote/PhiAccrualFailureDetector.scala

**Maturity:** production-proven in distributed runtimes; this local-agent application is novel but
mechanically close. **REC: TRIAL first, then ADOPT if the shadow gate passes.**

## 4. Banker's safe-state launch admission

### Borrow line

Borrow Dijkstra's single rule: **grant a resource request only if the hypothetical post-grant
state still has at least one ordering in which every admitted customer can finish and return its
resources**.

Translate `customer/current loan/maximum claim/cash` to
`agent/current RSS/declared peak working set/free commit`. Before a local fan-out or heavy tool
launch, simulate the safety sequence. An unsafe request is queued or sent through the already
approved cloud/offload lane; capability is not removed.

This is not the proposed cgroup/OOM killer: it prevents unsafe admission before pressure rather
than killing a victim afterward. It is also not the static `<8 GB` rule: two 2 GB lanes and one
bursty 10 GB lane can have different safe states at the same free-RAM reading.

### Estate fit

- Fold the check into the existing consolidated Task/subagent launch branch; no new hook process.
- Seed each `max_claim_mb` from measured p99 peak working set plus a margin, stratified by runtime
  and work type. Unknown claims take the conservative lane.
- Record `safe_sequence`, claim source, wait duration, and actual peak in the existing event
  ledger so estimates self-correct without a new store.
- Preserve an explicit owner bypass for latency-critical work; log it rather than silently
  degrading the requested capability.

### Test and kill criterion

Offline-replay at least **30 real launches** against their measured peak RSS, then run controlled
2/3/4-lane pressure scenarios. Compare with the static free-RAM threshold.

Adopt only if RAM-caused cancellation/OS-thrash episodes fall by **50% or more** with no false-safe
allocation and p95 queue delay below **5 minutes**. **Kill** if peak claims underpredict actual RSS
by more than **20%** in over **10%** of launches, if head-of-line blocking appears in two trials,
or if no safe sequence can be computed because work has no bounded claim. In that case retain the
static gate and measured cloud routing.

### Sources and maturity

- Dijkstra, EWD108, original Banker's Algorithm: inspect the hypothetical allocation and grant
  only if all customers can still be ordered to finish.  
  https://www.cs.utexas.edu/~EWD/transcriptions/EWD01xx/EWD108.html
- Dijkstra, EWD623, formal definition and mathematics of a safe resource-allocation pattern.  
  https://www.cs.utexas.edu/~EWD/transcriptions/EWD06xx/EWD623.html

**Maturity:** canonical deadlock-avoidance theory since the 1960s. Direct OS deployment is limited
because maximum claims are often unknown; that is exactly why claim calibration is the kill gate,
not an assumption. **REC: TRIAL.**

## 5. Metamorphic contracts for fragile MCP/tool paths

### Borrow line

Borrow metamorphic testing's oracle workaround: where one output is difficult to certify, define
a necessary relation between outputs of two semantically related inputs. A relation violation is
evidence of tool-path fragility even when neither answer has a known golden value.

Start with read-only, deterministic relations:

1. equivalent Windows path spellings resolve to the same canonical resource;
2. a filtered result is a subset of the unfiltered result on the same frozen snapshot;
3. concatenated non-overlapping pages equal the corresponding unpaginated stable set;
4. ordering-only changes to commutative query parameters preserve the normalized result.

This is not a tracer round: no planted forbidden payload or expected single output is required.
It is not PACE fallback: it evaluates the current tool rather than switching tools after failure.

### Estate fit

- Add relation pairs to the existing `agents mcp test --runtime`/mcp-liveness test path.
- Keep each relation next to the server's registry test metadata; do not create another MCP.
- Run after sync and on a sampled schedule, not on every user tool call.
- Emit ordinary tool-attempt/result events so lens 11's terminal coverage and failure-to-rescue
  metrics apply unchanged.

### Test and kill criterion

Seed historical path, pagination, normalization, stale-session, and empty-envelope regressions.
Each relation must detect at least **80%** of the seeded faults. Shadow against **500 stable
executions**.

**Kill an individual relation** if its false-alarm rate exceeds **1%**, the upstream API does not
promise the relation, or snapshot drift makes it non-reproducible. Keep the mechanism only if at
least three relations catch a real or seeded defect at under **2×** the runtime of existing smoke
tests.

### Sources and maturity

- Segura et al., IEEE TSE survey: metamorphic testing checks relations across transformed inputs
  when a concrete test oracle is unavailable; surveys applications from web services to graphics.  
  https://doi.org/10.1109/TSE.2016.2532875
- Liu et al., IEEE TSE empirical study: small, diverse metamorphic-relation sets can materially
  alleviate the oracle problem.  
  https://doi.org/10.1109/TSE.2013.46
- Chen et al., 2024 state-of-the-art review: reports real bug detection in compilers, search,
  scientific simulation, ML, and autonomous-driving systems.  
  https://arxiv.org/html/2406.05397

**Maturity:** established research and industrial testing technique; relation quality remains the
main risk. **REC: ADOPT as a narrow trial on the three most fragile read-only MCP paths.**

## 6. Generational context tenure

### Borrow line

Borrow the JVM's **weak generational hypothesis** and tenure rule, not a GC implementation:
assume most newly introduced context dies young; collect it cheaply and frequently, and promote
only items that survive observed reuse.

Use three logical generations:

- **Eden:** current-turn observations and tool output; eligible for immediate compaction.
- **Survivor:** an item referenced by the next work unit or unresolved thread.
- **Tenured card:** promote only after two independent retained uses, or an explicit durable
  decision/fact. The card remains terse and points to the source ledger event.

Maintain a small remembered set for tenured cards that depend on unresolved young evidence.
This is distinct from planned typed eviction: type decides *how* an item is represented; observed
survival/reuse decides *whether* it earns scarce injected context. It is also distinct from
time-decay: an old item can stay tenured while a new unused item dies immediately.

### Estate fit

- Fold classification into the existing precompact/event-ledger path.
- Basic-memory remains the sole semantic writer; only hook-approved tenured facts/decisions use
  its existing write path.
- The event ledger remains authoritative for evicted detail. No vector DB, graph store, or second
  transcript archive.
- Do not alter prompt prefix order; append the small survivor/tenured view to preserve cache
  hygiene.

### Test and kill criterion

Replay **20 long sessions** with held-out questions about constraints, corrections, open work, and
decisions. Blind-compare answers from the current summary path and generational tenure.

Adopt only if injected history tokens fall by **30% or more** while held-out factual accuracy is
non-inferior within **2 percentage points** and every load-bearing correction remains recoverable.
**Kill** on one unrecoverable binding constraint/correction, p95 compaction cost above **500 ms**,
or token reduction below **15%**. Never delete source ledger events.

### Sources and maturity

- Oracle HotSpot GC guide: generational collection exploits the empirical observation that most
  objects survive briefly and promotes survivors to older generations.  
  https://docs.oracle.com/en/java/javase/25/gctuning/garbage-collector-implementation.html
- Oracle's earlier generations guide, independently documenting young collection and survivor
  promotion.  
  https://docs.oracle.com/javase/8/docs/technotes/guides/vm/gctuning/generations.html
- Datadog's JVM GC review describes remembered sets for old-to-young references, the exact
  dependency edge needed here.  
  https://www.datadoghq.com/blog/understanding-java-gc/

**Maturity:** generational GC is production-standard; applying survival-based tenure to prompt
context is experimental. **REC: TRIAL after eviction-landmark work, not before.**

## 7. Tall-Man agent identities with confusable rejection

### Borrow line

Borrow medication safety's Tall Man rule: for two look-alike labels, visually emphasize the
minimal differing substring. Pair it with Unicode UTS #39's confusable-skeleton test at identity
creation. Do not borrow a medical terminology system.

Example display labels:

- `QZP·RESearch·7K2`
- `DEMOS·RESearch·9F4`

The project token and short checksum are mandatory in every lifecycle and `[IMPORTANT]` header;
role-only names such as `researcher-agent` are never sufficient. If two active labels have the
same UTS #39 skeleton or exceed the chosen similarity threshold, `create_agent_identity` proposes
a more distinct display label. Routing still uses the immutable internal ID.

This complements rather than duplicates the project-identity resolver: the resolver decides which
project an event belongs to; Tall-Man display and confusable rejection stop humans and agents from
mistaking two correctly resolved identities for one another.

### Estate fit

- Implement as formatting/validation in existing agent-mail identity creation, `rename_window`,
  message headers, and handoff templates.
- No new identity database; internal IDs/project hashes already exist.
- Never rely on color alone. Preserve the original machine ID in payload metadata.

### Test and kill criterion

Construct a blinded forced-choice set from active project/role pairs plus Unicode confusables.
Measure message-to-agent/project attribution with current labels versus differentiated labels,
then shadow real handoffs for 30 days.

Adopt only if laboratory misattribution falls by **50% or more** and real routing mismatches remain
zero. **Kill/revise the typography** if attribution improves by under **20%**, label truncation
removes the distinguishing segment, or user-rated scan effort worsens by over **10%**. The mixed
clinical evidence makes this a measured UI trial, not a safety claim.

### Sources and maturity

- FDA Name Differentiation Project: defines Tall Man lettering and has evaluated look-alike name
  pairs since 2001.  
  https://www.fda.gov/drugs/medication-errors-related-cder-regulated-drug-products/fda-name-differentiation-project
- Systematic review of look-alike/sound-alike interventions: evidence for Tall Man lettering is
  limited/mixed, so it should not stand alone.  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC9328434/
- Unicode Technical Standard #39: specifies skeleton-based detection of visually confusable
  identifiers and warns that the skeleton is internal, not a display normalization.  
  https://unicode.org/reports/tr39/

**Maturity:** long-deployed regulatory/clinical convention plus a mature identifier-security
standard, but mixed outcome evidence for typography alone. **REC: TRIAL, paired with immutable
internal IDs.**

## 8. Rejected near-misses

- **Proof-carrying completion / in-toto manifests:** useful, but it is provenance and typed-receipt
  work already selected.
- **E-values for optional stopping:** mathematically attractive for repeated noisy checks, but most
  estate completion gates are deterministic and do not yet have a defensible stochastic null.
  Premature here.
- **Erlang supervision trees, circuit breakers, bulkheads, and N-version fallbacks:** already
  absorbed by lifecycle rescue, PACE, MEL, cloud offload, and existing supervision.
- **Working-set OOM victim selection:** duplicates the planned fleet governor/apoptosis. Banker's
  pre-admission safety test is the non-duplicate part.
- **Content-addressed transcript snapshots:** duplicates ledger/provenance/eviction-landmark work.

## 9. Recommended order

1. Shadow phi accrual using existing heartbeat/lifecycle records.
2. Offline-replay Banker's admission against measured peak RSS; do not enforce until claims
   calibrate.
3. Add three read-only metamorphic relations to the existing runtime MCP test.
4. Trial identity labels independently; their mixed evidence warrants easy rollback.
5. Sequence generational tenure after eviction landmarks because its safety test needs reliable
   source pointers.

No candidate should become a new always-on process or a standalone hook family.

UNIT-COMPLETE: lens-15
