---
title: Config-drift audit + auto-compact fix 2026-07-13
type: report
permalink: main/harness/config-drift-audit-auto-compact-fix-2026-07-13
tags:
- harness
- config-drift
- compaction
- reconcile
- agent-skills-toolchain
---

Checkpoint for the harness/config **centralization program** (user's big ask: pull all harness/skills/MCP/hooks/settings into the versioned toolchain repo, user-scoped + portable, enforce no-drift, then build native-grade configurable Codex + verbose monitor).

## Auto-compact throttle — FIXED 2026-07-13
`~/.claude/settings.json` had `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70` (env block) + `autoCompactWindow=800000` → auto-compact fired at **70% × 800k = 560k** on a **1M-capable `opus[1m]`** model (≈44% of capacity wasted; user reported "compacts too fast"). **Fixed → `90` + `1000000` = 900k trigger.** Backup `settings.json.bak-autocompact-20260713-030334`. JSON re-validated. Activates on **next Claude Code restart** (the pct override is a launch-time env var; a live session keeps its old trigger).
- **REUSABLE:** early/aggressive compaction → check those two knobs in `~/.claude/settings.json` first. It was NOT the harness.
- **Deeper baseline eater:** the MCP tool catalog was ~421k (**52% of window**) from 63 user-scope servers → the MCP-prune step below reclaims it. `ENABLE_TOOL_SEARCH=auto:5` (deferral) is already on and helping — keep it.

## Config-drift audit — DONE (Workflow `wos6gww7i`, 4 domains, 5 agents, 0 err, 778k tok)
Full RECONCILE+ENFORCE plan durable at the scratchpad `tasks/wos6gww7i.output` (+ per-agent `journal.jsonl`). Headline: **zero real secrets in any domain** (every hit = placeholder / fake fixture / public tool example); drift is **coherent, tested (350 pass), shadow-gated** → **safe to enshrine** behind excludes. Biggest structural gap: **`~/.agents/harness` (load-bearing runtime) has NO version control** — no history/rollback. `~/.mcp.json` IS mirrored (stale) at `tools/mcp/canonical-mcp-servers.json`.

## 5 decisions LOCKED (backed by prior directives / user's own ask)
- **D1 security** — enshrine secret-literal / rm-rf+force-push / credential-read hard-blocks **as-is (opt-in, default-OFF)** per explicit **2026-07-11 owner directive**; redaction-to-disk floor stays ON+tested. Documented with temporal validity. User may flip back to ALWAYS-ON on request (surfaced, reversible).
- **D2 architecture** — **repo-as-source-of-truth, deploy repo→live** (matches user's "one place, toolchain repo, enforce it"). Flips MCP (`~/.mcp.json` self-declares canonical) + harness edit-in-place to repo-first.
- **D3** — crypto-ctf versioned but **stripped** (`.venv` 313MB + nested `RsaCtfTool/.git` + example keys excluded/allowlisted).
- **D4** — 53 ECC/community skill packs → marked `external/` subtree (preserve `origin:`); **security-review 3 hook-installers** (gateguard, plankton-code-quality, continuous-learning-v2) before trusting; collapse 4 governance dupes onto versioned winners.
- **D5** — `codex-fleet-github` experimental-in-canonical (not promoted live) until `feat/codex-parity-runner` merges; OVH/Databricks env parked.

## FIX-FIRST bugs (fix during reconcile)
1. **Data-loss footgun:** 5 hand-edits in `settings.json` hooks block (narrowed PreToolUse matcher, SessionStart local-tui-reminder, PreToolUse workflow-monitor "Workflow" group, WorktreeCreate, WorktreeRemove) → a bare `install.py`/`--bootstrap` regenerates from `registration.py` and SILENTLY WIPES them → fold into `registration.py`. **Freeze bare install.py until done.**
2. `_repro_fingerprint` (modules.py:1686 — calls `ledger.last_failed_fingerprint` that only exists on the test fake) + `_config_drift` (modules.py:615 — reads `installed.json` from `default_state_root()` but install.py writes `HERE/`) = green-but-inert gates.
3. **playwright supply-chain:** `~/.mcp.json:226` auto-fetches unofficial abandoned `playwright-mcp@0.0.19` → official `@playwright/mcp` (fix in live + canonical).
4. cloud-hub `KAGGLE_API_TOKEN` → `KAGGLE_USERNAME`+`KAGGLE_KEY`.
5. crypto-ctf bloat strip (D3).

## Already-live-only from PRIOR session (must flow into VCS during enshrine)
- **Loop fix:** `adapters.py` populates `event.trigger` from `stop_hook_active`; `modules.py` `ClaimWarningModule` re-entrancy guard → stops the "Stop 3/4 · 53k tokens" endless-loop. 350 tests pass.
- **Codex config fix:** removed the malformed `[mcp_servers."github"]` block from `~/.codex/config.toml` (url-under-stdio killed codex at load).

## NEXT
Isolated git worktree off `feat/codex-fleet-github-wave2` tip (repo has **12 dirty cloud-hub/search-hub files from another session — do NOT entangle**; scoped adds only, no `git add -A`). Add `.gitignore` excludes (`installed.json`, `backups/`, `__pycache__`, `.venv`, `**/.git`, `node_modules`), apply FIX-FIRST, enshrine 4 domains, gitleaks scan, commit local branch (**no push**). Then enforce wiring (canonical-config edit-guard shadow-first + basic-memory discipline + RECONCILE-LOG + DEPLOYED-MANIFEST) + codex-native features. MCP user-scope promote (`promote-mcp-userscope.ps1 -PruneExtraUserServers`) requires **Claude fully closed** → run-after-close step.

Relations:
- relates_to [[harness-drift-memory-chain-gap-discovered-2026-07-13]]
- relates_to [[Reframe codex audit 2026-07-13]]