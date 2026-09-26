---
title: 'Compaction checkpoint: code-review + cookies + parallel-adoption 2026-07-24'
type: note
permalink: main/compaction-checkpoints/compaction-checkpoint-code-review-cookies-parallel-adoption-2026-07-24
tags:
- compaction-checkpoint
- cookies
- code-review
- git-crypt
- parallel-adoption
- agent-skills-toolchain
---

# Compaction checkpoint — session 5c615def (2026-07-24)

Long session, many workstreams. Current truth + the one launched background program.

## 1. LAUNCHED (background) — parallel 3-way adoption Workflow
- Run: `wf_a04df9d0-7bd` (task w1w3dkuic). Watch `/workflows` / `wfmon`.
- Script: `<scratchpad>/parallel_adoption.js`. Run root: `~/.claude/workflow-runs/parallel-adoption-2026-07-24/`.
- Lanes = workflow-harness / cyberstrike / hacktricks. Each reads a FROZEN prompt by path+hash from
  `~/.claude/workflow-runs/parallel-adoption-2026-07-24/prompts/final-*-prompt.md`
  (originals live at `~/source/databricks-fanout-harness/e2e/_E_promptsynth/results/`). shas: workflow c38cabd2, cyberstrike ac7162a8, hacktricks 01f896b8.
- Base = agent-skills-toolchain `origin/main` **7475ee7**. Worktree-isolated lanes → integrate shared files (canonical-mcp-servers.json, .mcp-disabled-defaults, AGENTS.md §9) → parallel final-verify.
- Owner decisions: **auto-merge-when-fully-green** (strict AND-gate) + **human-gates-hand-back**.
- HUMAN GATES the run CANNOT do (expect FAILED/UNVERIFIED + hand-back): CyberStrike install + operator `SAFE-TO-START:<commit>` + AGPL license decision; MCP user-scope promotion (needs ALL Claude closed); HackTricks rotated API key + corpus provisioning + Scheduled Task; any active security scope. Expect PARTIAL: 16-18K-word specs → focused PRs + honest receipts, not full completion in one pass.

## 2. Codex Cloud code-review — DONE (verified 72/72)
All 72 `Prekzursil/*` repos set to `review_preference=team · global_review_preference=review_everyone · code_review_trigger_policy=every_push · exhaustive_code_review=true` ("Review all PRs · On every push · Enabled"). Method that worked: phone ChatGPT cookies → bare Chrome (CDP :9333, temp profile) via `Network.setCookies` → page's own **PATCH `/backend-api/wham/settings/code_review`** (needs `Authorization: Bearer <accessToken from /api/auth/session>`; cookies alone 401). Bare Chrome :9333 still logged into Codex.

## 3. Cookie storage + git-crypt regression (ACTION PENDING)
- **git-crypt is DISABLED repo-wide** in agent-skills-toolchain: `filter.git-crypt.clean = cat` (identity, no encryption) though the key is present. So `tools/mcp/cloud-hub/accounts.json` (holds the live Databricks PAT in the working tree) is ONE `git add` from a PLAINTEXT commit. FIX before committing any secret: restore real filters (`git config filter.git-crypt.clean 'git-crypt clean'` + smudge + diff) — do it carefully (parallel agents active). My encryption gate caught this (blocked a plaintext cookie commit).
- Cookies meanwhile: DPAPI vault has `chatgpt-cookies.dpapi` + `aws-cookies.dpapi` (encrypted); **databricks cookies are plaintext-only** at `~/.crcp/cookie-bridge/databricks_cookies.json` (offer to vault). Landmine `tools/crcp/reports/*cdp_cookies*.json` now gitignored. Cookie-inject extension built at `~/.crcp/cookie-bridge/cookie-inject-extension/`.

## 4. Non-breaking cookie injection (research) — REPORT `~/.claude/cookie-injection-research-2026-07-24/REPORT.md`
Never write the Cookies SQLite. Chrome 127+ **App-Bound Encryption (v20)** = only the browser binary can produce valid cookie blobs; external writes fail the GCM auth-tag → row skipped → logout; browser also overwrites DB from its in-memory store on exit + holds an exclusive lock. Reliable = **browser extension `chrome.cookies.set()`** (no restart, no DB write, no logout) or CDP against a debug-port browser. cf_clearance/__cf_bm are device-bound (IP+UA+TLS) → can't transplant.

## 5. Browser main-profile wipe forensics (root cause CORRECTED)
NOT a direct-DB-write. `inject_all_main_profiles.py` (2026-07-20) force-killed browsers + CDP-injected 36 STALE phone ChatGPT cookies into the REAL profiles → overwrote the live-valid, ROTATING `__Secure-next-auth.session-token` with a dead Jul-20 copy → logout/login-loop. Disabled the latent re-breaker scheduled task **CRCPPhoneCookieReapply** (it targeted the durable profile :9340, not mains). ChatGPT now works. Only real collateral: Chrome dropped 5 of 6 Google accounts (owner chose to re-sign-in). Edge/Comet fine.

## 6. Parked / open loops (durable, not lost)
Interrupted PR-landing worktrees left untouched: `drift-wave2` (+7), `fb-parity` (+1), `lk-lane-ast` (+1), `aws-cloud-hub` (1 uncommitted). 47 uncommitted files on branch `fix/mcp-health-agentmail-fbmessenger` left as-is (do NOT `git add -A` — secret + entanglement risk).

Lesson: the honest, cited forensic code-read beat my initial plausible "direct-DB-write" inference — [[reference_databricks_auth_restore_2026-07-24]] neighborhood.
