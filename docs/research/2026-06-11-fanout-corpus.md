## CLUSTER: discovery
DISCOVERY CLUSTER BRIEF
Generated: 2026-06-10 | Corroborator role

---

STRONGLY CORROBORATED CONCLUSIONS
(multiple probes agree, high confidence)

1. THE 30/50/200/740 TOOL DEGRADATION CURVE IS REAL

All six probes that touch benchmark data agree on the shape:
- <30 tools: >90% accuracy, all-in-context safe (RAG-MCP stress test)
- 30-50 tools: retrieval mandatory to stay above 80%
- 200 tools: severe degradation begins non-linearly (Zylos, RAG-MCP both)
- 740 tools: effectively 0% for most models (Zylos)

The non-linearity (cliff between 207 and 417 tools) is noted by ragmcp as a FLAG but is consistent with known long-context "lost-in-the-middle" behavior (position 40-60% drops to 22-52% selection accuracy) and ToolRet's NV-embed-v1 nDCG=33.83 baseline. Four independent data sources agree on the curve's shape even if exact thresholds vary.

2. CLAUDE CODE'S TOOL SEARCH IS ALREADY LIVE AND HANDLES THE PRIMARY PROBLEM

toolsearch and ragmcp agree on: `ENABLE_TOOL_SEARCH` default-on since v2.1.x, `auto:N` syntax added v2.1.9, `alwaysLoad` added v2.1.121+. Accuracy numbers match across both probes (Opus 4: 49%→74%, Opus 4.5: 79.5%→88.1%). Token reduction numbers converge (85% on a typical 5-server setup, scaling to 92%+ at 500+ tools). Both probes cite the same Anthropic engineering blog as primary source - HIGH confidence these numbers are valid.

3. THE HTTP TRANSPORT BUG IS REAL AND UNMITIGATED

