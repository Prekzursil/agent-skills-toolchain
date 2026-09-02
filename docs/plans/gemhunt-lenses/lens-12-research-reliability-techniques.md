# Lens 12: research reliability techniques
Source: subagent bc-68ba5a88-fc1f-5081-b011-77d6864d4a5f, dispatched 2026-09-02 from cloud run bc-2a7f9bf8-4a9a-4193-a2c3-4f80d21392f9; completion notification was lost, report recovered from the transcript on 2026-09-02.
Status: raw lens report — findings, not decisions. Decisions live in ../2026-09-02-search-research-tools-gemhunt.md.

# Gem-hunt lens report: agentic deep-research reliability techniques to borrow (2025–2026)

**Scope of this lens:** iterative/tree planning, self-RAG, CRAG, ReAct loops, plan-and-solve, claim-level grounding, gap detection, test-time compute, triangulation, contradiction detection, sub-question graphs, HyDE, step-back, freshness gating, and (weighted highest) checkpointing/resumability + budget-aware early-stop.

**Dedup baseline (verified read-only against `deep-research/references/research_harness/`):** capability→provider routing (`plan_research`, `top_n=2`), query-hash cache with per-capability TTL (`query_hash`, `ttl_for(capability)`), RRF fusion, deterministic grading (`grade_source`: tier × corroboration × recency), Admiralty/WEP calibration, claim contracts + `audit_claims` (`SUPPORT_VERDICTS = {supported, partial, unsupported, unchecked}`), cited-report renderer (`Report`/`render`), preflight, top-2 cross-corroboration. Gaps that shaped the ranking: no per-run state on disk, no budget object, no terminal-state/partial status, no `contradicted` verdict, TTL keyed on capability not volatility, no dependency ordering, no loop guard.

**Ranking rule:** (reliability lift, weighted toward reducing partial-run failures) × (small diff, stdlib only). **Confidence legend:** High = peer-reviewed or production write-up, 2025 or earlier; Med = 2025 preprint with code; ⚠2026 = 2026 preprint, unreviewed unless noted.

## Ranked summary

| # | Technique | Partial-run lift | Diff size | Value×Effort | Confidence |
|---|---|---|---|---|---|
| 1 | Run ledger + resume-from-checkpoint | Direct | ~1 new module | H×L-M | High (+ ⚠2026 ACL paper) |
| 2 | Terminal-state taxonomy: partial = degraded success, always emit partial report | Direct (fixes the metric) | 1 field + 1 section | H×L | Med (⚠2026 for taxonomy) |
| 3 | Budget tracker + regime-based early stop | Direct | 1 dataclass + prompt line | H×L | High (BATS) / ⚠2026 (BAGEN) |
| 4 | Keep-latest-K raw + summarize older | Direct (context) | 1 digest function | H×L-M | Med / ⚠2026 |
| 5 | Struggle/loop guard reusing `query_hash` | Direct | ~20 lines | M-H×L | High |
| 6 | Sufficiency gate per sub-question + one bounded follow-up | Indirect | 1 function | H×L | High |
| 7 | Report-as-state (Markovian workspace reconstruction) | Direct | Refactor of `Report` use | H×M | Med |
| 8 | Sub-question DAG + effort classes | Indirect (order of loss) | 2 fields on `ResearchPlan` | M×L-M | High |
| 9 | Contradiction detection + source-aware consolidation | Indirect | new verdict + grouping | M-H×L | High |
| 10 | Behavior-aware best-of-N filter | Indirect | regex + rule | M×L | ⚠2026 |
| 11 | Active claim verification pass (CoVe-style) | Indirect | extends `audit_claims` | M×L-M | High |
| 12 | Freshness gating by question volatility | Indirect | `ttl_for` gains an axis | M×L | High |

---

## 1. Run ledger + resume-from-checkpoint

