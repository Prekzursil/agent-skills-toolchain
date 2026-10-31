The two notes the contrarian leaned on (`harness_trim` and `bc_fsm_redesign`) are already summarized verbatim in my MEMORY.md system context — the trim cut every-turn load 64% via path-scoped rules, and the FSM redesign replaced a Ralph loop with a deterministic phase state machine that passed all gates. I have what I need; re-reading the full notes would burn tokens for marginal gain and risk the very echo-chamber pattern under analysis. Synthesizing now.

---

# FINAL SYNTHESIS — Optimal Agentic Workspace (Claude Code + Codex + Antigravity, ~40 MCP / 100s of skills)

The research and the 6-persona council are unusually convergent. Two personas (behavior-ux, contrarian) returned hard critiques; four returned nothing, which I read as "no objection to the corroborated core." The contrarian's central move — **the layer split is organized by mechanism, but failure happens by lifecycle** — is correct and I adopt it as the organizing frame below. L0-L4 are retained only as a vocabulary; the actual design is a **task-lifecycle state machine** with the four mechanisms woven through each phase.

---

## 1. CORROBORATED BEST-PRACTICES PER LAYER (highest-confidence, multi-source, one-line-actionable)

**L0 — Behavior (this is a *wiring table*, not prose; see Hole #1):**
- Add one literal line to CLAUDE.md/AGENTS.md: *"Ask clarifying questions before any long-horizon or ambiguous task."* — single highest-impact behavior change (resolve rate 28% → 48.8%, ICLR 2026 / docsastruth-N7; character-N7).
- Make clarification **EVPI-gated, not always-on**: ask only when `E[utility_gain] > cognitive_cost`, over tool-parameter space (SAGE-Agent; character-C1) — "always-ask" trains rubber-stamping (Anthropic: 93% of prompts rubber-stamped; character-C5).
- **Front-load** all goal clarification into the first 1-2 actions — there is a hard phase transition at 10% of execution after which it is baseline-worthless (arXiv:2605.07937; character-N1).
- Proactive suggestions **only at task boundaries** (PostToolBatch/idle), never mid-task — mid-task task-switching is the strongest single predictor of performance decline, ~3x intrinsic complexity (Precision Proactivity; character-C-Contradiction-3).
- Mandate a **generator-critic pass** before surfacing any significant output — sycophancy is trained into weights, not promptable away (Silicon Mirror 85.7% reduction; character-C7).

**L1 — Discovery / Routing:**
- Keep total **auto-loaded tools ≤ 30**; defer the rest — the 30/50/200/740 degradation curve is the most multi-sourced finding in the corpus (RAG-MCP, Zylos, ToolRet; discovery-C1, sota-C1).
- Turn on **`ENABLE_TOOL_SEARCH=auto:5`** (BM25+regex, default-on ≥ v2.1.x) — 85% token reduction, Opus 4.5 79.5%→88.1% (discovery-C2, memory-C3, sota-C2).
- **Hybrid BM25 + dense** beats either alone; BM25 wins on tool *names* specifically (compound identifiers) — NDCG@5 0.853 vs 0.834 (discovery-C4, sota — already what Anthropic ships).
- Every tool/skill description carries the **scope clause**: *"Use when X / do NOT use when Y / use Z instead"* — highest-ROI single description edit (<12%→97.2% coverage, Trace-Free+; -29.23% accuracy degradation at 150+ tools; discovery-C5, character-C6).
- **Two representations per skill**: a short routing label (what the agent sees) + the full body (what the retriever indexes) — SkillRouter shows a 31-44pp drop when bodies are hidden (discovery-N4, semrouter; sota Gap-3).
- Index full skill bodies in FAISS/SQLite-vec with **`all-MiniLM-L6-v2`** (22M params, 3.5ms CPU, proven at 2,413 tools) — no GPU (discovery-C7).

**L2 — Context / Overhead:**
- **Route every HTTP/SSE MCP through a stdio aggregator** (lazy-tool, Go/MIT single binary) — `ENABLE_TOOL_SEARCH` does *not* defer HTTP-transport tools (Issue #40314, closed not-planned); 120K tokens load upfront otherwise (discovery-C3, discovery-N9). **This is also a self-inflicted leak in the draft — see Hole #2.**
- **ToolScope-style overlap dedup before count reduction**: your 40 servers have overlapping search/list/get ops; semantic overlap alone costs +34-38% accuracy independent of count (arXiv:2510.20036; sota-N5).
- **HOT/WARM/COLD memory tiering** (<500 / 1-3K / compressed tokens) — 65-75% session cost reduction (memory-C7).
- **Compact early, at 70%** (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`) — the summarization model itself can overflow and deadlock at high fill (deadlock confirmed ~48% on Opus 4.6, #23751; memory-N3, sota-C7).
- **AGENTS.md as the cross-tool config** (`@AGENTS.md` import at top of CLAUDE.md), 100-150 lines soft cap, Linux-Foundation-governed, read by Codex + Antigravity + Claude (sota-C3) — directly serves the three-backend goal (closes discovery-G4 partially).

**L3 — Memory / Durability:**
- **JIT/pull, identifiers-in-context, content-via-tools** — "assume interruption; all progress not in memory is at risk" (Anthropic; memory-C2).
- **Two-layer stack**: IDE-native session-continuity (basic-memory) + graph/temporal layer (Graphiti + **FalkorDB**, not deprecated Kuzu) — no single framework covers storage+curation+retrieval+lifecycle (memory-C6, memory-C10; resolves X3/X4 toward FalkorDB).
- **Write discipline is the gap, not recall** — write *distilled conceptual beliefs* with `confidence / source / verified_by / learned_date` + **causal provenance** (one metadata field, -24.6% retrieval accuracy without it), prefer **failure-derived heuristics** over success traces (selflearning-C2/E, antidegen-N8, memory-N1). **The draft has no write schema — see Hole #4.**
- **Deduplicate-then-compress**, never aggressive-merge — 97.2% retention precision, 58% storage reduction (Microsoft prod; memory-C9).
- **Cull stale content from CLAUDE.md/notes as a performance task, not hygiene** — topically-coherent-but-irrelevant content is a *worse* distractor than random noise (memory-N9). Directly vindicates the user's own `harness_trim` (64% cut) as correct, not just tidy.

**L4 — Hooks / Enforcement:**
- **Hooks are the only enforcement layer; CLAUDE.md is advisory** — "if violating it causes unrecoverable damage, it belongs in a hook" (sota-C9, hooks-#9, selflearning-#4).
- **`exit 2` is the only blocking code**; Stop hooks use `{"decision":"block"}` + `exit 0`; always honor **`stop_hook_active`** or you get infinite loops (hooks-#1/#2, #55754).
- **Phase-gated tool visibility** (statewright): destructive tools simply don't exist in a read-only phase — local models went 2/10→10/10; highest-leverage structural anti-degenerate-action technique (sota-C10, harnesses).
- **PreToolUse goal re-injection every N turns**, verbatim, as a write-op preamble — counters instruction fade-out / drift (OpenDev; orchestration-E, character-C4). **Missing from draft — see Hole #5.**
- **Terminal-state tool outputs** (`SUCCESS:/FAILED:` + txn id, not "more results may be available") — 7x reduction (14→2 calls), zero infra, *before* any detector fires (antidegen-C1, 4 probes). **Draft reaches for the detector and skips the free prevention — Hole #6.**
- **Result-aware fingerprint** `(tool_name, args_hash, output_hash)`, not exact-match input hash — your health-check/status MCPs (`server_health`, `get_binary_status`) have identical args by design and a plain debounce will destructively false-positive (antidegen-N1/C3). **Hole #7.**

---

## 2. HOLES / CORRECTIONS THE COUNCIL SURFACED (specific)

**H1 — L0 is a wish-list with no enforcement owner.** "Be honest / ask / don't tunnel" as prose is structurally insufficient (Calibration-3: models verbalize calibrated uncertainty and *never act on it under penalty*; selflearning-C1). Worse, L0's ~7 virtues are themselves ~7 more rules competing for an already-overflowing attention budget — and adding procedural prose *without the backing mechanism increased regressions* (TDAD: 6.08%→9.94%; hooks-#6). **Fix: convert L0 into a Behavior-Enforcement Matrix — every behavior names its enforcement owner + external validation signal + timing (see §3-N1).**

**H2 — The draft's "shared HTTP hot-core on 127.0.0.1" silently destroys its own discovery layer.** Any tool behind an HTTP transport is invisible to `ENABLE_TOOL_SEARCH` (Issue #40314) → a latent ~120K-token leak baked into the architecture (contrarian; discovery-C3). **Fix: the hot-core must be stdio, or front it with lazy-tool so it's deferrable.**

**H3 — Inquisitiveness placed in the wrong primitive AND a security hole.** (a) UserPromptSubmit hooks *cannot ask* — synchronous transform filters, 30s timeout, no `AskUserQuestion`; the hook can only *route to* a skill that asks (hooks-#4) — the draft as written does not function. (b) **ASPI (arXiv:2605.17324): mid-execution clarification amplifies prompt injection 15-16x** because the user/MCP trust boundary collapses — and "always-ask + research-by-default" is precisely the vulnerable geometry (behavior-ux, character-N4). **Fix: clarification is EVPI-gated, hard-isolated to a pre-execution phase with no MCP/web tools loaded, and routed hook→skill.**

**H4 — No write-discipline schema anywhere (THE biggest gap).** L3 is entirely read/recall; the corpus is unanimous that **the write path is the bottleneck (retrieval failures dominate 11-46% of errors), not the read path** (selflearning-C2, memory). **Fix: defined schema — conceptual-belief + confidence/source/verified_by/learned_date + causal provenance, failure-heuristics preferred.**

**H5 — Anti-tunnel-vision is named in L0 but has no mechanism in L1-L4.** Drift causes 65% of 2025 enterprise agent failures (sota-C8); the fix (verbatim goal re-injection every N turns + ReflAct "gap between state and goal?" framing, +27.7%) is absent (character-C4, behavior-ux). The checkpoint stores the goal but nothing re-injects it *during a live session*, which is where drift happens.

**H6 — "/clear + reload-only-the-checkpoint" is built on a hook that doesn't fire, and is itself an echo chamber.** (a) **PreCompact does NOT fire on manual `/compact`/`/clear`** (#13572, closed not-planned) — L3 silently no-ops on the exact path it's built around. (b) `/clear`+reload-the-summary keeps only the agent's own distilled self-narrative and discards the corrective signal that lives in the failures/dissent — *the definitional echo chamber* (contrarian; selflearning-C1). (c) The checkpoint is a **poisoning surface**: a drifted/compromised pre-compaction agent writes a high-trust note read back verbatim with no surviving context to cross-check (memory-N5). **Fix: move checkpoint write to a Stop hook; recover by replaying an append-only typed ledger, not a lossy summary (§3-N2).**

**H7 — Stop verification gate will echo-chamber or loop.** A Stop hook that asks the same model "are you done?" amplifies error (AUQ Delusion Gap: System-2 reflection raises confidence in *wrong* answers 14.3% vs 3.6% correct; character-N6, selflearning-C1). **Fix: the Stop gate checks an external signal — `.coverage-thresholds.json` tests, a heuristic, or a fresh-context reviewer — never the working agent's own judgment.** (Note: heuristic detectors beat LLM judges 60.1% vs 4.7% at failure detection, antidegen-C7 — cheap external checks first.)

**H8 — "Anti-degeneration debounce" is the wrong fingerprint** (exact-match → destructive false-positives on polling tools; antidegen-N1) and **"research-by-default" has no trust tier** (ToolHijacker 7-12x usage inflation via description text; SKILL.md registry 86% adversarial-embedding success — sota-N7, discovery-N6). **Fix: result-aware triplet; and quarantine untrusted research results from the tool-selection decision + local vetted allowlist.**

**H9 — Inherited drift across the Claude→subagent→subagent chain (the user's actual metaswarm architecture) is unmitigated.** Even drift-resistant models absorb drift when conditioned on a weaker agent's raw trajectory (arXiv:2603.03258; character-N2). **Fix: never pass a subagent's raw output as prefix context — only a structured summary with the original goal re-anchored at top.** Doubly glaring given the user's own `feedback_parallel_agent_worktree` note.

---

## 3. NOVEL INTEGRATIVE IDEAS (the "find something new" deliverable)

**N1 — The Behavior-Enforcement Matrix: collapse L0 into a wiring table that forces L0↔L4 coupling.** Replace prose with a table where each behavior names *where enforced* + *external validation signal* + *timing*:

| Behavior | Enforcement owner | External (anti-echo) signal | Timing |
|---|---|---|---|
| Inquisitive | UserPromptSubmit hook → AskUserQuestion **skill** | EVPI > cost; Shapley single-Q | **Pre-exec only** (10% cliff) |
| No tunnel-vision | PreToolUse goal re-injection (verbatim) | goal-gap delta vs ledger | every N turns |
| Self-learning | Stop hook → typed ledger write | confidence/source/verified_by | task boundary |
| Proposes things | PostToolBatch/idle only | — | **never mid-task** |
| Honest (anti-syco) | generator-critic pass | independent fresh-context critic | before surfacing |

*Rationale:* this is the single change that converts the whole behavior layer from aspiration to architecture, and it's the synthesis of three convergent findings (CLAUDE.md-is-advisory + hooks-are-enforcement + each behavior has a *known* mechanism in the research). Nothing in L0 is shippable without it.

**N2 — One append-only typed event ledger subsumes L0-prose + L3-recall + the write schema (the unifying mechanism).** Borrow LogAct (memory-N6: typed shared log → **+17% work, -41% tokens**) + weft's event-sourced state machine (hooks-N4: append-only `events.jsonl` + projected `state.json`, crash-recoverable by replay, 191 tests pure stdlib). Decisions/rationale/goal/provenance are appended as typed events on the **Stop hook** (not PreCompact). Post-compaction recovery **replays the ground-truth log**, not a lossy self-summary.
*Why this is the keystone:* it simultaneously (a) kills the echo chamber (replay events, not a self-narrative — fixes H6b), (b) fixes the PreCompact-doesn't-fire bug (Stop-hook append — H6a), (c) *is* the write schema H4 demands, (d) removes the single-point poisoning surface (append-only + provenance — H6c). One artifact, four problems. It also operationalizes the user's own proven prior art — `bc_fsm_redesign` already replaced a stale-short-circuit loop with a deterministic phase state machine and passed 5/5 design + 3/3 plan gates. This *is* that pattern promoted from one project to the workspace backbone.

**N3 — Close the L3→L1 feedback loop with OATS: memory makes discovery self-improve (the cross-layer synergy nobody wired).** The draft treats Memory and Discovery as orthogonal boxes. They aren't — **basic-memory's session-outcome logs are the exact training signal OATS needs** to shift tool-retrieval embeddings toward historically-successful query centroids (`ê_i = (1−α)·e(d_i) + α·ē(Q⁺) − β·ē(Q⁻)`, α=0.3/β=0.1, **+11.4% Recall@1, CPU-only, zero serving-infra change**; discovery-N3, contrarian). Wire the N2 ledger to emit `(query, chosen_tool, success)` triples → run ~50 lines of OATS on a `schedule`/cron weekly → **discovery accuracy self-improves from the user's own usage.** This is also the *only* way "self-learning" in L0 becomes real rather than aspirational.

**N4 — The Intent/Drift Sentinel sub-agent: one component serves four layers and dissolves the inquisitiveness timing contradiction.** Stand up a lightweight Sentinel (UA-Multi pattern, arXiv:2603.26233: **69.4% vs 61.2% resolve on underspecified tasks; mid-task asks as valuable as pre-task, 43.4% vs 41.8%**) with a *tiny curated toolset* (L1's ≤30 rule — only AskUserQuestion + read-ledger + basic-memory-read). It owns **inquisitiveness AND drift-detection in one isolated-context loop**: monitors for missing info (ask-gate) and goal-gap divergence (drift-gate). Because it runs in a separate context that never touches MCP/web content, it can ask *mid-task without the ASPI 15-16x amplification* (H3b) and without inheriting the main agent's drift (H9). It writes to the N2 ledger so *intent* survives compaction — closing memory-Gap-1 (no compaction-specific clarification protocol). **One sub-agent serves inquisitiveness (L0), anti-tunnel-vision (L0), curated-toolset discipline (L1), and memory (L3).**

**N5 (bonus) — Tool-augmented adversarial review escapes the "Reasoning Trap."** The most theoretically important novel finding in the corpus: closed-system debate *cannot* increase mutual information between evidence and output (Data Processing Inequality; SFS drops 43% with standard debate — orchestration-X2/B, arXiv:2605.01704). But **tool calls injected between debate rounds break the Markov chain.** For the user's existing adversarial review council (peer-review is already mandated in CLAUDE.md), design reviewers to *call verification MCPs between rounds* (semgrep, tests, web-fetch) rather than only re-reading each other — this is what makes the council actually anti-echo-chamber rather than mutual-confirmation. Pairs with EFC (arXiv:2605.29682, R²=0.99 vs 0.33 for raw tokens): suppress any observation returned N times without changing a downstream decision.

---

## 4. REVISED ADOPTION ORDER (effort → impact) + THE FIRST MOVE

**Tier 0 — free, today, no infra (do all five this session):**
1. Add the literal *"ask clarifying questions before long-horizon/ambiguous tasks"* line to CLAUDE.md (28%→48.8%).
2. Set `ENABLE_TOOL_SEARCH=auto:5` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`.
3. Clear any stale AutoDream lock (`memory/.consolidate-lock` > 10 min — silent permanent disable, #50694).
4. Add the two-sentence **Dual-Goal + Think-in-Opposites** block to every review/critic prompt (-14pp confirmation bias, free; selflearning-B).
5. Seed basic-memory with high-quality legitimate per-project entries (MINJA poisoning 62%→6.67%; memory-N4).

**Tier 1 — low effort, structural (this week):**
6. **★ FIRST MOVE → route the HTTP/eager hot-core through a stdio aggregator (lazy-tool).** *Rationale for picking this as #1:* it is the single change that is (a) **a correctness fix, not an improvement** — the draft's HTTP hot-core silently defeats `ENABLE_TOOL_SEARCH` (H2), so the user is paying ~120K tokens/session *believing* deferral is on; (b) **the gating dependency** — Tool Search, the ≤30-tool budget, and phase-gated visibility all only work once every server is stdio-deferrable; and (c) **one binary, reversible, zero behavior risk.** Every other discovery/overhead win is downstream of this. (discovery-C3/N9, contrarian H2.)
7. Audit all ~40 MCP + skill descriptions for the scope clause; add 3-5 negative-control test rows per skill (selflearning-H).
8. ToolScope overlap-dedup pass across the 40 servers.
9. Move the compaction checkpoint write from PreCompact → **Stop hook** (fixes the silent no-op).

**Tier 2 — medium, the keystones:**
10. Build the **append-only typed event ledger** (N2) — the workspace backbone.
11. Stand up the **Intent/Drift Sentinel** sub-agent (N4) + PreToolUse goal-reinjection hook.
12. Add the graph/temporal layer (Graphiti + FalkorDB) above basic-memory.

**Tier 3 — compounding, once ≥100 successful invocations are logged:**
13. Wire the **OATS L3→L1 loop** (N3) on a weekly cron.
14. Convert subagent handoffs to structured-summary-only with re-anchored goal (H9).

**The single highest-leverage FIRST move: lazy-tool stdio aggregation of the hot-core (item 6).** It is the only Tier-1 item that is simultaneously a correctness fix *and* the unblocker for the entire discovery/overhead stack.

---

## 5. OPEN QUESTIONS GENUINELY NEEDING THE HUMAN

1. **Three-backend memory authority.** basic-memory + Graphiti span Windows-native vs WSL2. Do you want one canonical store with the others as read-replicas, or per-backend stores? No probe covered Codex/Antigravity memory interop (discovery-G4, memory-G-cross). *This is an architecture choice only you can make.*
2. **Quota contention.** Claude Code + Codex + Antigravity share one user-level quota; no source covers parallel-session rate-limit behavior (sota-Gap-6). Do you want a coordinator that serializes heavy phases, or accept occasional 429s? (Relates to your documented 401 refresh-race note.)
3. **Dreams API.** Worth requesting the research-preview for weekly memory consolidation (REM-phase association, SCM), or stay fully self-hosted? Access gate to Max/Pro is unconfirmed (memory-G1).
4. **Echo-chamber tolerance vs context cost on recovery.** N2's replay-the-ledger is more correct but heavier than reload-a-summary. Do you accept higher post-compaction recovery token cost for poison-resistance + corrective-signal retention? *This is the one explicit cost/safety tradeoff in the design.*
5. **Skill-authoring spend.** Opus-authored skills transfer to weaker agents at **+54.3%** (SkillWeaver) and **+19pp over human-authored** *only with the full multi-shot evaluate-refine-test-gate loop* (one-shot self-gen is worse than nothing; selflearning-Contradiction-1). Do you want to fund a deliberate Opus skill-authoring pass, or keep authoring opportunistically?
6. **Worktree runtime isolation.** Worktrees isolate the git index but NOT ports/DBs/env (orchestration-7). For parallel metaswarm agents, do you want ephemeral per-worktree Docker containers, or keep serial execution on shared runtime?

---

**Bottom line:** the corroborated core (defer-to-≤30 + Tool-Search + scope-clauses + hooks-as-enforcement + phase-gating + two-layer memory + compact-at-70%) is solid and largely already half-built in your harness. The council's real value was three corrections the draft got *wrong* (HTTP hot-core defeats deferral; PreCompact doesn't fire on /clear; UserPromptSubmit can't ask) and one reframe (organize by lifecycle, not mechanism). The novel ceiling-raiser is the **append-only typed ledger (N2) as the unifying backbone**, with **OATS (N3) closing the memory→discovery loop** so the system self-improves from its own usage — the only way the "self-learning" goal stops being aspirational. Start with **lazy-tool**: it's a correctness fix the rest depends on.