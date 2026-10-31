---
title: 2026-06-11-workspace-knowledge-base
type: note
permalink: dqverify-repo-20261013/docs/plans/2026-06-11-workspace-knowledge-base
---

# Optimal Agentic Workspace — Solution-Mapped Synthesis (canonical)

**Date:** 2026-06-11 · Evidence base for the design. **Raw research is now archived as docs** (read for depth):
- `docs/research/2026-06-11-fanout-synthesis.md` (22K — distilled, 5 sections)
- `docs/research/2026-06-11-fanout-corpus.md` (100K — the 8-cluster, 50-probe corroborated research)
- `docs/research/2026-06-11-fanout-council.md` (the 2 Opus personas)
- Council critiques also: external model-council (4 models) + 4 Fable personas (in conversation/design doc).

**Provenance:** 4 deep pillars + 50-probe fan-out (`wf_d3c3408d-c34`) + 3 council streams (external models; 2 Opus self-council; 4 Fable self-council). User corrections folded in: **tooluniverse STAYS** (in active use); **FalkorDB/Graphiti DROPPED** (Fable: contradicts the user's own context-rot audit [[toolkit-gap-analysis-2026-05]]).

---

## ★ SOLUTION MAP — the concrete fix for each problem you named

### 1. "Skill-find" — agent doesn't auto-pick the right skill/MCP
**Root cause (measured):** selection accuracy collapses past **30-50 tools** → 13-20% at 200-740 (RAG-MCP, ToolRet). You run 300-1000+. **Fixes, in order:**
- **`ENABLE_TOOL_SEARCH=auto:5`** (free, today) — 85% token cut + Opus 4.5 79.5%→88.1% selection. Native BM25; default-on ≥v2.1.x.
- **Keep auto-loaded tools ≤30** — i.e. **PRUNE the menu** (the duplicate packs, near-dups) + per-project scoping. This is *most* of the fix; everything else is downstream.
- **Single-line scope-clause descriptions** ("Use when X / NOT when Y / use Z instead") — <12%→97.2% coverage (Trace-Free+); multi-line YAML truncates to line 1 (~40% of misfires).
- **ToolScope overlap-dedup** — semantic overlap costs +34-38% accuracy *independent of count* (you mount binary-ninja 2×, browsers 4×, docx/pdf/xlsx 3×).
- **Later, IF measured insufficient:** hybrid BM25+dense + **cross-encoder reranker** (one component fixes negation + near-dups + register gap). Build a recall@5 eval (mined from transcripts) first. *At ~40 tools you may never need an index.*

### 2. "RAM"
**Reframe (council):** tokens degrade *cognition*; RAM only constrains the *machine* — **RAM is the lower-leverage half.** The ~35K-token/subagent baseline is fixed by **shrinking the menu, not by a daemon** (ephemeral spawn *adds* 5-15s latency and still inherits the menu). **Fixes:** prune; native Tool Search; lazy-spawn+idle-reap tail (lazy-mcp 5-min reaper / MCPJungle) *only if* a shared daemon is built; keep `mcp-reaper.ps1` backstop. **DROP Docker** (WSL2 Resource Saver can't reclaim RAM) and **FalkorDB** (Redis→Docker→multi-GB vmmem pin — costs more RAM than it saves).

### 3. "Context" — token bloat + post-compaction echo-chamber + repetitive actions
- **Tokens:** Tool Search (85% cut) + **compact early at 70%** (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`; summarizer deadlocks ~48% at high fill, #23751) + HOT/WARM/COLD tiering (65-75% cut) + cull stale (topically-coherent-but-irrelevant is a *worse* distractor than noise — vindicates [[harness-trim]]).
- **Echo-chamber ROOT fix (keystone N2):** an **append-only typed event ledger** (`events.jsonl` + projected `state.json`, crash-recoverable by replay) written on the **Stop hook** (NOT PreCompact — it doesn't fire on `/clear`, #13572). Recovery = **replay the ground-truth log**, never a lossy self-summary. Kills the echo-chamber at the source + IS the write-schema + removes the poisoning surface. *This is your `bc_fsm_redesign` pattern promoted to the workspace backbone.*
- **Repetitive actions:** **terminal-state tool outputs** (`SUCCESS:/FAILED:`+id, no "more results may be available") = 7× reduction (14→2) *before* any detector; **result-aware fingerprint** `(tool, args_hash, output_hash)` not input-hash (polling MCPs like `server_health` have identical args by design → plain debounce destroys them); heuristic detectors beat LLM judges 60.1% vs 4.7%.

### 4. "Behavior" — inquisitive, disciplined, anti-tunnel-vision, proactive, honest (your contract)
**The single biggest structural win = the Behavior-Enforcement Matrix (N1):** convert the prose contract into a *wiring table* — each behavior names its **enforcement owner + external (anti-echo) signal + timing.** Prose alone *increases* regressions (TDAD 6.08%→9.94%).

| Behavior | Enforced by | External signal | Timing |
|---|---|---|---|
| Inquisitive | UserPromptSubmit hook **→ routes to an AskUserQuestion skill** (the hook itself CANNOT ask) | EVPI > cost (not always-ask → 93% rubber-stamping) | **Pre-execution only** (hard 10% cliff; mid-task asking = 15-16× injection risk, ASPI) |
| No tunnel-vision | PreToolUse **goal re-injection** (verbatim) every N turns | goal-gap delta vs ledger (ReflAct +27.7%; drift = 65% of 2025 agent failures) | every N turns |
| Self-learning | Stop hook → typed ledger | confidence/source/verified_by | task boundary |
| Proposes things | PostToolBatch/idle only | — | **never mid-task** (task-switching ~3× complexity) |
| Honest (anti-syco) | **generator-critic pass** before surfacing | independent fresh-context critic | before output (sycophancy is in weights, not promptable) |

Plus **H9:** never pass a subagent's raw output as prefix context — only a **structured summary with the goal re-anchored at top** (drift is inherited down the Claude→subagent chain — your own `feedback_parallel_agent_worktree` burn).

### 5. "Self-learning" — made real, not aspirational
**N3 — OATS L3→L1 loop:** the ledger emits `(query, chosen_tool, success)` triples → a **weekly cron** nudges tool-retrieval embeddings toward historically-successful centroids (+11.4% Recall@1, CPU-only, ~50 lines). **Memory makes discovery self-improve from your own usage** — the cross-layer synergy. Failure-derived heuristics (with TTL + falsifiable preconditions + auto-tombstone-on-contradiction) preferred over success traces.

### 6. The unifying reframe
Organize by **task-lifecycle state machine, not by mechanism** — failure happens per *phase*. **Phase-gated tool visibility** (destructive tools don't *exist* in a read-only phase; local models 2/10→10/10). The "4 orthogonal layers" are really **one diagonal:** hooks emit signal → ledger stores it (incl. failures) → retrieval/OATS consumes it → next selection improves.

---

## Holes that change the design (H1-H9, from the deep synthesis)
H1 L0-prose needs the Matrix (N1). H2 HTTP hot-core defeats Tool Search (#40314) → stdio/lazy-tool. H3 UserPromptSubmit can't ask + mid-task clarify = 15-16× injection → hook→skill, pre-exec, isolated. H4 no write-schema (the biggest gap; write path is the bottleneck, 11-46% of errors) → N2 ledger. H5 anti-tunnel has no mechanism → goal re-injection. H6 PreCompact doesn't fire on /clear (#13572) + reload-summary IS the echo chamber → Stop-hook ledger + replay. H7 Stop "are you done?" amplifies error (System-2 raises confidence in WRONG answers) → external signal only. H8 debounce wrong fingerprint + research has no trust tier (ToolHijacker 7-12×; 86% adversarial-embedding success) → result-triplet + quarantine untrusted research. H9 inherited subagent drift → structured-summary handoffs.

## Novel ceiling-raisers (N1-N5)
N1 Behavior-Enforcement Matrix. **N2 append-only typed ledger = THE keystone** (one artifact, four problems). N3 OATS memory→discovery self-improvement. N4 Intent/Drift Sentinel sub-agent (inquisitiveness + drift, isolated, no injection risk). N5 tool-augmented adversarial review escapes the "Reasoning Trap" (closed debate can't add info — Data Processing Inequality; tool calls *between* rounds break the Markov chain → your council reviewers should call verification MCPs between rounds).

## Reconciled adoption order (Opus-build ∩ Fable-simplify)
- **Tier 0 — free, today:** clarifying-Q line in CLAUDE.md (28%→48.8%); `ENABLE_TOOL_SEARCH=auto:5` + `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`; clear stale AutoDream lock (`memory/.consolidate-lock` >10min = silent disable, #50694); Dual-Goal/Think-in-Opposites block in critic prompts (−14pp confirmation bias); seed basic-memory legit entries (MINJA poisoning 62%→6.67%).
- **Tier 1 — structural, this week:** **PRUNE ~600→~40** (Fable's #1; tooluniverse kept); scope-clause audit + negative-control rows; ToolScope dedup; move checkpoint write PreCompact→**Stop hook**.
- **Tier 2 — keystones:** the **N2 typed ledger** (backbone); **N4 Intent/Drift Sentinel** + goal-reinjection hook. *(FalkorDB/Graphiti DROPPED — basic-memory only; derive any graph as a rebuildable read-index if ever needed.)*
- **Tier 3 — compounding (after ≥100 logged invocations):** **N3 OATS** weekly cron; structured-summary subagent handoffs.

## 6 open questions that genuinely need YOU
1. **Memory authority across 3 backends** — one canonical basic-memory store with Codex/Antigravity as read-replicas, or per-backend? (No probe covered Codex/Antigravity memory interop.)
2. **Quota contention** — a coordinator that serializes heavy phases across Claude+Codex+Antigravity, or accept occasional 429s? (Tonight's rate-limits + your 401 refresh-race note.)
3. **Echo-chamber tolerance vs recovery cost** — N2 replay is more correct but heavier than reload-a-summary. Accept higher post-compaction token cost for poison-resistance? (The one explicit cost/safety tradeoff.)
4. **Skill-authoring spend** — fund a deliberate Opus skill-authoring pass (+54.3% transfer, but only with the full evaluate-refine-test loop; one-shot is worse than nothing), or author opportunistically?
5. **Dreams API** — request the research-preview for weekly memory consolidation, or stay self-hosted?
6. **Worktree runtime isolation** — ephemeral per-worktree containers for parallel metaswarm agents (worktrees isolate git index but NOT ports/DBs/env), or keep serial?