- **What:** Persist per-run progress to disk after every completed sub-question (plan, sub-question results, grades, partial report) so a killed/OOM'd/context-truncated run restarts at the last checkpoint instead of from zero. FS-Researcher externalizes all research state to a file-system workspace so "a new session can resume exactly where the previous one left off"; Anthropic's production Research system saves the plan to memory before the 200k context truncates and "built systems that can resume from where the agent was when the errors occurred… deterministic safeguards like retry logic and regular checkpoints"; ReSum resumes a fresh context from a summary of the prior trajectory.
- **Why THIS user:** Your hypothesis is that long runs die on a RAM-starved box and log as failures. A ledger converts "died at sub-question 5/8" into "resume at 6/8". It is the single highest-leverage change for the 42% number and needs zero new runtime, only `json` + `pathlib`.
- **Smallest harness change:** New `checkpoint.py` (stdlib). Key = hash of the normalized plan (sub-questions + capabilities). Append-only JSONL under the existing cache dir: `{"event":"plan"}`, `{"event":"subq_done","id":..,"sources":[..],"grades":[..]}`, `{"event":"report_partial","md":..}`, `{"event":"sealed"}`. On start: if an unsealed ledger for the plan hash exists, `plan_research` drops completed IDs and the renderer seeds from the last `report_partial`. Sub-question results already flow through `fetch_with_cache`, so most resumed calls are cache hits. Fail closed on corrupt JSONL (the apache/maka reproduction of FS-Researcher documents exactly this contract).
- **Sources:** FS-Researcher, arXiv:2602.01566 (ACL 2026) https://arxiv.org/abs/2602.01566 · Anthropic, "How we built our multi-agent research system" (Jun 2025) https://www.anthropic.com/engineering/multi-agent-research-system · ReSum, arXiv:2509.13313 https://arxiv.org/abs/2509.13313 · minimal contract reproduction: https://github.com/apache/maka/blob/main/docs/deep-research-durable-workspace.md
- **Value×Effort:** H × L-M. **Novelty:** Medium (mainstream in 2025–26 production agents, absent here). **Confidence:** High for the practice (Anthropic production); FS-Researcher is ⚠2026 but ACL-accepted.
- **Dedup:** The query cache is per-query and TTL'd; a ledger is per-run and ordered. Distinct.

## 2. Terminal-state taxonomy: partial = degraded success, always emit a partial report

- **What:** Classify how a run ended (confident / uncertain / give-up / no-answer / budget-stop / context-stop) and always render whatever evidence exists, with an explicit "Unanswered sub-questions" section. The Context Rot paper shows agents "give up or provide uncertain incorrect answers long before exhausting the context window" and defines a premature-termination rate = give-up + uncertain-incorrect; Deep Research Bench's failure taxonomy (hallucination, repeated tool calls, forgets information) is built from traces, not just final scores.
- **Why THIS user:** Your 42% is measured as binary. If a partial run currently logs as failure, you cannot tell "wrong answer" from "ran out of box". Making the harness emit a status makes the hypothesis testable in the next 20 uses and immediately raises perceived reliability (a partial cited report beats a crash).
- **Smallest harness change:** Add `status: str` and `open_subquestions: tuple[str, ...]` to `Report`; `render` writes a `## Status` line and a `## Unanswered sub-questions` section when non-empty. Harness sets `status` from the budget object (find 3) or ledger (find 1). The skill's instrumentation counts `partial:*` separately from `failed`.
- **Sources:** Diagnosing and Mitigating Context Rot in Long-horizon Search, arXiv:2606.29718 https://arxiv.org/abs/2606.29718 (code: https://github.com/GAIR-NLP/ContextRot) · Deep Research Bench, arXiv:2506.06287 https://arxiv.org/abs/2506.06287
- **Value×Effort:** H × L. **Novelty:** Medium. **Confidence:** ⚠2026 preprint for the taxonomy numbers; the practice itself is low-risk and independently supported by Deep Research Bench (2025).
- **Dedup:** Renderer exists; it has no notion of incompleteness. New.

## 3. Budget tracker + regime-based early stop

