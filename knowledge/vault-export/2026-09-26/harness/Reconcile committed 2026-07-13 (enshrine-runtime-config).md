---
title: Reconcile committed 2026-07-13 (enshrine-runtime-config)
type: report
permalink: main/harness/reconcile-committed-2026-07-13-enshrine-runtime-config
tags:
- harness
- config-drift
- reconcile
- milestone
- agent-skills-toolchain
---

Phase-1 (RECONCILE) of the config-centralization program is **committed**. Continues [[config-drift-audit-auto-compact-fix-2026-07-13]].

## Commit
- Repo `C:/Users/Prekzursil/source/agent-skills-toolchain`, isolated worktree `C:/Users/Prekzursil/source/ast-harness-reconcile`, branch **`chore/enshrine-runtime-config`**, HEAD **`5d2fca2`**, **371 files**, **NOT pushed** (local only, awaiting user).
- Based off `feat/codex-fleet-github-wave2` tip (the audit baseline), NOT main, so the diff is pure live-drift. Worktree git-crypt neutralized per-worktree (accounts.json inert; main tree's 12 dirty files + real git-crypt untouched).

## What landed (verified independently, not self-cert)
- **Harness → ci/harness**: 8 core + 4 new modules (install/registration/recall_index/injection_grammar) + net-new tests/ (**356 pass, 12.8s**) + schemas + README. Carries the Stop-loop fix. 3 defect fixes: `_config_drift` path→HERE/installed.json; `EventLedger.last_failed_fingerprint` implemented; the 5 settings.json hooks hand-edits folded into `registration.build_hooks` (verified: build_hooks('claude') regenerates all 18 events incl WorktreeCreate/Remove + narrowed matcher + tui; **codex output unaffected**). Data-loss footgun closed.
- **Skills**: 85 live-only vendored — 30 first-party, 54 `external/` (origin preserved), crypto-ctf STRIPPED (313MB .venv + RsaCtfTool gone), `DEPLOYED-MANIFEST.json` (85 entries, installs_hook flags), design-review-loop marked superseded by design-studio, `learned` skipped.
- **Hooks**: 4 wired-but-unversioned artifacts (local-tui-reminder, workflow-monitor-autolaunch, create/remove-worktree.ps1).
- **MCP**: canonical reconciled up to live (+agent-mail/biomni-hub/angr, −exa/tavily/firecrawl/figma-rest); playwright `playwright-mcp`→`@playwright/mcp` + Kaggle `API_TOKEN`→`USERNAME+KEY` in BOTH ~/.mcp.json (backed up) and canonical.
- **gitleaks CLEAN**: 4 findings all verified SYNTHETIC (test_security_regressions.py PRIVATE_BODY_SENTINEL + parametrized fakes; workflow-monitor "FAKE credentials for redaction tests" fixture; c2patool `private_key: es256_private.key` = a filename). Added `.gitleaks.toml` allowlist 3 for these paths → re-scan 0.

## Method note (reusable)
4 parallel Opus subagents (file-ops only, NO git — orchestrator holds all git for scoped adds): harness-fix, skills-enshrine, mcp-reconcile + a python-reviewer. Each verified DIRECTLY in the worktree (git status/numstat, test run, build_hooks probe) — never trusted self-cert. Scoped `git add` per area (never -A); 364 A + 7 M (7 M = exactly intended). Windows-git `autocrlf=true` produces phantom-M on content-identical LF files — they resolve to no-op on commit; `git diff --numstat` distinguishes real vs EOL.

## NEXT (this session or after restart)
- python-reviewer (harness fixes) running → address findings.
- Task 8 ENFORCE: canonical_config_edit_guard gate (modules.py, shadow-first) + deploy-harness step in install.py + basic-memory nudge + RECONCILE-LOG.md + CI exclude-guard job.
- Task 9: codex-native features (configurable model/effort/skills/MCPs/tools + verbose monitor + how-to doc) + /self-reflect.
- **Blocked-on-restart**: MCP user-scope promote (`promote-mcp-userscope.ps1 -PruneExtraUserServers`) needs Claude fully CLOSED; a restart also activates the new 900k auto-compact window. Push of the branch awaits user approval.

Relations:
- continues [[config-drift-audit-auto-compact-fix-2026-07-13]]