---
title: Reconcile + MCP-prep session (2026-07-18)
type: note
permalink: main/projects/reconcile/reconcile-mcp-prep-session-2026-07-18
tags:
- reconcile
- harness
- mcp
- compaction-checkpoint
- '2026-07-18'
---

# Reconcile + MCP-prep session (2026-07-18)

Big agent-skills-toolchain PR reconcile + the durable managed-mcp prep. Checkpoint is MID-session (#94 + the harness-WU decision still in flight).

## Reconcile outcome (main advanced through the wave, head ~4ea0540)
MERGED this session: #79/#80/#81/#82/#84/#85/#88/#91 (earlier) + #86/#87/#89/#90 (drafts) + #92 codexmon (#83 CLOSED superseded — its `/home` redact + ctx% `last_token_usage` fixes salvaged into #92) + #93 stub-ledger + #95 doc + #96 gitleaks-config + #97 qdx-hardening + #98 enshrine-additive.
- **#94 tu-wearables**: REVIVED + reviewed (verdict=merge; safe/INERT Phase-0 scaffold; 188 tests @ 100% cov independently reproduced). User chose review+merge (2+3). BLOCKED only on a gitleaks FALSE-POSITIVE (fake `AIzaSyVERYSECRET999` fixture in HISTORICAL commit b7f960b6). Fix in flight = squash the branch so the scanned tree carries the inline allows. NEXT-phase hardening prereqs tracked: the egress guard is currently DEAD CODE (no production caller) — wire it + fix endpoint-vs-base_url + enforce scrubbing + broaden scrub_secrets BEFORE any LLM-egress wiring.

## KEY FINDING — harness divergence
main's repo `ci/harness` was INDEPENDENTLY REWRITTEN to ~1/3 size AFTER Wave-0 forked (dispatcher 478->148, modules 1994->608, adapters 169->102, install.py 731->ABSENT). So Wave-0's 4 reliability WUs (WU-1 Stop-boundary re-entrancy guard, WU-2 deploy-receipt source_commit, WU-4 SHADOW gates, task-9 edit-guard) are un-cherry-pickable -> need RE-IMPLEMENTATION. #98 landed only the ADDITIVE parts (21 net-new skills + Wave-0 docs). User chose "investigate first" -> investigating whether main's leaner harness already meets Wave-0's reliability goals (obsolete) or lost them (regression). Likely a concurrent session did the rewrite.

## LESSONS (durable)
- **Count-inference != set-comparison (NEAR-MISS).** I called WU-3's 22-skill backport "redundant" from a manifest COUNT (main 161 > target 107) and nearly instructed DROPPING it. User challenged -> verified: only 1/22 (multi-ai-mingle) was on main; **21 were NET-NEW**. A count proves nothing about set membership. Always do the actual per-item set-comparison for any "redundant/skip" call.
- **CI pins ruff 0.15.17; local/PostToolUse is 0.15.22 and they FORMAT DIFFERENTLY.** Use `uvx ruff@0.15.17` for any format fix on this repo; never run local 0.15.22 `ruff format` on a branch (reintroduces a diff CI rejects).
- **Agents run `ruff check` but forget the separate `ruff format --check` gate-lint step** — bit #93/#94/#97. Prompt agents to run BOTH.
- **gitleaks path-`[[allowlists]]` do NOT waive a finding in a HISTORICAL commit under CI git-log (base..head) mode.** Inline `# gitleaks:allow` only covers the commit it is IN. Fix a historical fake-fixture finding by SQUASHING the branch (scanned tree then carries the allow) or rewriting the fixture to a non-matching literal. Also: `.gitleaks.toml` mixing singular `[allowlist]` + plural `[[allowlists]]` FAILS to load (falls back to defaults, false-flags everything) -> #96 merged into plural + a test-path allowlist.
- **quality.yml runs pytest for only ~3-4 packages** (mcp-manager, scholarly-access-mcp, taskwatch_monitor). Most MCP packages' suites NEVER run in CI -> "CI green" usually means only ruff/opengrep/gitleaks/osv passed, NOT that the package's tests ran. (BW1 candidate: expand coverage.)
- **Don't own-assign a coder a task whose title says "merge" when its prompt says don't** — a coder resumed and merged 4 PRs autonomously because its owned task was titled "Finish + merge...". Main stayed green (required quality gate passed) but the pre-merge review became post-hoc. Reconcile the task-title vs the prompt.

## MCP durable fix — PREP DONE (apply = owner, Claude-closed)
Continues the managed-mcp durable fix (see the 2026-07-17 note). Prep this session; artifacts in `~/.claude/mcp-restructure-2026-07-17/`:
- **serena RE-ADDED** to mcp-fleet.json (on-demand tier, count 64->65, NOT daily — owner chose on-demand to avoid eager-spawn RAM on the ~1GB-free box). Command: `uvx --from git+https://github.com/oraios/serena serena start-mcp-server`.
- **Secrets diagnosed** (names/scope only, no values): 11/19 daily already USER-persistent (0 need migration — the "migrate ~15 profile secrets" gate is effectively satisfied); 8 absent everywhere (EXA_API_KEY_2, FIRECRAWL_API_KEY_2, GOOGLE_CLOUD_PROJECT, KAGGLE_KEY/USERNAME, MODAL_TOKEN_ID/SECRET, TAVILY_API_KEY_2) = unset now too, so NOT a managed-mcp regression.
- `PREP-STATUS-2026-07-18.md` written. APPLY (admin + Claude-fully-closed, per APPLY-managed-mcp.md) remains owner-action; rotate the plaintext `ghp_` PAT (security).

## Still pending
#94 merge (after gitleaks squash), the harness-WU divergence decision (after investigation), Phase-E branch/ref prune (gated behind these), BW1 harness build, the Jul-12 dirty-worktree leftover reconcile (untracked leftovers backed up to reconcile-2026-07-18/leftover-backup/).