- **What:** Give the loop an explicit, continuously updated budget (tool calls, estimated tokens, wall clock) and a regime (explore → converge → finalize) that changes behavior. Google/UCSB's Budget Tracker is "a lightweight plug-in that provides the agent with continuous budget awareness" and alone improves scaling; BATS adds dig-deeper-vs-pivot decisions; s1's budget forcing shows hard caps on thinking preserve most accuracy; BAGEN reports a simple early-stop policy saves 28–64% of tokens on failing trajectories at a 1.6–4.2pp success cost; Anthropic hard-codes effort rules (simple: 1 agent, 3–10 calls; comparisons: 2–4 subagents, 10–15 calls each).
- **Why THIS user:** On a memory-starved box the budget is the box. A run that knows it has 4 calls left should stop searching and render, rather than start sub-question 7 and die mid-fetch. Combined with find 2 this converts crashes into on-time partial deliveries.
- **Smallest harness change:** `budget.py`: `@dataclass Budget(max_calls, max_seconds, used_calls=0, started=...)` with `.regime()` returning `explore` (<60%), `converge` (60–85%), `finalize` (>85%). `plan_research` assigns per-sub-question call allotments from the existing complexity/high-stakes flags. Each loop iteration prepends one line: `Budget: 11/20 calls, 6 min left, regime=converge`. Rule: `finalize` → no new searches, render with status `partial:budget`.
- **Sources:** Budget-Aware Tool-Use for Agent Scaling (Budget Tracker / BATS), arXiv:2511.17006 https://arxiv.org/abs/2511.17006 · s1: Simple test-time scaling, arXiv:2501.19393 https://arxiv.org/abs/2501.19393 · BAGEN, arXiv:2606.00198 https://arxiv.org/abs/2606.00198 · Anthropic scaling rules (link above)
- **Value×Effort:** H × L. **Novelty:** Medium-High (budget awareness as a first-class signal is a late-2025 idea). **Confidence:** High for Budget Tracker/BATS and s1; ⚠2026 for BAGEN and BAVT (arXiv:2603.12634).
- **Dedup:** Preflight checks providers, not budget. New.

## 4. Keep-latest-K raw tool responses, summarize older (length-triggered compaction)

- **What:** Once working context passes a length threshold, keep the last K tool outputs verbatim and replace older ones with a compact digest. Among seven context-management variants benchmarked (compaction by length/turns/semantics, discard-all, keep-latest, keep-latest+summary, sub-agent isolation), keep-latest-with-summary gave the best average for one flagship model, and all variants cut premature termination; ReSum resumes reasoning from a structured summary when context nears the limit (+4.5–8.2%); Kimi-Researcher reports a naive agent exceeds context "within 10 iterations" while context management extends rollouts past 50; AgentFold frames the same idea as multi-scale folding.
- **Why THIS user:** Raw search/fetch payloads are what blow the context (and RAM) on long runs. The harness already caches the raw payload; the working context only needs the graded digest.
- **Smallest harness change:** `compact.py`: `digest(sources: list[Source], grades) -> str` producing ≤N lines per sub-question (URL, tier, grade, one evidence sentence). Loop rule in SKILL.md: keep the last 3 tool outputs raw; everything older is replaced by its digest (raw stays in cache for re-read). Threshold ~32k tokens, matching the paper's setting for open-web benchmarks.
- **Sources:** Context Rot paper (above, §4.1, Table 3) · ReSum arXiv:2509.13313 · AgentFold arXiv:2510.24699 https://arxiv.org/abs/2510.24699 · Kimi-Researcher, https://moonshotai.github.io/Kimi-Researcher/ (Context management section)
- **Value×Effort:** H × L-M. **Novelty:** Medium-High. **Confidence:** Med (ReSum, Kimi are 2025 with results); the seven-way ranking is ⚠2026.
- **Dedup:** No compaction exists. New.

## 5. Struggle / loop guard reusing `query_hash`

