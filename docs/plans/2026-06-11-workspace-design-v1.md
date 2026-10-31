---
title: 2026-06-11-workspace-design-v1
type: note
permalink: dqverify-repo-20261013/docs/plans/2026-06-11-workspace-design-v1
---

# Optimal Agentic Workspace — Design v1 (LOCKED architecture)

**Date:** 2026-06-11 · **Status:** v1 — supersedes the v0 draft (`2026-06-10-optimal-agentic-workspace-design.md`). Evidence base: `2026-06-11-workspace-knowledge-base.md` + `docs/research/2026-06-11-fanout-*.md`. Pending Design Review Gate (Fable) → build.

## The thesis (what the whole effort distilled to)
The optimal workspace is **not a platform to build — it is a prune + a handful of hooks, with one keystone artifact.** Organize by **task-lifecycle**, not by mechanism (failure happens per phase). The "4 layers" are **one diagonal:** hooks emit signal → a typed ledger stores it (incl. failures) → retrieval consumes it → next selection improves.

## Locked decisions (with rationale → knowledge base)
- **tooluniverse KEPT** (in active use). **FalkorDB/Graphiti DROPPED** (3rd memory layer contradicts the user's own context-rot audit [[toolkit-gap-analysis-2026-05]]). **Docker DROPPED** (WSL2 can't reclaim RAM). **No vector index / capability-gateway yet** — measure after prune first.
- **Echo-chamber recovery = REPLAY the typed ledger** (user-decided) — not a lossy summary.
- **Tier-0 already applied:** `ENABLE_TOOL_SEARCH=auto:5`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`, CLAUDE.md clarifying-Q/anti-tunnel line.

## Architecture (5 concerns, lifecycle-woven)

### A. Discovery / skill-find  →  "agent picks the right skill/MCP"
- Native **Tool Search** (`auto:5`, done) + **PRUNE the menu to ≤30 auto-loaded** (the cause of mis-selection): uninstall the 3× identical packs (`document-skills`≡`example-skills`≡`claude-api`), dedupe reviewers, collapse `source-command-*`; **tooluniverse stays**, disabled-until-needed where heavy.
- **Single-line scope-clause descriptions** ("Use when X / NOT when Y / use Z instead") — done for 29 user skills (commit 88af95d); audit remainder + MCP tool descriptions.
- **ToolScope overlap-dedup** (binary-ninja ×2, browsers ×4, docx/pdf/xlsx ×3).
- *Deferred (measure-first):* hybrid BM25+dense + cross-encoder reranker index — only if prune+ToolSearch proves insufficient; build a recall@5 eval (mined from transcripts) before any index.

### B. Overhead / RAM  →  lower-leverage than cognition
- The **prune IS the RAM fix** (kills the ~35K-token/subagent baseline). No daemon. Keep `mcp-reaper.ps1` backstop. If a shared hot-core is ever built it must be **stdio** (HTTP defeats Tool Search, #40314) and **authenticated** (per-identity broker, default-deny for code-exec MCPs — the Fable security verdict).

### C. Memory & continuity  →  THE KEYSTONE (fixes echo-chamber + repetitive actions)
**N2 — append-only typed event ledger** (`events.jsonl` + projected `state.json`, replay-recoverable):
- **Written by hooks, not the agent** (agent = annotator). Harvest on the **Stop hook** (NOT PreCompact — it doesn't fire on `/clear`, #13572): objective ledger (cmd / exit / files / git HEAD / test-counts) + rare typed decision/goal records.
- **Recovery = replay the ledger** (keeps failure/dissent signal — kills the echo-chamber at the source). SessionStart diffs the ledger stamp vs live `git rev-parse HEAD` + dirty-hash → surfaces drift **before** the agent reads.
- **Failure entries** carry falsifiable preconditions (version/env/error-sig) + TTL, labeled "hypothesis — re-test before trusting"; a contradicting success **auto-tombstones** (supersedes-link) — fixes the rotting-notes problem visible in the vault.
- basic-memory stays the semantic store; CLAUDE.md <300 lines; pull-not-push.
- *Repetitive actions:* terminal-state tool outputs (`SUCCESS:/FAILED:`+id, 7× cut) + result-aware fingerprint `(tool, args_hash, output_hash)`.

### D. Behavior  →  the Behavior-Enforcement Matrix (N1), not prose
| Behavior | Enforced by | External (anti-echo) signal | Timing |
|---|---|---|---|
| Inquisitive | UserPromptSubmit hook **→ routes to an AskUserQuestion skill** (the hook itself can't ask) | EVPI > cost | **pre-execution only** (10% cliff; mid-task asking = 15-16× injection risk) |
| No tunnel-vision | PreToolUse **goal re-injection** (verbatim) | goal-gap vs ledger | every N turns |
| Self-learning | Stop hook → typed ledger | confidence/source/verified_by | task boundary |
| Proposes things | PostToolBatch/idle only | — | never mid-task |
| Honest (anti-syco) | generator-critic pass | fresh-context critic | before surfacing |
- **Subagent handoffs:** never pass raw output as prefix — structured summary with re-anchored goal (H9).
- **N4 Intent/Drift Sentinel** (Tier 2): tiny isolated sub-agent (AskUserQuestion + read-ledger + basic-memory-read only) owns inquisitiveness + drift-detection; asks mid-task without injection risk.

### E. Self-learning  →  N3 OATS (Tier 3, deferred)
Once ≥100 invocations are logged, a weekly cron nudges tool-retrieval toward historically-successful centroids (+11.4% Recall@1). Memory makes discovery self-improve — the only way "self-learning" is real.

### Cross-AI
**AGENTS.md** (`@AGENTS.md` import in CLAUDE.md) = the one config Claude+Codex+Antigravity all read.

## Adoption order
- **Tier 0 — DONE** (Tool Search, autocompact, CLAUDE.md line).
- **Tier 1 — prune + descriptions (this week):** prune ≤30; scope-clause audit (remainder); ToolScope dedup; move checkpoint write → Stop hook; AGENTS.md.
- **Tier 2 — keystone:** the N2 typed ledger + replay-recovery + Stop/SessionStart hooks; the Behavior-Enforcement Matrix hooks; the N4 Sentinel.
- **Tier 3 — compounding:** OATS loop; structured subagent handoffs everywhere.

## Open questions for the human (the 6 from §5; 1 resolved)
1. Memory authority across 3 backends (canonical basic-memory + read-replicas, or per-backend)? · 2. Quota coordinator vs accept-429s? · 3. ~~Echo-chamber recovery cost~~ **RESOLVED = replay** · 4. Fund an Opus skill-authoring pass (+54.3%, needs the full evaluate-refine-test loop)? · 5. Dreams API preview? · 6. Per-worktree container isolation for parallel agents?

## Build sequence
Design v1 → **Fable Design Review Gate** (Opus throttle-safe) → writing-plans (keystone-first: N2 ledger) → execute Tier-1 prune + Tier-2 ledger. The mcp-manager (building now) becomes the **operator UI for the pruned menu** + can drive the prune.