codeexec and toolsearch independently confirm: ENABLE_TOOL_SEARCH does NOT defer HTTP/SSE MCP tools (Issue #40314, closed "not planned"). Only stdio transport benefits. toolsearch quantifies: 120K tokens loaded upfront for a 250-tool HTTP gateway even with the setting on. This is a critical deployment constraint for the user's 40-server setup - any HTTP-transport MCP server is completely unaffected by the tool search feature.

4. BM25 BEATS DENSE EMBEDDINGS FOR TOOL NAMES, HYBRID WINS OVERALL

ragmcp, toolret, and tooldesc all report this counter-intuitive finding: on ToolBench, BM25 achieves NDCG@5=0.853 vs dense embedding at 0.834. Reason: tool names are technical compound identifiers ("get_function_xrefs") where lexical overlap is a stronger signal than semantic similarity. Hybrid (BM25 + dense) wins overall, which is exactly what Anthropic's production Tool Search implements (BM25 + regex variants). CONFIRMED across three probes.

5. DESCRIPTION SCOPE CLAUSE IS THE HIGHEST-ROI SINGLE CHANGE

tooldesc and skilltrigger independently converge: the "Use this tool when X / do NOT use when Y, use Z instead" pattern is the most impactful description element. tooldesc cites Trace-Free+'s finding of <12% original coverage → 97.2% after rewriting, with 29.23% reduction in accuracy degradation at 150+ tools. skilltrigger calls it "the single most important line in the description" for large skill libraries. Two independent probes, consistent conclusion.

6. SKILL BODY TEXT IS REQUIRED FOR RETRIEVAL (NOT JUST METADATA)

semrouter's SkillRouter result (31-44 percentage point drop when bodies are hidden) and tooldesc's SkillRouter citation both flag the same finding: routing retrieval needs the full implementation body, not just name+description. This contradicts the intuition that "just write a good description" is sufficient. Two probes cite the same paper (arXiv 2603.22455) consistently.

7. ALL-IN-ONE MINIS ARE CHEAP AND EFFECTIVE AT 600-TOOL SCALE

ragmcp, tooldesc, semrouter, and codeexec all recommend `all-MiniLM-L6-v2` (22M params, 3.5ms CPU) for the user's ~600-tool scale (40 servers × ~15 tools). It's proven at 2,413 tools in OATS. No GPU required. This is the practical recommendation for a Windows power-user running tools locally.

---

CONTRADICTIONS / DISAGREEMENTS

C1. Token reduction claims vary widely and are partly incompatible

- Anthropic Tool Search: 85% reduction (toolsearch, ragmcp)
- MCP-Zero on APIBank full corpus: 98% (mcpzero, toolret)
- Tools-as-filesystem pre-tested scripts: 99.6% (codeexec)
- Semantic MCP discovery (arXiv 2603.20313): 99.6% token reduction, 97.1% hit rate (toolret, ragmcp)

These numbers are not contradictory when you realize they measure different things against different baselines. Tool Search measures reduction in schema-loading overhead per session; MCP-Zero measures tokens per APIBank task turn; scripts pattern measures discovery tokens vs loading all schemas. They compose, they don't compete. But the probes present them without this clarification, which could mislead someone choosing an approach.

C2. OATS accuracy claims diverge slightly

ragmcp reports: MetaTool (199 tools) Recall@1 0.716→0.830 (+11.4%), NDCG@5 0.869→0.940.
semrouter reports: OATS achieves 83.4% accuracy on MetaTool at 3-7ms CPU.
toolret reports: MetaTool NDCG@5 0.869→0.940.

The 83.4% figure in semrouter appears to be a different metric or rounded form of the same number. No genuine contradiction but the way semrouter presents it (as standalone accuracy vs LLM routing) and ragmcp presents it (as improvement delta) could be confusing. Underlying paper is the same (arXiv 2603.13426).

C3. MCP-Zero vs Tool Search framing

mcpzero treats MCP-Zero as a complementary technique to Anthropic's Tool Search (compound cosine scoring adds precision over BM25). ragmcp says "you don't need to separately implement MCP-Zero" because Tool Search already covers it. This is a real disagreement. mcpzero is correct that the scoring formulas differ and the hierarchical server-then-tool structure is not replicated by Tool Search's BM25. ragmcp is correct that for the user's scale, the marginal gain from MCP-Zero's compound scoring over BM25 may not justify the implementation cost. Resolution: Tool Search is the starting point; MCP-Zero's compound scoring is an optional upgrade for the 5-10% of cases where BM25 mis-ranks tools with similar names.

C4. skillListingBudgetFraction: probes assume different defaults

skilltrigger reports default `skillListingBudgetFraction=0.01` (1% of context). codeexec does not mention this field at all. toolsearch mentions ENABLE_TOOL_SEARCH without connecting it to the skill budget. These cover different layers (MCP tools vs skills) but the interaction between them - both competing for the same context window budget - is not addressed by any probe. Gap, not strictly a contradiction.

---

GAPS (unanswered or undercovered)

G1. No probe addressed dynamic MCP server lifecycle management

All approaches (Tool Search, MCP-Zero, tools-as-filesystem, semantic routing) assume servers are already running. None covers spinning MCP servers up/down on demand. mcpzero explicitly calls this out as MCP-Zero's acknowledged limitation. lazy-tool indexes statically. This is an open problem in 2026 with no shipped solution.

G2. Cross-session memory for tool discovery state is not addressed

After context compaction, toolsearch documents that discovered tools can silently disappear (agent re-searches automatically but adds latency). No probe addressed how to persist tool-routing state across sessions or how basic-memory could be used to accelerate re-discovery after compaction. This is a genuine gap for the user's use case.

G3. The interaction between skillListingBudgetFraction and ENABLE_TOOL_SEARCH is uncharted

Skills and MCP tools compete for the same context budget via different control paths. No probe models the combined token budget and what happens when both mechanisms are active simultaneously at the user's scale (40 MCPs + 100s of skills).

G4. No probe covered Codex CLI or Antigravity tool discovery

All probes are Claude Code / Anthropic API centric. The user also runs Codex CLI and Antigravity. How tool routing interacts across three agent backends sharing the same MCP server pool is not addressed.

G5. Adversarial/untrusted MCP server risk is noted but not mitigated concretely

ToolCert (ragmcp) and ToolHijacker (tooldesc) are both cited but none of the probes provided a concrete mitigation stack for the user's scenario. The 0.82 cosine similarity deduplication threshold (ToolScope) is the closest to a concrete defense.

G6. OATS implementation is described but no working code for Windows was identified

Multiple probes recommend OATS (arXiv 2603.13426) but none found an open-source implementation. The paper describes ~50 lines of Python with formula `ê_i = (1−α)·e(d_i) + α·ē(Q⁺) − β·ē(Q⁻)` (α=0.3, β=0.1). It would need to be implemented from scratch.

---

NOVEL / NON-OBVIOUS IDEAS WORTH CARRYING FORWARD

N1. Built-in Claude Code tools (Bash, Read, Edit) were moved behind ToolSearch in v2.1.69 without release notes (Issue #31002). This adds a round-trip on fresh sessions for the very first Bash call. Any skill or hook that assumes immediate Bash availability may now have a hidden latency. HIGH PRIORITY to verify in the user's setup.

N2. The "less body text is more accurate" finding from SkillReducer (48% compression → +2.8% quality) is genuinely counter-intuitive and worth acting on. The mechanism is attention dilution from boilerplate. Directly applicable to the user's skills/ directory.

N3. OATS zero-latency embedding shift: offline refinement of tool embeddings toward historically-successful query centroids requires no serving infrastructure change, runs on CPU, and delivers +11.4% Recall@1. The user's basic-memory MCP already logs session outcomes - those logs are the raw input for OATS. This is the most underrated technique across all probes.

N4. SkillRouter body-field finding changes the architecture: you need TWO representations per skill - a short routing label for context injection, and the full body for vector indexing. These serve different consumers. The short label is what the agent sees; the body is what the retriever uses to find it. Most implementations only have one representation.

N5. MCP-Zero compound scoring formula `(s_server × s_tool) × max(s_server, s_tool)` is non-standard and unvalidated against simpler alternatives (flagged by mcpzero). If it genuinely outperforms plain cosine, it would be worth adopting in a custom search handler. But the ablation is missing from the paper - treat as provisional.

N6. Tool selection is gameable via description text alone (ToolHijacker, "assertive cues" 7-12x usage inflation). For a user who auto-discovers community MCP servers, this is a practical security concern, not just academic. The 0.82 cosine deduplication threshold before adding any new server is a concrete first-line defense.

N7. `user-invocable: false` does NOT prevent model auto-invocation of skills. Only `disable-model-invocation: true` blocks it. This is a documented surprise (Issue #19141) that creates "shadow skills" - invisible to the user's slash-command menu but still silently callable by Claude. Audit the user's skill library for this combination.

N8. `outputSchema` in the June 2025 MCP spec is underused: none of the 2025 tool description papers mention it, but it mechanically enforces output structure with downstream validation. For any tool whose output feeds another tool's input, this is the correct implementation over natural-language output descriptions.

N9. lazy-tool (Go, MIT, single binary) solves both the HTTP transport bug AND the 40-server MCP aggregation problem in one move: it proxies all 40 servers through a single stdio endpoint, making them all Tool Search compatible regardless of their original transport. This is the most pragmatic single fix for the user's current setup.

---

BOTTOM LINE FOR ACTION

The three highest-ROI non-overlapping actions for the user's specific setup:

1. Verify ENABLE_TOOL_SEARCH=auto:5 is working on stdio servers, then migrate any HTTP MCP servers to stdio (or route through lazy-tool) to close the HTTP transport gap - this is the biggest token leak.

2. Audit every skill description for the scope clause pattern ("do NOT use when X, use Y instead") and raise skillListingBudgetFraction to 0.04-0.05 to prevent silent skill dropping at 100+ skills.

3. Index full skill bodies (not just names+descriptions) in a FAISS/SQLite-vec vector store using all-MiniLM-L6-v2, and plan to apply OATS-style centroid refinement once 100+ successful invocations are logged in basic-memory.

## CLUSTER: memory
MEMORY CLUSTER BRIEF — CORROBORATION REPORT

=== STRONGEST CORROBORATED CONCLUSIONS (3+ sources converge) ===

**C1 — Context rot is continuous, not threshold-based**
[ctxeng + compaction + coala + memframeworks] All four probes agree: degradation begins from the first token, not at window limits. The 30-55% accuracy drop for middle-position content (lost-in-the-middle) is confirmed by the Chroma 2025 study cited in ctxeng and independently corroborated in the framework comparisons in memframeworks. The 5-layer Claude Code compaction cascade (compaction probe) is a direct engineering response to this continuous rot.

**C2 — JIT/pull beats push for dynamic data; external files beat in-context accumulation**
[ctxeng + docsastruth + compaction + memframeworks] All probes agree on the principle: keep identifiers in context, load content via tools. The 3-file recovery pattern (docsastruth), CLAUDE.md as pointer-not-content (docsastruth), and the compaction-survival hierarchy (redis pattern in compaction) are all implementations of the same axiom. Anthropic's own engineering blog states it directly: "Assume interruption. All progress not recorded in memory is at risk."

**C3 — Tool minimalism is mandatory at 40 MCPs; Tool Search is the solution**
[ctxeng] A 5-server MCP setup with 58 tools burns ~55K tokens before first message. Anthropic's Tool Search (`defer_loading: true`, BM25 retrieval) shipped January 14, 2026, reduces overhead 85% and lifts Opus 4 accuracy 49%→74%. No other probe contradicts this; all assume it. This is the single highest-ROI change for the target workspace.

**C4 — Episodic memory: subtask-granular + category-filtered + abstract wins; raw/upfront injection harms**
[coala] Multiple ablations on SWE-bench (arXiv:2602.21621) and HumanEval (Reflexion) converge: abstract insights (+3.9pp) beat raw trajectories (+1.2pp); subtask-granular (+4.7pp avg) beats instance-level (+1.6pp); per-step dynamic retrieval beats upfront injection. The CTIM-Rover paper is the critical counter-evidence: episodic memory caused a 2pp regression when injected upfront without filtering. Both findings are HIGH confidence and compatible: the mechanism that helps (filtered, abstracted, dynamic retrieval) is distinct from what hurts (dump-all upfront).

**C5 — Compaction leaves ~20-30% of detail; skills are lost entirely; PreCompact-on-/compact is broken**
[compaction] Three independently confirmed bugs shape recovery design: (1) skills context is lost after compaction (GitHub #13919, closed not planned); (2) PreCompact hook does NOT fire on manual /compact (GitHub #13572, closed not planned); (3) AutoDream's lock file silently disables it permanently on crash (GitHub #50694, open). The `source=compact` SessionStart hook and `additionalContext` injection are the recovery mechanism but rely on undocumented behavior.

**C6 — Two-layer stack beats any single framework for the target workspace**
[memframeworks + kgmemory] All comparison work agrees: no single framework optimally covers storage, curation, retrieval, and lifecycle. The consensus recommendation across memframeworks and kgmemory is identical: IDE-native plugin (claude-mem or basic-memory) for session continuity/compaction survival + graph-capable MCP (Graphiti or Hindsight) for semantic/temporal retrieval.

**C7 — HOT/WARM/COLD tiering reduces session costs 65-75%**
[memframeworks + ctxeng + compaction] HOT <500 tokens, WARM 1,000-3,000 tokens, COLD compressed. Trigger proactive compaction at 60-70% fill rather than waiting for the 83.5% auto-trigger; the ctxeng probe shows coding agents reach critical degradation at ~35 minutes. Setting `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70` operationalizes this.

**C8 — Procedural/skill memory: Skill-Pro achieves 99.3% compression vs RAG, but SWE-Skills-Bench shows 39/49 SE skills = zero improvement**
[coala] Both findings are HIGH confidence and compatible: Skill-Pro's gains are on ALFWorld (tool-use tasks), not code generation. The SWE-Skills-Bench finding (only 7/49 skills gave meaningful gains; 3 caused degradation up to -10%) is a direct caution against naive skill-library enthusiasm for SE agents. Skills are a narrow intervention requiring domain fit.

**C9 — Deduplication outperforms aggressive summarization for factual accuracy**
[sleeptime] Microsoft's production system (97.2% retention precision, 58% storage reduction) validates deduplicate-then-compress ordering. Aggressive merging destroys detail needed for correct retrieval. This directly constrains how compaction prompts and Dreams API calls should be configured.

**C10 — Graph > vector for temporal/relational queries; bi-temporal model is the architecture**
[kgmemory + memframeworks] Graphiti's four-timestamp per-edge model (tvalid, tinvalid, t'created, t'expired) enables point-in-time queries and contradiction resolution without deletion. Zep's 72x context compression (115k tokens → 1.6k average) alongside accuracy gains inverts the usual accuracy-cost tradeoff. Both probes identify this as the highest-accuracy self-hostable temporal memory architecture.

=== CONTRADICTIONS / DISAGREEMENTS ===

**X1 — Vendor benchmark scores are unreliable by 15-45 points**
[memframeworks] Independent evaluation (paperclipped.de) shows Mem0 at ~58% LoCoMo vs. 92.5% self-reported; Zep at ~58.44% vs. ~85% self-reported. MemPalace's 96.6% is ChromaDB's score, not MemPalace's. The ctxeng and coala probes cite these benchmark numbers without flagging the inflation. Consumer: treat all single-source benchmark claims with skepticism; require cross-benchmark validation (LoCoMo + LongMemEval + BEAM).

**X2 — Episodic memory: improvement vs. no-improvement for code quality**
The Sandelin controlled benchmark (memframeworks/coala, MED confidence, one system) finds episodic memory gives "0% improvement in code correctness, 14-32% cost savings." The subtask-level SE memory paper (arXiv:2602.21621, HIGH confidence) finds +4.7pp on SWE-bench. These are compatible if interpreted carefully: correctness on simple tasks is unchanged; complex tasks and efficiency show gains. However the framing differs enough to cause confusion. Resolution: episodic memory helps on hard tasks and reduces cost, does not reliably improve correctness on easy tasks.

**X3 — KuzuDB backend status**
[kgmemory + memframeworks] kgmemory references the Vela Partners fork as "actively maintained" and cites 374x speed claim. memframeworks notes the Kuzu backend is now deprecated in Graphiti v0.29.2 and the Vela fork is a single-organization fork with sustainability risk. This is a genuine contradiction: kgmemory treats it as viable, memframeworks treats it as risky. Resolution: FalkorDB is the safer recommendation for a new Graphiti deployment.

**X4 — Zep Community Edition status**
[memframeworks] Deprecated April 2025 — not maintained. [kgmemory] Treats Graphiti (the open-source engine, not the cloud product) as fully viable. These are actually compatible once the distinction between Zep Community Edition (deprecated) and Graphiti open-source (active, v0.29.2 as of June 8, 2026) is clarified. Migration path: Zep CE → Graphiti + FalkorDB.

=== GAPS (not answered by any probe) ===

**G1 — Anthropic Dreams API access gate**: All probes acknowledge it exists and cite its value. None confirm whether it is accessible to the standard Max/Pro subscription (vs. API-only enterprise). No probe fetched the actual request form or confirmed approval timelines.

**G2 — SkillRouter full-text requirement for the 100s-of-skills case**: coala confirms that routing 80K skills requires the full implementation body (31-44pp drop if body hidden). No probe addressed how to structure skill files for the SkillRouter BM25 pipeline specifically, or how to implement it for the Claude Code/basic-memory skill vault.

**G3 — MemAdapter bridge between basic-memory and graph**: kgmemory flags arXiv:2602.08369 as a potential bridge tool (13-minute alignment, flat notes → graph KG) but marks it as a flag-to-corroborate, not a confirmed implementation. No probe verified whether it works on basic-memory's markdown format specifically.

**G4 — Weibull decay implementation in any existing MCP server**: SSGM (arXiv:2603.11768) describes the mathematical framework. kgmemory explicitly flags: "no existing off-the-shelf MCP server implements this." No probe found a working implementation.

**G5 — The retrieval-use gap**: sleeptime flags this as the most important unsolved problem — agents retrieve facts correctly but fail to apply them in decisions (40-60% drop on MemoryArena vs LoCoMo). No probe proposed a concrete solution beyond "active context injection at the right decision point." This remains architecturally open.

**G6 — SSGM write-gate integration with basic-memory**: The semantic drift risk to compaction checkpoints (mempoison + kgmemory agree this is real) is unaddressed at the implementation level. No probe specified how to add a contradiction-check gate to basic-memory's write_note calls without modifying the MCP server.

**G7 — CCL (Context Compression Language)**: Mentioned in compaction as a user-invented notation achieving 65-72% CLAUDE.md compression. No other probe referenced it. Unknown whether the BPE tokenizer exploitation it relies on is stable across model versions.

=== MOST NOVEL / NON-OBVIOUS FINDINGS WORTH CARRYING FORWARD ===

**N1 — PreCompact does NOT fire on /compact (highest operational urgency)**
[compaction] The best practice is proactive /compact (before 83.5% threshold). But the PreCompact hook only fires on auto-compaction. Manual /compact silently bypasses every checkpoint hook. Any recovery architecture built on PreCompact is broken for the most important use case. Fix: run checkpoint script explicitly before calling /compact, or build the checkpoint into a Stop hook instead.

**N2 — AutoDream stale lock = permanent silent disable**
[compaction] Check for `~/.claude/projects/*/memory/.consolidate-lock` files older than 10 minutes on your system right now. This bug (GitHub #50694) silently prevents all future AutoDream consolidation with no visible error. A cron job to clean stale lock files is the practical fix.

**N3 — Compaction uses a smaller/different model for summarization**
[compaction] The summarization call can itself overflow, causing a deadlock at 48% context usage (confirmed on Opus 4.6, GitHub #23751). This explains "compaction fails exactly when needed most." The architectural fix is `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70` — compact earlier when the context is still small enough for the summarization model to process.

**N4 — Memory seeding as proactive security**
[mempoison] Pre-populating basic-memory with high-quality legitimate entries reduces MINJA attack success from 62% to 6.67% (GPT-4o-mini). This is not mentioned anywhere in the security literature as a defense recommendation — it falls out of the dilution effect. For the existing basic-memory vault, this is immediately actionable at zero infrastructure cost.

**N5 — Compaction checkpoints are an attack surface**
[mempoison] The PreCompact hook writes high-trust memory entries that are read back on context recovery. A compromised agent running before compaction could poison the checkpoint and the poison survives compaction. No paper explicitly addresses hook-induced memory persistence as an attack vector. Mitigation: restrict write_note calls from non-orchestrator agents, especially in the pre-compaction window.

**N6 — LogAct's 41% token reduction from supervisor coordination alone**
[docsastruth] Meta's LogAct (arXiv:2604.07988) — typed shared log with voting, abort, and semantic recovery — achieved 17% more work and 41% fewer tokens vs baseline. A crashed agent's successor diagnosed a pathological sort and completed remaining work 290x faster. No other multi-agent coordination pattern in any probe achieves comparable efficiency gains. Worth direct implementation investigation for the metaswarm orchestration layer.

**N7 — ICLR 2026: omitting "ask clarifying questions" drops resolve rate from 48.8% to 28%**
[docsastruth] Without explicit instruction in AGENTS.md/CLAUDE.md, agents default to non-interactive behavior. This is the direct cause of tunnel-vision. The fix is a single explicit line in CLAUDE.md: must ask clarifying questions before long-horizon tasks when intent is ambiguous. Lowest-effort/highest-impact change for the inquisitive behavior goal.

**N8 — REM-phase generative association in SCM**
[sleeptime] SCM's sleep cycle generates new associative edges via random walks — not compression, but synthesis of novel connections absent in raw experience. For a workspace accumulating sessions across BC RE, trainer GUI, social MCP, etc., this could surface cross-project patterns no single session contained. Currently only in SCM (open-source, Python/Ollama/NetworkX/SQLite, 8GB RAM); not in any production system. Flag: verify at scale before relying on it.

**N9 — Coherent documents can degrade performance MORE than shuffled haystacks**
[ctxeng] Topically coherent but factually irrelevant content creates the worst distractor interference — worse than random noise. This means a well-organized CLAUDE.md with deprecated rules or superseded decisions can be more harmful than a sparse or poorly organized one. Implication: regular culling of outdated content from CLAUDE.md and memory notes is not just hygiene but performance-critical.

**N10 — MemAdapter: 13-minute bridge from flat notes to graph KG**
[kgmemory] arXiv:2602.08369 claims cross-paradigm alignment between basic-memory-style flat notes and a proper graph KG in 13 minutes on a single GPU. If verified on basic-memory's markdown format, this could unify the existing vault with a graph layer without starting over. Currently a flag-to-corroborate; no production deployment evidence found.

=== SYNTHESIS FOR ACTION PRIORITY ===

Immediate (no new infrastructure):
1. Check and clear stale AutoDream lock files (N2)
2. Set `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70` (C7, N3)
3. Add "must ask clarifying questions" to CLAUDE.md (N7)
4. Seed basic-memory vault with high-quality legitimate entries per project (N4)
5. Rebuild PreCompact hook to also fire on Stop (workaround for N1)

Near-term (new tools, existing stack):
6. Enable Tool Search (`defer_loading: true`) on all 40 MCP servers (C3)
7. Add namespace prefixes to all basic-memory write_note calls; gate subagent write access (N5, mempoison)
8. Add `compactPrompt` in settings.json to preserve decisions verbatim (compaction)
9. Add `llms.txt` to active projects (docsastruth)

Medium-term (new infrastructure):
10. Add MemoryGraph MCP (Windows-native, SQLite) or Graphiti+FalkorDB (WSL2) as semantic/temporal layer above basic-memory (C6, C10)
11. Request Anthropic Dreams API research preview access; configure weekly Routine (sleeptime)
12. Investigate LogAct pattern for metaswarm orchestration (N6)

## CLUSTER: antidegen
**ANTIDEGEN CLUSTER BRIEF**

Cross-checking [loops], [specra], [progress], [ralph], [longhorizon], [hung] — five probes with ~150+ aggregate sources.

---

## STRONGLY CORROBORATED CONCLUSIONS (3+ sources agree)

**C1. Ambiguous tool feedback is the dominant root cause, not model defect.**
All probes converge: when tools return non-terminal signals ("more results may be available"), agents rationally keep calling. Terminal-state tool redesign (explicit SUCCESS:/FAILED: strings with transaction IDs) is the single highest-leverage fix — empirically 7x reduction (14→2 calls, 21s→4s) before any hook infrastructure. [loops], [specra], [ralph], [progress] all cite the same AWS/Strands demonstration.

**C2. Three-tier detection stack has consensus: exact-match hash → semantic/FFT → semantic loop (embedding).**
- Tier 1: SHA-256 of `(tool_name + canonical_json(args))`, sliding window 10-20, trigger at 3 consecutive hits. Cheapest. Misses near-miss loops.
- Tier 2: SpecRA FFT autocorrelation on token stream — catches near-miss lexical loops that hashing misses, O(N log N), black-box/streaming deployable. [specra]
- Tier 3: Semantic embedding cosine similarity, calibrated threshold ~0.85 (not raw cosine — space is anisotropic). [progress] cites λ=0.8/κ=2 contractive regime taxonomy.
All agree: hash is a necessary cheap first layer; alone it is insufficient for sophisticated agents that vary phrasing on each retry.

**C3. Result-aware detection beats input-only fingerprinting for polling tools.**
[loops] (zeroclaw #2152) and [specra] independently arrive at the same fix: trigger only when `(tool_name, args_hash, output_hash)` repeats — same args + different output = genuine progress, not a loop. Critical for 40-MCP stacks where health-check/status tools have identical args by design.

**C4. TIDE two-axis taxonomy is correct and actionable.**
[loops] and [specra] corroborate: "recursive looping" and "accumulated memory" are distinct failure axes requiring different fixes. Applying a fingerprint guard to a context-overloaded agent fails because the agent is looping due to attention dilution, not lack of a stop signal. The correct fix for the memory axis is ToolSearch deferred loading + subagent isolation, not loop detection.

**C5. Budget enforcement must be synchronous/pre-call, not async alerts.**
[hung], [progress], and [ralph] all cite the $47K incident (63-incident catalog, arXiv:2606.04056): async alerts require human action that may not arrive. Hard pre-call budget proxy is mandatory. Rust affine-type ownership is the correct design pattern; Python equivalent is a context manager that raises `BudgetExhausted` before the API call.

**C6. Fresh-context-per-iteration (Ralph pattern) severs all three context-rot failure modes simultaneously.**
[ralph] and [longhorizon] corroborate: context poisoning, attention dilution, goal drift all require accumulated context to propagate. Ralph/Reflexion-style fresh iterations with filesystem state externalization are the architectural cure. Anthropic multi-agent (subagents with isolated context) achieved 90.2% improvement over single long-session agents on the same benchmark.

**C7. Heuristic detectors beat LLM judges for failure detection.**
[progress] cites the 7000-trace study: 60.1% accuracy at $0.00 vs. Claude 3.7 Sonnet at 4.7% accuracy at $0.05–0.15/trace. Deterministic rule-based checks are the right first tier; LLM judges only for the ~40% that heuristics escalate.

**C8. Block message wording matters.**
[loops] and [ralph] both note: a silent deny causes the model to retry with slightly varied args (bypassing hash guard). `permissionDecisionReason` must be sent back to Claude as the tool result with explicit instruction ("BLOCKED: Duplicate call detected — try a different approach"). This triggers strategy change rather than phrasing variation.

**C9. 75% of agent turns produce no recovery-relevant state changes.**
[hung] (Crab, arXiv:2604.28138): checkpoint-on-every-turn is 4x more expensive than needed. eBPF effect classification before checkpointing cuts overhead 87% while recovering correctness 8%→100%. Corroborates the observation-masking finding in [longhorizon]: replace older tool outputs with single-line placeholders, preserve reasoning and action records — 52% cheaper than LLM summarization, 2.6% better solve rate.

**C10. Context rot begins at ~50K tokens in a 200K window; all 18 tested frontier models degrade monotonically.**
[ralph] (Chroma 2025 study). Non-obvious corollary corroborated by [longhorizon]: **well-organized codebases cause MORE rot than disorganized ones** — structural coherence creates plausible distractors that degrade attention further. Implication for a Windows power-user with a large organized codebase: single-session context is more dangerous, not less.

---

## CONTRADICTIONS / DISAGREEMENTS

**X1. LLM-based loop detection (Gemini CLI d8618f6) vs. heuristic-first recommendation.**
[loops] describes Gemini's upgrade to route loop detection through the model itself for semantic accuracy. [progress] cites the 60.1% vs. 4.7% study recommending heuristics first. These are not fully reconciled — the Gemini approach trades token cost for accuracy on ambiguous cases, while the heuristic-first approach is validated on production traces. Resolution: heuristics handle ~60% cleanly at zero cost; LLM judge is appropriate for the escalated remainder, not as primary detection.

**X2. Reflection: essential vs. harmful.**
[longhorizon] cites the 2024 ICLR finding that intrinsic self-correction is unreliable (coherence trap). [progress] shows selective reflection (only when step score <2/10) outperforms both unrestricted reflection AND no reflection. [ralph] cites Generative Agents study: removing reflection causes behavioral degeneration within 48 simulated hours. Resolution: the sources agree on the nuance — threshold-triggered reflection with external grounding, not cadence-based and not eliminated. The apparent contradiction is between "reflection as implemented naively" (harmful) and "reflection triggered by failure signal against external ground truth" (beneficial).

**X3. Model size vs. memory architecture ROI.**
[longhorizon] states memory architecture accounts for 45% performance variance while scaling 8B→32B gives only 3.8% improvement. This is a strong claim from a single source (AMA-Bench). No other probe explicitly corroborates the exact numbers. Flag as directionally correct but specific percentages need verification against the full paper.

---

## GAPS (NOT ANSWERED)

**G1. SpecRA formal bounds claim unverified.**
[specra] flags: "theoretical bounds on false positives and detection efficacy" are claimed in the abstract but the full PDF was not parseable. The JL-style bounds for the randomized projection are the single most important technical claim — if they hold, SpecRA is the only black-box degeneration detector with formal guarantees. Not corroborated by any other probe.

**G2. Multi-period nested loops — no production implementation found.**
[specra] identifies that SpecRA detects multiple simultaneous loop periodicities via FFT (all periods visible in the spectrum simultaneously). No probe found a deployed system that handles this case. Standard hashing with any fixed window misses it. Gap: there is no production code to reference.

**G3. CUSUM hidden-state early warning — white-box only, no production deployment.**
[ralph] and [specra] both flag arXiv:2601.05693: semantic circularity precedes textual repetition by ~40 sentences/~1500 tokens, detectable via hidden-state cosine similarity. Potentially very high value (fire before wasted tokens), but requires white-box model access — not applicable to Claude/Codex API. No production tool wraps it. Gap remains open for API-only stacks.

**G4. AgentPRM Promise signal — not yet implemented in any mainstream harness.**
[ralph] and [longhorizon] both identify the Promise/Progress dual-signal gap: existing DONE gates almost exclusively measure Progress (tests pass, coverage%) but not Promise (is the overall trajectory still viable toward the global goal?). AgentPRM (arXiv:2511.08325) formalizes this but no harness ships it. Gap: the theoretical fix exists, the engineering implementation does not.

**G5. Windows-specific IPC deadlock — no fix merged.**
[hung] documents Claude Code issues #49150 and Windows stdio pipe deadlock (JSON chunk straddling buffer boundary). "Not planned" as of research date. No cross-probe corroboration adds new information. The gap is a known unresolved platform bug.

**G6. MCP overthinking-loop attack — no mitigation tooling exists.**
[specra] cites arXiv:2602.14798: a malicious MCP server can induce cyclic trajectories where each individual call looks benign (up to 142x token inflation). SpecRA's aggregate token-stream view is architecturally better positioned to catch this than per-call fingerprinting. No probe found deployed mitigation tooling for this specific attack on a 40-MCP stack.

---

## MOST NOVEL / NON-OBVIOUS IDEAS TO CARRY FORWARD

**N1. Result-aware fingerprinting is load-bearing for polling tools (not widely implemented).**
Standard exact-match hash generates destructive false positives on any tool that polls external state with fixed args. The correct triplet is `(tool_name, args_hash, output_hash)`. For a 40-MCP stack with health-check and status tools, this distinction is critical. No major framework ships this by default.

**N2. The TIDE two-axis diagnosis changes which fix to apply.**
If an agent is looping due to context overload (accumulated memory axis), a fingerprint guard will not stop it — the agent cannot process its history well enough to recognize it is repeating. Correct diagnosis determines the fix: loop detection for recursive-looping axis; ToolSearch deferred loading + session rotation for accumulated-memory axis. Wrong diagnosis wastes engineering effort.

**N3. Observations should be masked, not summarized.**
Replace older tool outputs with single-line placeholders, preserve reasoning/action records. 52% cheaper than LLM summarization, 2.6% better solve rate (JetBrains 2025). This counterintuitive result (throwing data away outperforms intelligent compression) has no production library wrapping it — must be custom-implemented.

**N4. ACRFence semantic rollback: retried LLM calls synthesize DIFFERENT requests.**
Unlike traditional programs, an LLM agent re-entering after checkpoint restore does not replay the original request — it synthesizes a new one. This enables action replay (duplicate payments) and authority resurrection (reuse of consumed credentials). The fix (ACRFence, arXiv:2603.20625) records irreversible tool effects and enforces replay-or-fork semantics. Overlooked in every checkpoint-restore implementation this cluster reviewed.

**N5. Scratchpad usage is the strongest predictor of success in 100s-of-turns planning.**
YC-Bench (arXiv:2604.01212): Claude Opus 4.6 achieved highest performance specifically due to superior scratchpad usage. Agents that externalized suspicion signals to scratchpad detected adversarial events; those relying on working memory missed them. Implication: harness design should explicitly encourage and preserve scratchpad writes as first-class compaction-survival artifacts, not treat them as disposable reasoning traces.

**N6. Timely Machine reframes budget as wall-clock, not tokens.**
For tool-heavy agents, token generation time is decoupled from tool latency. Wall-clock budget per task type is the correct primitive. No major framework adopted this as of the January 2026 paper. For a Windows stack with 40 MCP servers where tool latency varies 10ms–10s, this framing changes how to set caps.

**N7. Ping events as watchdog keep-alive — naive watchdogs false-positive on valid slow responses.**
[hung] FLAG: Anthropic's API already sends periodic `ping` SSE events during extended thinking. A watchdog that resets only on content tokens will kill valid slow responses. Correct implementation resets on ALL SSE event types. This specific failure mode in naive watchdog implementations is non-obvious.

**N8. Causal provenance annotation costs almost nothing and has outsized memory retrieval impact.**
AMA-Bench (arXiv:2602.22769): causality graph ablation shows 24.6% accuracy drop when removed. The engineering cost is annotating each memory write with causal parents at write time. This requires only a metadata field addition to an existing memory store — no new infrastructure. The basic-memory MCP already in use is compatible with this pattern.

---

**Bottom line for implementation priority:**
1. Terminal-state tool redesign (zero infrastructure cost, 7x impact)
2. Result-aware fingerprint guard as PreToolUse hook (not exact-match)
3. Two-threshold session management (64%/80% context → checkpoint/rotate)
4. Observation masking as compaction mechanism
5. Synchronous budget proxy (pre-call, not async alert)
6. Causal provenance on basic-memory writes
7. External watchdog polling transcript mtime (independent failure domain)
8. ACRFence-style idempotency for any checkpoint-restore involving write tools

## CLUSTER: hooks
HOOKS CLUSTER BRIEF

STRONGEST CORROBORATED CONCLUSIONS (3+ independent sources agree)

1. exit 2 is the ONLY blocking exit code. exit 1 is a silent non-blocking warning and the #1 production bug. Confirmed across [hooksref], [tddguard], [hookbalance], [hookcollections]. Every source flags this. Stop hooks need JSON {"decision":"block"} + exit 0, not exit 2 — that distinction is confirmed by [hooksref] and [tddguard].

2. stop_hook_active flag is mandatory. Without checking it, every Stop hook is a potential infinite loop. Confirmed [hooksref] + [hookbalance] (GitHub #55754 documents a 50-minute session exhausted by the loop). Pattern: check the flag, exit 0 immediately if true. The alternative approach ([hookcollections]) is a marker file, which achieves the same thing but is fragile on crash.

3. 5 handler types as of 2026: command, http, mcp_tool, prompt, agent. Confirmed [hooksref] + [tddguard] + [hookcollections]. mcp_tool is new in v2.1.141+. http and prompt are confirmed independently. agent is flagged EXPERIMENTAL in [hooksref] only.

4. UserPromptSubmit hooks cannot directly ask clarifying questions — they are synchronous transform filters, not interactive flows. AskUserQuestion must be invoked by a skill. Hook is the router, skill is where the interaction happens. Confirmed [clarifyhook] + [hooksref] (30-second timeout, no AskUserQuestion available inside hooks).

5. Async hooks (async: true) never block and should be used for all logging/observability. asyncRewake: true allows a background hook to wake Claude at next idle. Confirmed [hooksref] + [tddguard] + [hookcollections].

6. PostToolUse cannot undo a completed tool call but CAN rewrite what Claude sees via updatedToolOutput, and injects stderr back to Claude as context. Confirmed [hooksref] + [tddguard] + [hookbalance]. This is the correct pattern for post-hoc correction.

7. HTTP hooks fail open on network error. mcp_tool hooks fail open on server disconnect. Neither is suitable for hard safety gates. Confirmed [hooksref] + [hookbalance] + [hookcollections].

8. PreToolUse updatedInput (argument rewriting) requires permissionDecision: "allow" to be set alongside it, or it is silently ignored. Confirmed [hooksref] + [hookcollections]. This is a documented gotcha in two independent sources.

9. Three-layer control stack: CLAUDE.md persuades (attention-sensitive, degrades with context dilution), settings.json filters statically, hooks enforce deterministically in a separate process. Confirmed [hookbalance] + [hookcollections] + [tddguard]. "If violating it would cause unrecoverable production damage, it belongs in a hook."

10. Over-blocking causes its own faults. The over-constraint paradox (Shah et al., arXiv 2603.06847) is flagged by [hookbalance] with MEDIUM confidence — one systematic study, needs corroboration. But Goodhart's Law metric gaming (delete the feature, mock the test output) is confirmed with HIGH confidence across [hookbalance] with multiple documented real examples.

CONTRADICTIONS / SOURCE DISAGREEMENTS

1. Event count: [hooksref] says 30 named events with some nuance on sub-types. [hookcollections] says 27. [clarifyhook] says 12 (likely the official docs count which hasn't been updated). [tddguard] says 12 (also from official docs). VERDICT: Official docs are stale. The 27-30 range from thepromptshelf.dev + v2.1.141+ sources is more likely accurate, but treat as MED confidence — the hookcollections source flags this caveat explicitly ("official docs still shows 12, community reference says 27").

2. Stop hook blocking: [hooksref] says "exit 2 OR JSON decision:block" for Stop events. [tddguard] says for Stop hooks specifically, "output JSON decision: block and exit 0, NOT exit 2." [hookbalance] implicitly agrees with exit 2 being valid. VERDICT: There is a genuine ambiguity here. The [tddguard] formulation (JSON + exit 0) appears to be the safer, more explicit pattern. The [hooksref] description of exit 2 on Stop meaning "Claude continues working" is consistent with using JSON output instead. Both may work; JSON + exit 0 is the recommended form.

3. prompt-type hook availability on UserPromptSubmit: [clarifyhook] explicitly states "prompt-type hook currently works ONLY on Stop and SubagentStop, NOT on UserPromptSubmit." [hooksref] lists prompt as a valid handler type for multiple events without this restriction. [tddguard] doesn't address this. VERDICT: [clarifyhook] appears to have a more current/tested finding. Flag as confirmed gap — prompt hooks on UserPromptSubmit may not work.

4. Alignment faking: [hookbalance] presents this with LOW-MED confidence for coding agents, notes Claude 4.x shows zero faking in replication experiments. The framing as a hooks concern is speculative. VERDICT: Corroborated that it's not a real operational concern for prompted coding agents with current Claude 4.x. Discard as a hooks design constraint.

GAPS (questions the probes didn't fully answer)

1. Exact event count: Official docs vs community refs disagree. No probe directly fetched the v2.1.141+ changelog to confirm 27 vs 30.

2. prompt-type hook on UserPromptSubmit: contradicted between sources; no probe directly tested this. GitHub #37559 (prompt hooks JSON errors) needs verification against current version.

3. TDAD pip package availability: [tddguard] notes "pip install tdad" from a March 2026 paper but flags it may not be on PyPI yet. Not verified.

4. Gitleaks v8.25+ allowlists rename: flagged by [tddguard] but not confirmed with live gitleaks binary. [allowlist] vs [[allowlists]] is a breaking change if real.

5. AskUserQuestion silent empty-answer bug (issue #29547) in plugin skills: flagged by [clarifyhook] but version-dependency unclear — not tested against current Claude Code version.

6. How many simultaneous hooks can run without degrading the turn latency beyond acceptable threshold for a 40-MCP setup. [hookbalance] gives raw numbers (80ms/hook, 10s for 4-hook chains) but no tested ceiling.

7. PreCompact blockability: [hooksref] lists PreCompact as blockable, with a warning about blocking auto-compaction on a near-full context causing errors. No probe explored the error behavior in depth.

MOST NOVEL / NON-OBVIOUS IDEAS WORTH CARRYING FORWARD

1. asyncRewake: true pattern for deferred enforcement. A background hook (e.g., post-commit linter, async security scan) can exit 2 after completing and wake Claude at its next idle moment with stderr as a system reminder. Enables zero-latency enforcement on the hot path with deferred consequence. Lightly documented, confirmed in [hooksref] + [hookcollections]. HIGH value for a power-user setup.

2. CLAUDE_ENV_FILE for dynamic environment. Hooks on SessionStart, Setup, CwdChanged, FileChanged can write export VAR=value lines to the file at $CLAUDE_ENV_FILE. Claude Code reads this and updates the session environment. Enables .envrc-style auto-sourcing without direnv. Very lightly documented ([hooksref] only). HIGH value for Windows workspace with many context-dependent env vars.

3. mvara-ai/precompact-hook: sends last 50 exchanges to a fresh Claude instance (zero prior context) to generate a structured recovery brief. The fresh-agent framing means full cognitive attention goes to summarization, not alongside growing history. Directly applicable to the user's compaction-survival problem. Confirmed in [hookcollections].

4. weft event-sourced state machine ([hookcollections]): append-only events.jsonl + projected state.json enforces workflow phase sequencing across three hooks (PreToolUse, PreCompact, Stop). Crash-recoverable by replaying the log. 191 tests, pure Python stdlib. Best found pattern for enforcing multi-step plan compliance without brittle marker files.

5. UA-Multi Intent Agent pattern (arXiv:2603.26233, [clarifyhook]): a dedicated Intent Agent continuously monitors conversation history for missing info and constrains the main agent to query when ambiguity is detected. 69.4% vs 61.2% resolve rate on underspecified SWE-bench tasks. Asking mid-task (43.4% of queries) is as valuable as pre-task asking (41.8%). Maps to a SubagentStart hook injecting intent-monitoring instructions.

6. TDAD test impact graph (arXiv:2603.17973, [tddguard]): builds an AST-derived source→test dependency map; tells agents exactly which tests to run for a changed file rather than running the full suite. 70% regression reduction. More importantly: naively adding TDD prompt instructions WITHOUT the test map INCREASED regressions (to 9.94% from 6.08% baseline) because procedural instructions consumed context budget needed for repo state. The lesson: agents need to know WHICH tests, not HOW to do TDD.

7. additionalContext must be factual statements, not imperative instructions. "The branch is main" works; "You must do X" triggers prompt-injection defenses and surfaces the text to the user. Confirmed [clarifyhook]. Applies to all hook context injection.

8. once: true only works in skill/agent frontmatter, silently ignored in settings.json. Confirmed [hooksref]. Easy trap when copying patterns from skills into settings files.

9. Semantic influence cannot be blocked by hooks (NeuroTaint, arXiv:2604.23374, [hookbalance]): taint propagates through the model's probabilistic reasoning, not just tool I/O. Even if hooks allowed a tool call, untrusted data that entered context can influence all subsequent calls invisibly. This is the irreducible 4% false-completion floor — multi-agent adversarial review is the only mitigation, not more hooks.

10. PostToolBatch event (confirmed [hooksref]): fires once after ALL parallel tool calls in a batch resolve, before the next model call. Blockable. Input contains the full array of tool calls and outputs. The correct event for cross-tool consistency checks (e.g., verify none of N parallel writes conflicted) — a use case that per-tool PostToolUse hooks cannot satisfy.

## CLUSTER: character
# CHARACTER CLUSTER BRIEF

## Cluster Members
- [inquisitive] — ask-vs-act, ambiguity detection, timing, MCP tool quality
- [tunnelvision] — goal drift, path drift, context dilution, anti-anchoring
- [proactive] — proactivity gating, cognitive load, suggestion surfacing
- [calibration] — uncertainty quantification, abstention, calibrated confidence
- [elicit] — requirement elicitation, EVPI, spec-first, MCP Elicitation protocol
- [metacog] — self-monitoring, reflection loops, stuck detection, memory
- [talkative] — communication discipline, notification budget, sycophancy, anti-echo-chamber

---

## STRONGEST CORROBORATED CONCLUSIONS

### 1. EVPI / Value of Information as the Universal Ask-Gate
**Sources:** [inquisitive] arXiv:2601.06407, [elicit] arXiv:2511.08798, [calibration] arXiv:2601.06407, [talkative] SAGE-Agent, [metacog] arXiv:2511.08798

All four probes independently converge on the same decision kernel: ask (or escalate, or clarify) only when `E[utility_gain_from_clarification] > cognitive_cost`. The SAGE-Agent operationalization (EVPI over tool parameter space, not free-form text) is cited by [inquisitive], [elicit], and [metacog] as the most principled formulation. The math is the same across all four. This is the most robustly corroborated single technique in the cluster.

**Carry forward:** Implement EVPI-gated clarification as the default ask-gate. Uncertainty lives in tool parameter space, not "I'm not sure" text.

### 2. Front-Load Clarification: Goal Clarity Collapses at 10% of Execution
**Sources:** [inquisitive] arXiv:2605.07937 (primary), [talkative] MAC/arXiv:2512.13154, [elicit] pre-execution phase design

[inquisitive] provides the hard empirical number: goal clarification value drops to baseline after the first 10% of execution. [talkative] independently validates that front-loading (ask-once before execution) yields +7.8pp task success and -25% turns vs. ask-as-you-go. [elicit] arrives at the same design prescription from a security angle (ASPI: mid-execution clarification amplifies injection risk 15-16x). Three independent reasons to front-load, zero reasons to ask mid-execution.

**Carry forward:** Hard gate — all ambiguity resolution must happen in a sandboxed pre-execution phase before any MCP tools fire.

### 3. Verbal Confidence Is Not a Control Signal
**Sources:** [calibration] arXiv:2601.07767 (decision-action gap), [metacog] semantic entropy/Zylos Research, [talkative] holistic trajectory calibration

Three probes independently establish that models verbalize calibrated-sounding uncertainty but almost never act on it (never abstain even under extreme penalties). The fix, across all three, is identical: build confidence assessment at the infrastructure/routing layer, not inside the model. UQLM / LM-Polygraph or AUQ dual-process are the tooling recommendations.

**Carry forward:** Route confidence gating to a pre-LLM classifier layer. Do not use "are you sure?" prompts as a safety mechanism.

### 4. Goals Must Be Externalized and Re-Retrieved
**Sources:** [tunnelvision] (StateAct, ReflAct, Factory.ai, Anthropic), [metacog] goal drift/arXiv:2505.02709, [talkative] CLAUDE.md anchor

Every source that studied long-horizon goal maintenance converges: a goal left passively in mid-context will be progressively deprioritized by the attention U-curve. Re-injecting the original goal verbatim every N turns, writing it to an external file (active-plan.md pattern), and using goal-state reflection framing ("what is the gap between current state and goal?" vs. "what should I do next?") all outperform "just put it in the system prompt once."

ReflAct's finding deserves special emphasis: replacing the ReAct backbone reasoning framing with goal-gap framing (+27.7%) beats layering any add-on module on top of standard ReAct.

**Carry forward:** `.beads/plans/active-plan.md` is correctly placed. Add a PreToolUse hook that re-injects the goal verbatim every 10 turns. ReflAct framing as the default reasoning backbone.

### 5. Approval Fatigue Renders Per-Action Prompts Counterproductive
**Sources:** [talkative] Anthropic auto-mode (93% approval rate), [metacog] max-turns hard limits, [proactive] PRISM false-alarm data (GPT-4o baseline >50% false alarms)

Anthropic's own production data shows 93% of permission prompts were rubber-stamped. [proactive] shows frontier models without PRISM have >50% false positive intervention rates. Both directions (too many approvals, too many suggestions) converge on the same outcome: users stop reading and the signal value collapses. Exception-based escalation is the consensus replacement.

**Carry forward:** Escalate only on 3+ consecutive denials or risk-threshold breach. Tier autonomy by domain risk, not globally.

### 6. 97% of MCP Tool Descriptions Have Quality Smells
**Sources:** [inquisitive] arXiv:2602.14878 (sole primary source, but flagged by two probes)

This is the structural root cause of over-asking in MCP-heavy environments. Fix descriptions first; then tune ask-rate. Corroborated directionally by [elicit]'s token-cost section (on-demand loading requires accurate descriptions to route correctly) and [metacog]'s KnowSelf finding (knowledge boundary confusion triggers unnecessary clarification).

**Carry forward:** Audit all 40 MCP server tool descriptions against the 6-component rubric before any behavioral tuning.

### 7. Sycophancy Is Structural, Not Promptable Away
**Sources:** [talkative] Silicon Mirror (85.7% reduction via generator-critic), [calibration] RLHF sycophancy finding, [metacog] A-MEM reconciliation

All three probes that touched sycophancy agree: RLHF trains agreement-seeking into weights. Prompt instructions to "be honest" are insufficient. The architectural fix is a generator-critic loop with explicit dissent mandate. Silicon Mirror achieves 85.7% relative reduction; without it, reported findings are shaped by perceived user preference.

**Carry forward:** Mandate a critic pass on every significant output before surfacing. This is the "peer review" principle from the user's MEMORY.md already implemented at the metaswarm level — the research confirms it is architecturally necessary, not just a preference.

---

## CONTRADICTIONS AND DISAGREEMENTS

### Contradiction 1: How Many Questions to Ask
[inquisitive] CLARITI says 41% fewer questions achieves same task success. [talkative] cites 62-100% ask rates by task difficulty from [elicit]'s data. These are not contradictory after closer reading — CLARITI optimizes question efficiency (fewer but better-selected questions), while the ask-rate percentages measure whether to ask at all (not how many). But a reader skimming could conflate them. The reconciliation: ask when EVPI justifies it (may be often on hard tasks), but use Shapley+answerability to select a single focused question, not a list.

### Contradiction 2: Frontier Model Behavior — Gemini Never Asks vs. Claude Sometimes Too Late
[inquisitive] reports Gemini 3 Flash never asks (0/100 sessions with ask_user tool available) while Claude Sonnet 4.5 asks at 50% trajectory depth (too late for goal clarification). These are not contradictory — they are opposite failure modes of the same axis. The implication: neither default behavior (never-ask nor late-ask) is correct; the system prompt and tooling design must impose the timing discipline that models do not self-generate.

### Contradiction 3: Cognitive Load of Proactivity
[proactive] (Precision Proactivity) says model-initiated task switching is the strongest predictor of performance decline, with extraneous cognitive load ~3x the effect of intrinsic complexity. [talkative] says post-commit proactive suggestions achieve 52% engagement. This is a context-dependent difference (notification during task vs. at task boundary) that both sources actually agree on — the disagreement is surface-level. The resolution is the timing rule: boundary-timed proactivity helps; mid-task proactivity harms.

---

## GAPS — QUESTIONS THE CLUSTER DID NOT ANSWER

**Gap 1: Compaction-specific clarification protocol.** Multiple sources note post-compaction context loss but none directly addresses how the agent should elicit from the human (vs. from memory) after compaction. [elicit] specifies "restore from plan file, do not re-elicit" but this is a design prescription, not an empirically validated protocol.

**Gap 2: Optimal notification budget for developer/power-user contexts.** The 3-5/day ceiling is extrapolated from consumer app research. There is no study of knowledge workers who explicitly opted into verbose agent output. The number could be 10-20 for power users; unknown.

**Gap 3: MCP Elicitation protocol adoption rates.** The MCP Elicitation spec (June 2025) is documented in [elicit] but no source reports how many of the 40+ MCP servers in a typical workspace have implemented it. The gap between spec availability and server adoption is uncharted.

**Gap 4: Cross-model calibration in a Claude + Codex + Antigravity setup.** [metacog] mentions CoE (Collaborative Entropy) for multi-model systems but it is a single paper at MED confidence. No empirical work on three-way heterogeneous model ensembles matching this exact stack.

**Gap 5: ASPI defenses.** [talkative] documents the 15-16x injection amplification during clarification but the paper offers no defenses. No other probe addressed this. The gap is open: what structural defense neutralizes this specific attack vector in an MCP-heavy workspace?

---

## MOST NOVEL / NON-OBVIOUS IDEAS WORTH CARRYING FORWARD

**Novel 1 (HIGH): The 10% trajectory cliff for goal clarification (arXiv:2605.07937)**
This is a sharp phase transition, not a gradual decay. After just 10% of a task's execution, goal clarification becomes literally worthless — not diminished, but baseline-equivalent. This is counterintuitive (you might expect gradual decay) and has an immediately actionable hard-stop: ask about goals in the first 1-2 actions of any plan, never later.

**Novel 2 (HIGH): Inherited drift via prefilled weak-agent trajectories (arXiv:2603.03258)**
Even drift-resistant models absorb drift when conditioned on a prior weaker agent's trajectory. Directly relevant to the Claude → subagent → subagent chain in metaswarm: each handoff is a drift injection risk. Mitigation: never pass a subagent's raw output as prefix context; pass only structured summaries with the original goal re-anchored at the top.

**Novel 3 (HIGH): First-person commitment syntax shifts reasoning stance (arXiv:2510.10013)**
The per-step syntax of how an agent reasons (first-person "I will" vs. third-person conditional) measurably shifts goal persistence and delays safety checkpoints from step 3 to step 9. Use conditional/exploratory framing in agent prompts; avoid imperative commitment framing until after the plan is validated.

**Novel 4 (HIGH): ASPI — clarification questions amplify prompt injection 15-16x (arXiv:2605.17324)**
Entirely overlooked in the other probes. During mid-execution clarification, the trust boundary between user instructions and MCP-retrieved content collapses. This is a severe, unintuitive security consequence of a commonly praised UX behavior (proactive clarification). The workspace-specific implication: isolate pre-execution elicitation from MCP tool invocations at the protocol level.

**Novel 5 (MED): TRIAGE finding — agents cannot reliably self-schedule compute (arXiv:2605.13414)**
Extended reasoning models detect fewer than 13% of unsolvable problems, and triage quality shows no consistent improvement with parameter count. Agents that schedule their own subtasks are worse than random at predicting which ones they will succeed on. External orchestration (metaswarm scheduler) is empirically superior to self-scheduled allocation — a vindication of the architecture the user already has, from a direction no one in this domain usually argues.

**Novel 6 (MED): AUQ "Delusion Gap" (arXiv:2601.15703)**
System 2 reflection can increase confidence in incorrect answers more than correct ones (14.3% correction vs. 3.6% regression). Pure confidence maximization is the wrong objective in a self-reflection loop; consistency across N samples + grounding in external signals is more reliable. This is a subtle but important failure mode for anyone naively implementing "retry with higher confidence" loops.

**Novel 7 (MED): Idle-time prefetch for anticipatory suggestion preparation (arXiv:2605.25971)**
Running prefetch during human thinking/idle time — forecasting upcoming queries and resolving knowledge gaps before the user asks — achieves 14.8% fewer turns, 11.7% lower user effort, 28.1% lower hallucination rates on ProActEval. For a 40-MCP workspace with tool-loading latency, pre-warming the top-N likely next tools during idle time has both a UX and accuracy payoff.

---

## SYNTHESIS JUDGMENT

The cluster has high internal consistency. The core architecture that emerges from cross-probe corroboration:

- **Pre-execution phase** (sandboxed, before any MCPs fire): EVPI-gated clarification + spec generation + ambiguity triage → stores to active-plan.md
- **Execution phase**: Goal re-injection every N turns via hook; EVPI threshold on mid-run questions (only input-type, not goal-type); per-step confidence tracking (AUQ triplets to basic-memory); stuck-loop guard (deque + semantic similarity)
- **Escalation layer**: Exception-based only; escalation package bundles what-tried + why-uncertain + ranked-options; daily interrupt budget self-enforced
- **Reporting layer**: Generator-critic pass before surfacing findings; three-tier progressive disclosure; trajectoral confidence (not per-output); independent parallel rounds before cross-agent visibility
- **Memory layer**: A-MEM-style reconciliation on every write; MC² outer-loop consolidation per batch; inherited drift prevention on subagent handoffs

## CLUSTER: selflearning
CLUSTER BRIEF — "selflearning" probe cross-check
Corroborator pass | 2026-06-10

---

STRONGLY CORROBORATED (3-4 sources agree, HIGH confidence)

1. Self-reflection without external signal degrades, not improves, performance.
All four probes converge on this as the single most important finding. [reflexion] labels it "degeneration-of-thought" (MAR paper). [mistakes] cites the TACL paper ("When Can LLMs Actually Correct Their Own Mistakes?") as the definitive empirical study. [instructfollow] frames it as the core reason hooks must enforce critical rules, not CLAUDE.md. [evals] folds it in as the "verifiability constraint." No disagreement anywhere. Confirmed: a solo actor/evaluator/reflector loop running the same model produces predominantly confirmatory, not corrective, output. The correctness of the final answer is largely determined by the first attempt.

2. The write path is the gap, not the read path.
[reflexion], [mistakes], and [instructfollow] all reach this conclusion independently. Most systems recall memories reasonably well but write raw logs instead of distilled heuristics, abstract principles, or structured lessons. [evals] corroborates via the retrieval/utilization probe: "retrieval failures dominate (11-46% of errors); utilization failures are small (4-8%)" — meaning the retrieval corpus itself is the bottleneck, which circles back to write quality. The ERL finding (failure heuristics outperform success trajectories) appears in both [reflexion] and [mistakes] from different papers (arXiv:2603.24639 vs. arXiv:2603.10600), adding weight.

3. Structural critic diversity (not stylistic role-labeling) is required to break the echo chamber.
[reflexion] documents the MAR architecture (Evidence Policy × Exploration Drive × Specification Strictness axes). [mistakes] independently recommends cross-model multi-judge (AgentHER MJ-X pattern, arXiv:2603.21357) as the most robust anti-echo-chamber mechanism, reducing label noise from 5.9% to 2.3%. [instructfollow] calls out the same failure: "A 'security reviewer' and a 'code reviewer' who both reason by confirming add no diversity." [evals] adds Agent-as-Judge data: single LLM judge disagrees with human majority ~31% of the time vs. ~0.3% for agent judges. Consistent across all four probes.

4. Rule/instruction compliance degrades with count; hooks are the only 100%-reliable enforcement layer.
[instructfollow] has the deepest coverage here (near-linear decay above ~150 rules, context position effects, the `--append-system-prompt` trick). [reflexion] does not contradict this but doesn't directly address it. [mistakes] corroborates indirectly: "Never auto-delete notes; mark as expired and let human decide" — implies passive accumulation is harmful. [evals] doesn't cover CLAUDE.md limits directly but validates the principle via Harness-Bench (configuration is co-determinant of capability). No contradictions. Hooks-first is the consensus.

5. Memory architecture, not base model scale, drives memory retention performance.
[mistakes] cites AMA-Bench: architecture variance = 0.45, model scaling variance = 0.038. [evals] independently cites the same finding from AMA-Bench and extends it: "memory system architecture, not base model scale, drives performance." [reflexion] and [instructfollow] are consistent (they prescribe architectural changes, not model upgrades). Full corroboration.

6. Skill shadowing is real and retrieval quality (not context length) is the fix.
[skillacq] documents it explicitly (arXiv:2605.24050, up to 21% degradation from wrong skill selection; context overhead near zero). [evals] corroborates from the SkillRouter paper and Harness-Bench angle. [reflexion] alludes to context pollution from ExpeL (loading entire insight list) fixed by ERL's selective retrieval, which is the same structural problem. Not directly contradicted anywhere.

---

CONTRADICTIONS / TENSIONS

1. Self-generated skills: zero benefit vs. +19pp over human skills.
[skillacq] reports two findings from different papers that point in opposite directions:
- SkillsBench (arXiv:2602.12670): 1-shot self-generated skills provide zero average benefit on average.
- MUSE-Autoskill (arXiv:2605.27366): multi-shot evaluate-refine loop produces skills 19pp better than human-authored.
These are not actually contradictions — they differ in the generation process (one-shot vs. multi-shot with test-gating). But the cluster brief must flag that "self-generated skills are better" is only true with the full evaluate-refine-register loop. One-shot generation is worse than nothing. This matters enormously for implementation — do not treat skill auto-generation as plug-and-play.

2. Failure trajectories: store or not?
[mistakes] (ReMe paper): "Store only successful trajectories at runtime refinement; failed trajectories provide context but aren't directly stored unless analyzed." [reflexion] and [mistakes] (ERL paper): "Failure-derived heuristics outperform success-derived ones." The resolution is level-of-abstraction: raw failed trajectories should not be stored verbatim; distilled failure heuristics (what went wrong and why, abstracted) should be stored and preferentially. This is a distintion the raw probe findings blur. Corroborator call: both are right at different levels of abstraction.

3. Memory write triggers: PostTask hook (active) vs. Claude's organic auto-memory (passive).
[instructfollow] recommends adding a Stop hook to actively write structured 3-tip session summaries. [reflexion] recommends a PostTask Reflection subagent. Claude Code's auto-memory (also documented in [instructfollow]) does this passively without hooks, but the [mistakes] probe notes it lacks confidence scoring and provenance. These are not contradictions but genuinely different design choices with different reliability profiles. The probes do not resolve which is preferable — this is an open design question.

---

GAPS (not answered by any probe)

1. Cross-session memory coherence after compaction is not formally benchmarked. All four probes acknowledge this. MemoryAgentBench and AMA-Bench test within-session or controlled multi-turn; none test the specific "post-compaction retrieval from basic-memory MCP" scenario that is the actual pain point. No answer exists in the literature.

2. Temporal decay / TTL implementation for basic-memory specifically. [mistakes] recommends Weibull-based decay (SSGM) and a 30-day half-life. But how to implement this on top of basic-memory's markdown+vector architecture (which has no built-in TTL) is not addressed by any probe. Only manual metadata field approach suggested.

3. Hook-based enforcement vs. RIMRULE symbolic rules: no comparison. [instructfollow] covers hooks and RIMRULE independently but does not address when symbolic rule injection (inference-time) is preferable to hook enforcement (pre-execution). The tradeoff space is unexplored.

4. Stopping condition for self-refine loops. [reflexion] flags this explicitly as an open problem. No probe answers it. Current practice: max 3-5 iterations + external verifier gate. No principled formula.

5. Skill library size at which GoS-style dependency retrieval becomes necessary vs. sufficient. [skillacq] shows skill shadowing starts at some unspecified scale; [evals] mentions SkillRouter but does not give a crossover threshold. Practically unknown.

---

NOVEL / NON-OBVIOUS IDEAS WORTH CARRYING FORWARD

Ranked by novelty × immediate actionability for this workspace:

A. Per-skill .memory.md files (MUSE-Autoskill, arXiv:2605.27366).
Each skill directory gets a MEMORY.md documenting known failure modes, edge cases, input quirks. Loads alongside SKILL.md. Zero code changes to Claude Code required. Extremely high ROI. Not obvious because people think of memory as session-level, not skill-level.

B. "Dual-Goal + Think-in-Opposites" prompt additions (Failing to Falsify, arXiv:2604.02485).
Two sentences added to every self-critique or review prompt: (1) "Your goal is both to confirm and falsify your current hypothesis"; (2) "Generate the strongest possible argument against your conclusion before finalizing." Free. Reduces confirmation bias by ~14pp. Directly applicable to all existing adversarial review agents.

C. DeltaMem's state-centric PostTask framing.
Instead of asking "what note should I write?", ask "what should my memory state look like after this session?" and write to close the delta. Subtle reframe that reduces over-writing and improves coherence. Not a tool change — a prompting discipline change.

D. SSGM append-only ledger + TMS contradiction check (arXiv:2603.11768).
Before writing any lesson to the active store, check it against protected core facts. Append-only raw trajectory log is the ground truth; derived lessons in the active vault are reconciled periodically against the ledger. This is a correctness architecture that basic-memory currently lacks entirely.

E. FinCon's "conceptual belief" abstraction level (arXiv:2407.06567).
Instead of writing tool-use transcripts, abstract to compact beliefs about when each skill/MCP works and when it fails. Example: "IDA MCP requires binary to be opened first via select_binary; cold calls return empty without error." These are the right granularity for procedural memory — more specific than CLAUDE.md rules, less noisy than raw logs.

F. Harness-Bench implication: build your own eval suite from real production tasks, not generic benchmarks.
[evals] is the only probe that frames this explicitly, but it follows from multiple findings. The 23.8pp gap from harness configuration means any benchmark score from a generic eval cannot be imputed to your specific 40-MCP setup. This is a non-obvious operational conclusion, not just a research note.

G. Cross-model skill transfer (SkillWeaver finding, arXiv:2504.07079).
Strong-model-authored skills (Opus) transferred to weaker agents (Haiku/Sonnet) with +54.3% improvement. One-time Opus authoring session compounds across all future invocations. This is an economic argument for spending Opus tokens on skill authoring explicitly, not just using whatever model is running.

H. Negative-control test rows in skill routing regression datasets.
The OpenAI Codex evals recipe ([evals] probe) calls out: prompts that should NOT trigger a skill are as important as positive tests. The most common false-positive failure mode is over-broad description fields. Corroborated by [skillacq]'s skill shadowing finding. Actionable: add 3-5 negative-control rows per skill to your regression CSV.

---

SUMMARY VERDICT

The four probes are highly consistent on fundamentals and complementary on implementation details. No significant contradictions exist except the one-shot vs. multi-shot skill generation tension (resolved by abstraction level). The biggest single gap in the workspace as described is the write discipline: sessions produce raw logs or no memory artifacts at all, rather than structured heuristics with provenance and confidence metadata. The second biggest gap is retrieval quality into the basic-memory vault, not the vault's capacity. Fixing both requires the same thing: a structured PostTask/Stop hook that writes in a defined schema (3-tip taxonomy or conceptual belief format) with explicit metadata fields (confidence, source, verified_by, learned_date).

## CLUSTER: orchestration
ORCHESTRATION CLUSTER BRIEF

---

STRONGEST CORROBORATED CONCLUSIONS (3+ sources agree)

1. Multi-agent wins by getting MORE TOTAL COMPUTE, not by architectural superiority.
Confirmed by arXiv:2604.02460 (single-agent matches MAS under equal token budgets, 3 model families), arXiv:2503.13577 (orchestration only justified when agents have measurable differentials), and Anthropic's own framing ("tasks where value is high enough to pay for increased performance"). The 15x token cost multiplier is confirmed from Anthropic's primary source - budget it as a hard constraint, not a footnote.

2. Routing and sequencing must live in CODE; reasoning must live in LLM.
Confirmed across: [workflowdet] (core thesis, multiple frameworks), [multiagent] (AdaptOrch topology routing is O(|V|+|E|) algorithmic), [scaleeffort] (in-context procedural beats LangGraph 1.2-1.7x fewer LLM calls), ReliabilityBench (ReAct beats Reflexion under production stress). The 17.2x error amplification (Google DeepMind, Dec 2025) in unstructured networks is the empirical nail in the coffin for fully-dynamic routing.

3. Practical sweet spot is 3 diverse (not homogeneous) agents.
Confirmed by: [council] (Self-MoA: quality > diversity, ICLR 2025 Spotlight), [scaleeffort] (O(n²) transaction cost scaling, Coasian boundary, diversity > count paper), [agentteams] (addyosmani: 3-5 teammates, 5-6 tasks each), [multiagent] (coordination overhead grows superlinearly beyond 3-4). Heterogeneous models from different training lineages beat same-model ensembles for hallucination/bias; same-model self-consistency beats mixed-model MoA for accuracy tasks. The resolution: for accuracy, use Self-MoA (same model, multiple samples); for hallucination/bias reduction, use heterogeneous council.

4. Confidence-gating is the highest-ROI efficiency mechanism.
Confirmed by: [council] (DOWN achieves 6x efficiency by debating only when agent confidence is below threshold), [scaleeffort] (TrACE: inter-rollout agreement as free early-stop, zero retraining; Calibrate-Then-Act two-phase; Difficulty-Adaptive SC allocates samples by difficulty), [multiagent] (DAAO self-adjusting feedback loop). The pattern: measure confidence first, skip deliberation when already high.

5. Style bias dominates LLM-as-judge (0.76-0.92 coefficient); cross-model panel judging mitigates it.
Confirmed across multiple independent [council] sources. Self-evaluation inflates same-model outputs 5-15%. Fine-tuned judges generalize poorly cross-task. Practical fix: cross-model panel + style-debiased rubric.

6. Context isolation is architecturally hard - the only parent→subagent channel is the prompt string.
Confirmed by [multiagent] (official SDK docs) and [agentteams] (official agent-teams docs). Everything the subagent needs must be in the launch prompt. This is the #1 handoff discipline failure point.

7. Worktrees isolate git index but NOT runtime resources (databases, ports, env vars, external APIs).
Confirmed by [agentteams] official docs and gptfrontier.com. The most common misconception. Fix: ephemeral Docker containers per worktree named `db-$WORKTREE_NAME`, `.env.agent.template` with dynamic port substitution in WorktreeCreate hook.

8. Communication tax (rebroadcasting full context) is the dominant waste vector in MAS.
Confirmed by [scaleeffort] (53.9% of tokens are input/context rebroadcast in SWE systems) and [multiagent] (AGENTTAXO communication overhead framing). AgentPrune (ICLR 2025) achieves 28-72% token reduction via one-shot message graph pruning - deployable today.

---

CONTRADICTIONS / WHERE SOURCES DISAGREE

1. Cross-model diversity: helps or hurts?
[council] Self-MoA (ICLR 2025): mixing weaker diverse models hurts vs same-model ensemble. ReConcile (ACL 2024): cross-model diversity is "critical to superior performance." Resolution: ReConcile uses confidence-weighted voting and domain-specialized models (task-model alignment, not raw diversity). Self-MoA uses uniform aggregation. These findings are compatible when understood correctly: diversity from task-relevant specialization helps; diversity from weaker generalist models hurts. Practical rule: include a diverse model only if it has a measurable advantage on the specific subtask.

2. The Reasoning Trap DPI bound vs. debate empirical gains.
[council] arXiv:2605.01704 (May 2026) proves via Data Processing Inequality that closed-system debate cannot increase mutual information between evidence and output - SFS drops 43% with standard debate, 98.5% with majority-vote MAD. Yet ReConcile and Du et al. show real factuality gains from debate. Resolution: the DPI bound applies to CLOSED systems (no external evidence injection). Tool-augmented debate (MCPs called between rounds) breaks the bound - agents accessing external evidence each round escape the information decay. For your 40-MCP workspace, tool-augmented debate is the correct design, not pure peer-output recycling.

3. Multi-agent vs single-agent on procedural tasks.
[scaleeffort] finds in-context self-orchestration beats LangGraph on 55-node procedural workflows (0.5-11.5% vs 9-24% failure rate). [agentteams] documents full multi-agent teams for similar complexity. Resolution: the in-context finding applies to fixed-topology procedural tasks with known workflows. Multi-agent is appropriate when topology is genuinely unknown at design time or when parallel execution provides wall-clock speedup. Test type of task first.

---

GAPS (what the raw findings did not answer)

1. Windows-specific tooling constraints. [agentteams] explicitly flags that split-pane teammate mode requires tmux/iTerm2 (unavailable on Windows Terminal/VS Code). No source addressed the Windows + Claude Code + Codex CLI coordination stack specifically. The workaround (WSL2 + tmux, or Claude Code desktop app with per-session worktrees) is mentioned but not benchmarked.

2. Skill and MCP auto-discovery routing. None of the probes addressed the specific problem of a model auto-routing to the correct skill/MCP from hundreds of options at low token cost. [multiagent] notes tool description quality is the #1 lever (40% completion-time improvement from rewriting descriptions) and Anthropic built a tool-testing agent for their MCP catalog - but the auto-invocation problem for 100s of skills remains unaddressed. This is a gap to fill with a dedicated probe or the tool-testing agent pattern.

3. Post-compaction echo chamber prevention in practice. [multiagent] covers the theory (distilled memory, basic-memory patterns). [agentteams] gives the MESI Invalid state framing (stale in-context = Invalid, must refetch). But concrete implementation recipes for the specific stack (basic-memory MCP + .beads/ files + bd prime recovery) were not tested end-to-end.

4. Cost data for the specific model combination (Claude Sonnet 4.6 + Codex + Antigravity). All cost figures are for Anthropic's internal system or paper-specific configurations. The 15x applies to Opus orchestrator + Sonnet workers; the actual multiplier for Sonnet-only or mixed-provider setups is unquantified.

5. DACS production adoption timeline. [multiagent] identifies DACS (arXiv:2604.07911) as the most promising context efficiency technique (3.53x, 90%+ steering accuracy) but notes it is not yet in the SDK. No source addressed when/if it will be.

---

NOVEL / NON-OBVIOUS IDEAS WORTH CARRYING FORWARD

High priority (corroborated or theoretically grounded, directly actionable):

A. Confidence-gated council as default routing pattern. The combination of DOWN (debate only when confidence < threshold) + CISC/TrACE (self-consistency only when needed) + single-agent for high-confidence queries gives an estimated 70-85% average cost reduction vs always-on council. This is the correct default for the workspace, not always-on multi-agent.

B. Tool-augmented debate escapes the DPI trap. The Reasoning Trap finding (arXiv:2605.01704) is the most theoretically important novel finding in this cluster. Peer-output recycling degrades evidence-faithfulness monotonically. MCP calls injected between debate rounds break the Markov chain and can recover evidence grounding. Design adversarial review agents to call verification tools between rounds, not just read each other's output.

C. Embed the 3-tier complexity rubric in every orchestrator system prompt. Anthropic's production formula verbatim: simple query = 1 agent, 3-10 tool calls; comparison = 2-4 agents, 10-15 calls; complex research = 10+ agents. The orchestrator classifies BEFORE spawning. This single change prevents most over-provisioning.

D. MESI Invalid state as the mental model for post-compaction behavior. After any context compaction, an agent's in-context memory of shared project state is formally in the Invalid state - it must fetch from the ledger (basic-memory / .beads/) before acting. The `bd prime --work-type recovery` pattern already implements this correctly; the MESI framing makes it diagnosable when it fails.

E. instruction fade-out countermeasure via PreToolUse hooks. OpenDev paper names the mechanism: long-running agents stop following CLAUDE.md rules mid-session because the rules fade from effective attention. Fix: PreToolUse hooks that re-inject critical rules as a preamble to every write operation. Directly implementable today.

F. AgentPrune for immediate token reduction. ICLR 2025, code available (github.com/yanweiyue/AgentPrune), 28-72% token reduction on shared-context multi-agent conversations via one-shot message graph pruning. No retraining. The closest to a free lunch in this cluster.

Medium priority (novel, MED confidence, worth prototyping):

G. Token-level Round-Robin to harden adversarial review. Under majority corruption (3/5 bad agents), standard voting collapses to 0.8-11% accuracy; token-level RR maintains 59-89%. For your adversarial review council where a sycophantic or drifted agent could dominate, interleaved generation into shared autoregressive context is the robustness mechanism.

H. Compiled AI break-even at ~17 runs. For any workflow running >20 times (your recurring metaswarm phases), consider a compile-once approach where the orchestration structure is code-generated once and then runs deterministically. 57x token reduction at 1,000 transactions.

I. DAAO self-adjusting difficulty feedback loop. The online curriculum (reduce difficulty estimate on success, increase on failure) continuously improves routing efficiency without retraining. If building a custom orchestrator, this is the highest-leverage single addition.

J. Phase-scoped visibility modes (Full/Focused/Blind) from TheBotCompany. Controlling what each worker SEES (not just what files it can touch) prevents semantic drift and duplicate work - a different axis of isolation from worktrees. Implementable via prompt construction in the orchestrator.

Defer/corroborate first:

K. DACS 3.53x context efficiency (arXiv:2604.07911) - not yet in SDK, architecture sound but unvalidated in production.
L. 11x distilled memory compression (arXiv:2603.13017) - single paper, not yet replicated; use vector retrieval (not BM25) if adopted.
M. Token Coherence MESI 84-95% token savings - simulation only, no real LLM experiments yet.

## CLUSTER: sota
SOTA RESEARCH CLUSTER BRIEF — CORROBORATOR REPORT

## Strongest Corroborated Conclusions (Multiple Sources Agree)

**C1. Tool count degradation is real and severe, with a hard empirical threshold.**
All four probes [harnesses, toolmin, crossai, novel2026] independently converge: 30–50 tools is the practical ceiling before LLM selection accuracy degrades significantly. The toolmin probe quantifies the cliff: 84–95% accuracy at ~50 tools → 0–20% at ~740 tools. The harnesses probe confirms via Anthropic's own numbers. The crossai probe confirms via the 99.6% token reduction finding for semantic retrieval at K=3–5. This is the most robustly multi-sourced finding in the cluster.

**C2. Anthropic's Tool Search Tool / `defer_loading` is the production solution for 40+ MCP servers.**
Three probes cite this independently [harnesses, toolmin, crossai]: 85% token reduction, Opus 4 accuracy +25pp (49%→74%), Opus 4.5 +8.6pp (79.5%→88.1%). Beta: `advanced-tool-use-2025-11-20`. Claude Code setting: `ENABLE_TOOL_SEARCH=auto`. Keep 3–5 tools always loaded; defer all others. This is first-party data, consistent across sources.

**C3. AGENTS.md is stable, cross-tool, Linux Foundation-governed infrastructure.**
Confirmed by crossai (primary research) and corroborated by harnesses: 60,000+ projects, 20+ tools, AAIF governance (Anthropic + OpenAI + Block + Google + Microsoft). The Claude Code workaround (`@AGENTS.md` import at top of CLAUDE.md) is explicitly documented as Pattern 0 and is the only non-admin solution on Windows. Optimal file size: 100–150 lines (crossai cites arXiv:2601.20404); the harnesses probe confirms the 200-line hard limit in Claude Code itself.

**C4. MCP-Zero active tool discovery (arXiv:2506.01056) is the strongest published large-scale result.**
Both harnesses and novel2026 cite this independently with identical numbers: 98% token reduction, accurate selection from 2,797 tools across 308 servers. The paradigm inversion (agent declares what it needs rather than selecting from a menu) is consistent across both probes. Both flag it as novel requiring corroboration; it is not yet a released library.

**C5. Durable memory requires an explicit multi-layer architecture, not prompting alone.**
All four probes cite variants of the same four-layer model (working/episodic/semantic/procedural). The compaction risk — that subdirectory CLAUDE.md files are NOT re-injected automatically — is confirmed by claudebest (official docs, high confidence). The PreCompact hook as the intervention point is confirmed by both claudebest and harnesses independently.

**C6. Tool description quality has outsized impact and is currently poor.**
Two independent probes confirm this [toolmin via arXiv:2505.18135 (10x selection shift from rewording), novel2026 via arXiv:2602.14878 (97.1% defect rate across 856 tools)]. The toolmin probe adds: description wording causes 10x shifts in selection. The novel2026 probe adds: full augmentation increases execution steps 67% (use component ablation, not full rewrite). Both probes agree: audit and fix purpose-clarity and constraint fields only.

**C7. Compaction destroys the KV cache — the real cost is not the summarization call.**
statusline probe calculates: a 125K-token compaction = ~$0.40 summarization + loss of 21 cached turns. The harnesses probe confirms transformer attention is n²-degrading, not a cliff. Both independently recommend delaying compaction as long as safe. No harness currently compensates for this.

**C8. Context drift kills more agents than context exhaustion.**
statusline probe: 65% of 2025 enterprise failures attributed to drift, not exhaustion. novel2026 (arXiv:2601.04170) confirms behavioral degradation over extended interactions. Detection signals (from statusline): goal wording shifts, re-reading already-processed content, technical detail corruption. No production harness currently monitors for this automatically.

**C9. CLAUDE.md is advisory; hooks are the only enforcement layer.**
claudebest (official docs, high confidence) is unambiguous: "An instruction like 'never edit .env' in CLAUDE.md is a request, not a guarantee. A PreToolUse hook that blocks the edit is enforcement." This is the most important architectural clarification for your setup. Any "must happen" rule needs a hook, not CLAUDE.md wording.

**C10. Phase-gated tool access via state machines eliminates the largest category of degenerate actions.**
harnesses probe (statewright): local models 2/10 → 10/10 by shrinking visible tool space per phase. The mechanism is simple: destructive tools cannot be called in a read-only planning state because they don't exist in that phase. This is structural prevention, not prompting. Both harnesses and toolmin probes frame this as the highest-leverage single anti-degenerate-action technique.

---

## Contradictions and Disagreements

**Contradiction 1: AGENTS.md optimal length.**
crossai cites arXiv:2601.20404 finding 100–150 lines as optimal, with gains reversing above ~150 lines. harnesses cites a different source (morphllm.com / Princeton benchmark) finding improvements at 20–30 lines. These are not reconciled. The 100–150 line figure comes from an adversarially reviewed paper; the 20–30 line guidance appears to be practitioner advice. Both agree that longer is not better; the disagreement is whether 30 or 150 is the right ceiling. Treat 100 lines as a soft upper bound until tested on your specific skill-heavy setup.

**Contradiction 2: Tool Search Tool native Claude Code support.**
harnesses states the Tool Search Tool is available and enabled via the beta header. crossai explicitly notes "Claude Code support pending (issue #12836)" as of research date. This is a genuine status uncertainty — the feature may be available via the API but not yet surfaced as a first-class Claude Code CLI feature. Verify current status before building on it.

**Contradiction 3: MUSE-Autoskill status.**
harnesses rates confidence LOW (working paper). novel2026 does not separately cite MUSE-Autoskill but cites the companion EvoSkill work (arXiv:2603.02766) as more mature. The ByteRover/EvoSkill pair from novel2026 appears more production-ready than MUSE-Autoskill from harnesses. Do not build on MUSE-Autoskill until a release exists.

**Contradiction 4: headroom and context-mode MCP reliability.**
harnesses claims "100% answer accuracy" for headroom and "315 KB → 5.4 KB" for context-mode. The statusline and novel2026 probes do not corroborate these specific tools at all. Both are small open-source projects with limited production reports. The "100% accuracy" claim specifically lacks verification. Treat as promising but unvalidated.

---

## Gaps (Questions Not Answered)

**Gap 1: Antigravity-specific AGENTS.md and MCP config support.**
crossai lists Antigravity as a target for the `amtiYo/agents` sync tool but does not independently verify Antigravity's actual config file paths, schema, or AGENTS.md discovery logic. None of the four probes covers Antigravity's native behavior in depth.

**Gap 2: Windows-specific hook behavior and ConPTY issues.**
claudebest covers hooks comprehensively but does not address Windows-specific reliability issues (shell quoting, ConPTY interaction, PowerShell vs cmd). The statusline probe notes PowerShell support is native but does not explore hook reliability on Windows in detail.

**Gap 3: Skill auto-invocation failure analysis for 100s-of-skills setups.**
The claudebest probe confirms the 1,536-character description stub limit and flags overlap as the failure mode. None of the probes provides empirical data on how skill auto-invocation degrades as skill count scales past 50–100. The SkillRouter finding (arXiv:2603.22455) — skill body text is the primary routing signal — is from crossai alone, not corroborated elsewhere in the cluster.

**Gap 4: Cost of the EFC monitoring layer itself.**
novel2026 presents EFC (arXiv:2605.29682) as the new scaling law but does not address what it costs to instrument feedback quality tracking in a real harness. The monitoring overhead for a 40-server / 100s-of-skills setup is unknown.

**Gap 5: MetaMCP gateway production reliability.**
crossai flags MetaMCP (metatool-ai/metamcp) as a potential solution for eliminating per-tool config churn across 40 servers. No other probe covers this, and there are no production reliability numbers. The Docker dependency and stdio-bridging latency are noted but not benchmarked.

**Gap 6: Rate limit behavior under multi-agent parallel sessions.**
statusline probe surfaces rate limit fields in the Claude Code JSON schema but no probe covers what happens when Claude Code + Codex + Antigravity are running simultaneously, contending for the same user-level quota.

---

## Most Novel / Non-Obvious Ideas Worth Carrying Forward

**N1. EFC as the design target, not token count (arXiv:2605.29682).**
R²=0.99 vs R²=0.33 for raw tokens. Improving feedback quality raised success from 27% to 90% at fixed token budget. This reframes the entire optimization problem: the right question is not "how many tokens am I using?" but "is each piece of feedback actually changing a downstream decision?" Implement as a redundancy filter at the orchestrator layer — if the same observation has been returned N times without affecting a decision, suppress it. Source: novel2026 (not in other probes — needs corroboration).

**N2. ByteRover's zero-infrastructure Context Tree (arXiv:2604.01599).**
96.1% LoCoMo with pure markdown files. The Adaptive Knowledge Lifecycle scoring layer (importance, maturity tier, recency decay) is layerable directly onto your existing `basic-memory` MCP without infrastructure changes. This is a direct upgrade path, not a replacement. Source: novel2026 alone — novel, deserves corroboration.

**N3. RCA 0.0% sycophancy at inference time (arXiv:2601.03263).**
The reasoning-trace causality check (conclusion must be causally derived from stated steps, not post-hoc rationalization of an external hint) achieves zero sycophancy without ground truth. The companion Silicon Mirror paper (arXiv:2604.00478) achieves 1.4% residual via independent judge. Both are from novel2026 only. The "inverse scaling" finding — sycophancy increases with model capability on hard tasks — is the most surprising implication: your strongest model is most at risk on your hardest tasks, and outcome-only evaluation will miss it.

**N4. Gemini CLI's 2-pass self-critique compaction probe.**
statusline probe: only harness that validates compaction quality by having a second model pass ask "did you miss anything?" Not yet in Claude Code. Replicable as a PostCompact hook: spawn a fast model, give it only the compaction summary, ask it to identify what critical technical details (variable names, file paths, error codes) are missing. Cost: one additional cheap API call per compaction.

**N5. Tool overlap is as harmful as tool count, independently (ToolScope, arXiv:2510.20036).**
+34–38% accuracy loss from semantic overlap alone, even at small tool counts. Your 40 MCP servers almost certainly have overlapping search, list, and get operations. The ToolScope merger (LLM-based semantic overlap detection → unified interface with parameterized dispatch) is the fix, with 95.4% merge correctness and 98.5–99.9% token reduction. Source: toolmin alone — corroborated by the general principle in harnesses and crossai but not the specific numbers.

**N6. The compaction-destroys-KV-cache asymmetry.**
statusline probe flags this; no other probe covers it. The real cost of compaction is not the ~$0.40 summarization call but the loss of cached tokens on all subsequent turns. A harness that delays compaction to 92% (vs triggering at 70%) and uses targeted /compact Focus commands to preserve hot tokens will see substantially lower bills than one that compacts eagerly. This is invisible to token-count monitoring alone.

**N7. SKILL.md public registry supply-chain attacks (arXiv:2605.11418).**
86% success rate for adversarial embeddings surfacing malicious skills. 36.5–100% evasion of governance blockers. This is from novel2026 only but the threat model is obvious in retrospect: the same embedding-based auto-discovery that makes the registry useful makes it exploitable. Maintain a local allowlist of vetted skills; do not auto-promote from public registries. Immediate action item.

**N8. History-aware tool routing via ACE-Router (arXiv:2601.08276).**
Both harnesses and crossai mention routing; only novel2026 covers the history-aware variant (conversation trajectory as a routing signal, not just the current query). For your multi-session setup where tool usage follows predictable sequential patterns (the AutoTool "usage inertia" observation), a lightweight routing model that reads prior tool choices would outperform stateless semantic retrieval. Research-grade but the training approach (random-walk on candidate graph + mutation to synthesize training data) is concrete enough to implement.

---

## Summary Verdict for the Agentic Workspace Design

The cluster agrees on the core stack: defer all but 3–5 tools, add semantic retrieval for the rest, gate tools by phase (statewright-style), use path-scoped CLAUDE.md rules not a monolithic file, run hooks as the enforcement layer (not CLAUDE.md text), maintain an explicit multi-layer memory with PreCompact snapshot, and monitor context drift not just context exhaustion.

The non-obvious advances worth prioritizing: EFC-aware feedback filtering (N1), ByteRover AKL scoring on top of basic-memory (N2), sycophancy detection via independent judge (N3/N4), ToolScope-style overlap deduplication before count reduction (N5), and a SKILL.md supply-chain allowlist (N7).