- **What:** Detect no-progress loops deterministically. Context Rot defines a struggle score (share of steps with repeated failed attempts / no progress) and shows give-ups concentrate at high struggle; Deep Research Bench finds "repeated tool calls" and "forgets information" are dominant action failures and that thinking models "get stuck repeatedly calling the same tools without adapting to failures".
- **Why THIS user:** Repeated near-identical queries burn the exact budget a RAM-starved box lacks, and they are the most machine-detectable failure mode you have. `normalize_query` + `query_hash` already exist.
- **Smallest harness change:** Per-run `seen: set[str]` of `query_hash(...)`; before a fetch, if the hash is seen or token-Jaccard ≥0.8 with a seen query → refuse and force either a reformulation (find 6) or "mark open, move on". After two consecutive rounds with zero new unique URLs for a sub-question → mark it open. ~20 lines.
- **Sources:** Deep Research Bench arXiv:2506.06287 (Table 4/6) · Context Rot arXiv:2606.29718 (§3, App. B.2)
- **Value×Effort:** M-H × L. **Novelty:** Medium. **Confidence:** High (DRB 2025); struggle-score framing ⚠2026.
- **Dedup:** Cache dedups identical fetches but happily returns the same cached result to a looping agent; this blocks the loop itself. New.

## 6. Sufficiency gate per sub-question + one bounded follow-up query

- **What:** After fusion, judge whether the retrieved set is sufficient before writing. CRAG scores retrieval as correct / ambiguous / incorrect and triggers refine-or-web-search; Google's Sufficient Context work shows models with RAG "hallucinate more than abstain" when context is insufficient and that a selective-generation gate using sufficiency + confidence improves correct-answer fraction by 2–10%; Search-o1 refines retrieved documents against the current reasoning step before injecting them.
- **Why THIS user:** Your grading is per source; nothing says "this sub-question has enough". A deterministic aggregate gate turns "write anyway" into "one targeted follow-up, else declare open", which is both a quality lift and a budget cap.
- **Smallest harness change:** `sufficiency(sources, grades) -> "sufficient"|"partial"|"insufficient"` from existing signals (≥2 sources graded ≥B with corroboration ≥1 and recency OK → sufficient; 1 → partial; 0 → insufficient). `insufficient` → exactly one reformulated query (inject the missing entity/date from the sub-question), then mark open. Optional one-line LLM judgment for `partial`.
- **Sources:** CRAG arXiv:2401.15884 https://arxiv.org/abs/2401.15884 · Sufficient Context arXiv:2411.06037 https://arxiv.org/abs/2411.06037 · Search-o1 arXiv:2501.05366 https://arxiv.org/abs/2501.05366
- **Value×Effort:** H × L. **Novelty:** Medium (2024–25, well replicated). **Confidence:** High.
- **Dedup:** Grading is per source; sufficiency is per sub-question. New. Self-RAG's ISREL/ISSUP tokens are the same idea but need a fine-tuned model — borrow only the rubric.

## 7. Report-as-state (Markovian workspace reconstruction)

- **What:** Make the evolving report the agent's state instead of the transcript. WebResearcher's IterResearch reconstructs the workspace each round from (question, evolving report, latest tool output) and discards the rest, avoiding the "cognitive suffocation" of mono-contextual accumulation; TTD-DR similarly keeps a draft that guides subsequent searches.
- **Why THIS user:** This is the structural version of finds 1 and 4: if `Report` is the state and is written to disk each round, checkpointing and compaction fall out for free and the context footprint stays bounded regardless of run length.
- **Smallest harness change:** Treat `Report` as the single mutable object: each sub-question round receives `render(report_so_far)` + this round's fused sources only; after the round, append `Theme`/`Claim`/`Citation` entries and persist. No new types; it changes call order in the loop, not the data model.
- **Sources:** WebResearcher arXiv:2509.13309 https://arxiv.org/abs/2509.13309 · TTD-DR arXiv:2507.16075 https://arxiv.org/abs/2507.16075
- **Value×Effort:** H × M. **Novelty:** High (Sept 2025 paradigm). **Confidence:** Med (Tongyi DeepResearch, open code; Google Cloud for TTD-DR).
- **Dedup:** Renderer exists but is terminal; making it incremental is the change.

