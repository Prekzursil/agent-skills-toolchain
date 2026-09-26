---
title: 'Harness capability build: full-coverage router + strong-tool-nudge + memory-prefetch
  (reconciled best-of-best)'
type: note
permalink: main/harness/harness-capability-build-full-coverage-router-strong-tool-nudge-memory-prefetch-reconciled-best-of-best
tags:
- harness
- router
- mcp
- memory
- hooks
- capability
- sota
---

# Harness capability build — reconciled best-of-best (2026-06-21)

Built from the deep-research harmony design ([[HARMONY-DESIGN-2026-06-21]] / `~/.claude/HARMONY-DESIGN-2026-06-21.json`), reconciled with its adversarial review (embeddings over-engineered for ~376 static units; claim-FACTS would poison the working guard). Lexical-first, eval-gated, embeddings deferred-on-measurement.

## Shipped + tested
- **`hooks/skill-router/capabilities.py`** (NEW library) — ONE shared regex->MCP map covering all ~48 servers (was 8). Read by BOTH the router and the nudge. `match(text, hand_roll_only=)`.
- **`hooks/skill-router/route.py`** (rewritten, INDEX_VER=4) — full-coverage UNI: indexes ALL routable units — skills (967) + agents (16) + commands (64) + **basic-memory notes (368, from D:\basic-memory)** = **1,415 units** (was 472 skill-only). IDF lexical scoring; output buckets skills/agents/commands/memory + MCP via capabilities.py. Fail-open, threshold-gated, 24h cache. eval.py is the validator.
- **`hooks/strong-tool-nudge/check.py`** (NEW hook, the ONLY net-new hook — anti-bloat OK) — PreToolUse(Bash|Write|Edit|MultiEdit); reuses capabilities.py hand-roll signatures; catches `pip install rdkit`->rdkit MCP, `requests.get` scraping->firecrawl, `git grep def`->serena, etc. at the action moment; inject-only, once/signature/session, fail-open. Wired in settings.json.

## Verified
Router: PDF->pdf-reader MCP, find-refs->serena, excel->excel MCP, security->security-reviewer agent, migration-prompt->the 2 relevant memory notes — all previously invisible, now route. Nudge: 3/3 hand-roll signatures fire once/session, benign silent. Trivial prompts silent.

## Known limitation (the eval signal)
Lexical recall misses paraphrases where the unit TITLE lacks the query terms (e.g. "args undefined bug" missed the Workflow-gotcha note). This is exactly what the **deferred embedding lane** (RAG-MCP/ScaleMCP/RRF per the dossiers) would fix — add ONLY if eval shows these misses matter. 

## Deferred (per the skeptic, measured-gated)
Embedding/semantic lane; claim-guard-FACTS (CUT — keep the categorical guard pure); episodic->semantic auto-consolidation; Decision-Point Sentinel (mid-task reasoning router) — a clean future add. Extends [[Skill/MCP router hook — fixes "only uses skills/MCPs when explicitly invoked"]].
