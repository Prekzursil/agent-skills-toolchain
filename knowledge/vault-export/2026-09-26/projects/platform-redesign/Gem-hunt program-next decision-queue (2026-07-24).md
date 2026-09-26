---
title: Gem-hunt program-next decision-queue (2026-07-24)
type: project
permalink: main/projects/platform-redesign/gem-hunt-program-next-decision-queue-2026-07-24
tags:
- gem-hunt
- decision-queue
- harness
- platform-redesign
- '2026-07-24'
- discovery
---

9-lens gem-hunt (wf_167af38d, all Opus/max, API key, 1.33M subagent tokens, 0 errors) → tiered decision-queue. Doc: `C:\Users\Prekzursil\.claude\gem-hunt-2026-07-24\DECISION-QUEUE.md` (43KB). DISCOVERY ONLY — owner steers adoption.

## Observations
- [milestone] 10 cross-lens-convergent gems map onto 6 documented pains (commit-exhaustion freeze, hung-reviewer deadlock, C2 overclaims, detector-rot, silent data-loss, green-but-nonfunctional). #convergence — KEYSTONE = a both-states detector-self-test (TG-1) that protects every later gate.
- [reference] TIER-0 (reversible config/prune, ~10): MCP blast-radius env caps (MAX_MCP_OUTPUT_TOKENS=25000/MCP_TOOL_TIMEOUT/MCP_TIMEOUT); reviewer subagent maxTurns+tools/mcpServers scope (isolation UNVERIFIED); verify native /rewind then retire custom checkpoint cmds; use built-in Explore as the grounding-pack primitive; prune ECC remnants (49MB cache + dead 298-line hooks.json); Playwright triple-mount→single (keep playwright-cdp, disable playwright+playwright-extension); backup-file sweep→_attic (+delete .corrupt-NUL/.tmp); delete design-review-loop tombstone + fold transpose-to-figma; drop 4 redundant deniedMcpServers + repoint stale claude-in-chrome matcher→playwright-cdp; enable context-editing clear_tool_uses_20250919 (+39%/-84% tokens). #tier0 — NOTE: MCP-curation items (Playwright, deniedMcpServers) hit the never-destroy-MCP-state rule → back up + verify before applying.
- [reference] TOP GEMS (builds, high-value): TG-1 detector-self-test (KEYSTONE); TG-2 mutation-gate on changed files (cosmic-ray/mutmut/Stryker — coverage is a proven liar); TG-3 metamorphic-oracle (oracle-free correctness for media/RE/chem/BC); TG-4 semantic-entropy confabulation gate (numeric layer under WEP bands, attacks C2 overclaims); TG-5 fencing tokens + idempotency keys (safe requeue — ~40LOC ledger-fold, pairs with H-20); TG-6 auto cross-vendor Codex oracle on 2nd stuck-fingerprint (automates AGENTS.md 4b, pairs with C16 breaker); TG-7 anti-degen fingerprint + OpenHands 5 stuck-heuristics; TG-8 rules-to-linter (prose footguns→semgrep+PSScriptAnalyzer PreToolUse); TG-9 blob-parity (format the git BLOB/LF not CRLF worktree); TG-10 structural-diff-guard (difftastic symbol-deletion); TG-11 kill self-conditioning (strip raw FAILED traces from re-injection); TG-12 count-in/count-out commit-scope gate; TG-13 ACH diagnosticity matrix; TG-14 injection-taint-scanner (feeds EXISTING ledger taint field). #top-gems
- [decision] PRUNES + SKIP-set. #prune — Prunes: ~39 orphan hook dirs → git mv into dated _retired-hooks/ (never delete); fold non-blocking hooks into _dispatch (-2 spawns/Bash); verify skill-router lazy-load still wired (else naive-session regression silently live). SKIP: already-BUILT (execution-grounded-bon, diff-blind-test-synth, event-ledger=Reflexion, diff-cover) + REJECTED-component (trained critic, 2nd-runtime, weights=SEAL, vector=mem0, observability=OTEL) — the anti-overfit anchor held.

## Relations
- relates_to [[A8 scope ruling: UNION both selections + build all divergent (2026-07-24)]]
- relates_to [[C16 + H-20 both BUILT (2026-07-24) — propose-only, review-pending]]