## 8. Sub-question DAG + effort classes

- **What:** Order sub-questions by dependency and assign an effort class per node. MindSearch's WebPlanner builds a DAG of sub-questions and executes nodes as their dependencies resolve; Anthropic embeds explicit effort-scaling rules because "agents struggle to judge appropriate effort".
- **Why THIS user:** When a run is cut short, a dependency-ordered plan guarantees the prerequisites are the parts that finished, so the partial report (find 2) is coherent rather than random. Effort classes feed the budget allotments in find 3.
- **Smallest harness change:** `RoutingDecision` gains `depends_on: tuple[int, ...]` and `effort: Literal["fact","compare","deep"]` → default allotments 3 / 8 / 15 calls; `plan_research` returns decisions in topological order (stdlib `graphlib.TopologicalSorter`).
- **Sources:** MindSearch arXiv:2407.20183 https://arxiv.org/abs/2407.20183 · Anthropic scaling rules (above)
- **Value×Effort:** M × L-M. **Novelty:** Medium. **Confidence:** High.
- **Dedup:** Routing picks providers per sub-question; it neither orders nor budgets them. New.

## 9. Contradiction detection + source-aware consolidation

- **What:** Detect when sources disagree, then resolve by reliability rather than majority. Astute RAG consolidates evidence source-aware, isolates conflicting groups, and finalizes on reliability; MADAM-RAG aggregates per-document judgments to handle ambiguity, misinformation, and noise (RAMDocs). Kimi-Researcher's reported emergent behavior is exactly this: reconciling six vs four sentences by preferring primary text over translations.
- **Why THIS user:** Cross-corroboration counts agreement; nothing counts disagreement, and `SUPPORT_VERDICTS` has no `contradicted`. A disputed number silently becomes "supported" if two low-tier sources agree.
- **Smallest harness change:** Add `"contradicted"` to `SUPPORT_VERDICTS`. `conflicts.py`: group `EvidenceSpan`s per claim by normalized value (numbers/dates/entities); ≥2 distinct values → verdict `contradicted`, winner by tier × recency (reuse `grade_source`), renderer emits a "Disputed" callout listing each value with its tier.
- **Sources:** Astute RAG arXiv:2410.07176 https://arxiv.org/abs/2410.07176 · MADAM-RAG arXiv:2504.13079 https://arxiv.org/abs/2504.13079 · Kimi-Researcher (above)
- **Value×Effort:** M-H × L. **Novelty:** Medium. **Confidence:** High.
- **Dedup:** Extends the existing corroboration path with the missing negative case.

## 10. Behavior-aware best-of-N filter

- **What:** When you have multiple candidate answers for a sub-question (you already do for high-stakes ones via top-2 providers), drop hedged/give-up candidates before aggregating. Context Rot shows give-up/uncertain terminations are highly correlated with wrong answers and that filtering them before min-length / fewest-turns / majority aggregation adds 2.6–4.9% on average, most on BrowseComp-style tasks. TTD-DR's component-wise self-evolution is the heavier cousin (generate variants, judge, merge).
- **Why THIS user:** Cheapest form of test-time compute that fits a budget: no extra runs, just a rule on the two answers you already have.
- **Smallest harness change:** In the high-stakes corroboration path: regex hedging detector ("unable to determine", "could not find", "possibly") + require ≥1 `EvidenceSpan`; candidates failing either don't vote; if none remain, fall back to the unfiltered pair and mark the sub-question `partial`.
- **Sources:** Context Rot arXiv:2606.29718 (§5) · TTD-DR arXiv:2507.16075
- **Value×Effort:** M × L. **Novelty:** Medium-High. **Confidence:** ⚠2026 for the filter numbers; TTD-DR (2025, Google) for the general principle.
- **Dedup:** Top-2 corroboration exists; this is the missing filtering rule on top of it.

## 11. Active claim verification pass (CoVe-style, budget-bounded)

- **What:** For high-value claims, generate an independent verification question, answer it from a fresh retrieval, and revise. Chain-of-Verification's factored variant reduces hallucination by answering verification questions without seeing the original draft; ReClaim interleaves reference-then-claim so every sentence is grounded; Anthropic runs a separate CitationAgent pass and grades outputs on factual accuracy, citation accuracy, completeness, source quality, tool efficiency.
- **Why THIS user:** `audit_claims` checks structure (citation indexes exist, kinds valid); it never re-tests a claim against the web. One bounded verification query per numeric/date claim mostly hits cache and catches the transcription errors that grading cannot.
- **Smallest harness change:** In `audit_claims(final=True)`: for `Claim.kind == "fact"` whose value is numeric/date and confidence < threshold, emit a verification query string; the loop runs at most N of them (from `Budget`), compares values, and downgrades to `partial`/`contradicted` on mismatch. Report prompt: cite-before-claim ordering (ReClaim).
- **Sources:** CoVe arXiv:2309.11495 https://arxiv.org/abs/2309.11495 · ReClaim arXiv:2407.01796 https://arxiv.org/abs/2407.01796 · Anthropic (above)
- **Value×Effort:** M × L-M. **Novelty:** Medium. **Confidence:** High.
- **Dedup:** Claims/audit exist; active re-retrieval does not.

## 12. Freshness gating by question volatility

- **What:** Classify each sub-question as never-/slow-/fast-changing/false-premise and let that drive TTL, recency weight, and an "as of" stamp. FreshLLMs shows accuracy collapses on fast-changing questions and that recency-ordered evidence (FreshPrompt) recovers it.
- **Why THIS user:** `ttl_for(capability)` treats "population of France" and "current CEO of X" identically. A volatility axis prevents both stale cache hits on fast questions and wasted refetches on stable ones (budget again).
- **Smallest harness change:** `plan_research` tags `volatility` per sub-question (keyword/LLM one-liner); `ttl_for(capability, volatility=...)` scales TTL (fast: hours, slow: days, never: weeks); `grade_source` recency weight scales with volatility; renderer stamps fast claims "as of <date>".
- **Sources:** FreshLLMs arXiv:2310.03214 https://arxiv.org/abs/2310.03214
- **Value×Effort:** M × L. **Novelty:** Low-Medium (2023, under-applied). **Confidence:** High.
- **Dedup:** TTL exists per capability only. Extension.

---

## Considered and demoted (with reasons)

- **HyDE** (arXiv:2212.10496): built for dense retrieval; your providers are web/academic search APIs, so the gain is at most "hypothetical-answer keyword expansion". Low value here.
- **Step-back prompting** (arXiv:2310.06117): one line in the planner prompt ("first ask the higher-level question"); fine to add, not a reliability lever.
- **Self-RAG reflection tokens** (arXiv:2310.11511): requires a trained critic; borrow only as the rubric in find 6.
- **Plan-and-solve / ReAct:** already the skill's Understand→Plan→Execute loop; no delta.
- **MindSearch code-as-DAG, TTD-DR full diffusion, BAVT value-tree search** (⚠2026, arXiv:2603.12634), **MADAM-RAG multi-agent debate**, **AgentFold SFT folding:** each needs either a value model, multi-agent fan-out (Anthropic: ~15× tokens vs chat), or fine-tuning. Borrowed only as the lite versions in finds 4, 7, 8, 9.
- **Sub-agent context isolation** (best method for the strongest model in the Context Rot study): costs a fresh context per sub-question; on a RAM-starved box that is the failure mode you are trying to avoid. Prefer finds 4 and 7.

## Suggested order of implementation

Finds 2 → 3 → 1 first (they are additive, ~3 small modules plus a `status` field, and they make the 42% number diagnosable within the next batch of uses). Then 5 and 4 (stop the budget bleed). Then 6, 9, 8. Finds 7, 10, 11, 12 are quality lifts once partial runs are no longer counted as failures.