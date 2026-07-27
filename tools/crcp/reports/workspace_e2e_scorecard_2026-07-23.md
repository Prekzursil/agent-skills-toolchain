# Workspace E2E Scorecard — 2026-07-23

**Generated:** 2026-07-23 18:00 UTC+3  
**Machine:** DESKTOP-A60S9GP / Prekzursil  
**Agent:** Antigravity (Gemini)  

## Overall Health

All three workspaces are **operational**. The agent-skills-toolchain repo is on the
correct branch (`fix/mcp-health-agentmail-fbmessenger`) with 9ec075d as a confirmed
ancestor of HEAD (55e2149). CRCP runtime shows all 4 auth rails GREEN (Codex, Databricks,
agent-mail, ChatGPT live bridge). The harness surface (.codex, .claude, .agents) is intact
with 353 total entries. Browser cookie injection succeeded 4/4 (Chrome, Edge, Comet, Firefox)
with WEB_SESSION_OK on all targets. The only non-green readyz gate is `poll_fresh` (the live
bridge poller hasn't run recently) and `lease` (not reported). 182 secrets inventoried and
DPAPI-vaulted with 100% round-trip verification.

## Per-Workspace E2E Scorecard

### WS1: agent-skills-toolchain

| Check | Result | Evidence |
|---|---|---|
| Repo/layout health | **PASS** | branch=fix/mcp-health-agentmail-fbmessenger, HEAD=55e2149, 9ec075d is ancestor, tools/crcp exists, 78 reports |
| Dirty tree | **WARN** | 35 files (24 untracked, 11 modified) — no secret-bearing files tracked |
| Remote sync | **WARN** | local is 16 commits behind origin/main, 0 ahead of remote branch (but remote branch tip 26be01d ≠ local 55e2149 — local has unpushed commits) |
| CRCP entrypoints | **PASS** | `python -m crcp --help` succeeds, CLI surface: version/auth/health/livez/readyz/chatgpt/bus/inbox/publish |
| Tests | **SKIP** | tests/ directory exists but not run in this evaluation |
| Inventory doc | **PASS** | auth_estate_inventory_2026-07-21.md exists (6,322 B) |

### WS2: CRCP Runtime / Cookie-Bridge Estate

| Check | Result | Evidence |
|---|---|---|
| Layout | **PASS** | ~/.crcp/ has browser-broker-profile + cookie-bridge with 6 subdirs |
| Cookie store | **PASS** | chatgpt_cookies.json: 27,574 B, 36 cookies, all critical cookies present |
| Apply state | **PASS** | status=WEB_SESSION_OK, ok=true, 36/36 injected with 0 failures |
| Session probes | **PASS** | /session: 200, hasUser=true, emailPresent=true · /me: 200, keys include email/name/country |
| CDP broker | **PASS** | Chrome pid=52380 on port 9340 LISTENING |
| Main-profile inject | **PASS** | 4/4 browsers: Chrome, Edge, Comet, Firefox all WEB_SESSION_OK |
| Session restore | **PASS** | All 4 browsers restored with backups, preferences_patched=true |
| Cookie expiry risk | **WARN** | 6 cookies EXPIRED (_cfuvid ×4, oai-gn, __Host-next-auth.csrf-token) — session tokens still valid |
| Databricks secrets | **PASS** | 3 profiles (315 scopes), 37 keys with values — all DPAPI-vaulted, 37/37 round-trip OK |

### WS3: Codex/Claude Harness Surface

| Check | Result | Evidence |
|---|---|---|
| .codex | **PASS** | 93 entries, auth.json present (4,941 B) |
| .claude | **PASS** | 222 entries, .credentials.json present (27,627 B) |
| .agents | **PASS** | 38 entries (shared control plane) |
| Codex auth | **PASS** | access_token JWT valid (TTL 144h, exp 2026-07-29), auth_mode=chatgpt |
| Codex id_token | **WARN** | EXPIRED 94.6h ago — identity-only, doesn't block API access |
| Agent private key | **PASS** | agent_identity.agent_private_key present (112 chars) |
| Claude credentials | **PASS** | 15 OAuth tokens (Figma, Supabase, Prisma, Daloopa, BioRender, Anthropic, xAI) |
| Grok auth | **PASS** | xAI auth present (882 B access token) |
| Databricks CLI | **PASS** | v1.7.0, 3 profiles in .databrickscfg (bolt-datascience, bolt-common, bolt-geo) |
| Agent-mail | **PASS** | HTTP 200, status=ok |
| GitHub CLI | **PASS** | gh auth via .config/gh/hosts.yml present |
| SSH keys | **PASS** | 4 private keys (codespaces.auto, google_compute_engine, id_ed25519, lightning_rsa) |
| crcp livez | **PASS** | live=true, status=LIVE |
| crcp readyz | **WARN** | ready=false — poll_fresh=false (poller stale), lease=not_reported |
| crcp auth status | **PASS** | overall=GREEN, all 4 rails LOGGED_IN |

## Auth Planes Summary

| Plane | Status | Key Evidence |
|---|---|---|
| Codex (~/.codex/auth.json) | **GREEN** | access_token valid 144h, refresh_token present |
| ChatGPT web cookies | **GREEN** | 36 cookies, session-token + oai-is present, probe=200/hasUser |
| Databricks (3 workspaces) | **GREEN** | CLI v1.7.0, `secrets list-scopes` succeeds on all 3 profiles |
| Agent-mail (127.0.0.1:8812) | **GREEN** | HTTP 200 {status:ok} |
| Claude (.credentials.json) | **GREEN** | 15 OAuth tokens present |
| Grok (xAI) | **GREEN** | Auth present, 882 B access token |

## Secret Inventory

| Category | Count | Vault Container |
|---|---|---|
| Codex auth tokens | 4 | codex-auth.dpapi |
| ChatGPT web cookies | 31 | chatgpt-cookies.dpapi |
| Claude OAuth tokens | 19 | claude-credentials.dpapi |
| Databricks PATs | 3 | databricks-cfg.dpapi |
| Databricks workspace secrets | 37 | databricks/<profile>/<scope>/<key>.dpapi |
| Grok/xAI tokens | 2 | grok-auth.dpapi |
| SSH private keys | 4 | ssh-private-keys.dpapi |
| Environment service tokens | 76 | env-service-tokens.dpapi |
| git-crypt key | 1 | git-crypt-key.dpapi |
| **Total** | **182** | **46 containers** |

**Vault path:** `C:\Users\Prekzursil\.crcp\secret-vault\`  
**INDEX (metadata only):** `C:\Users\Prekzursil\.crcp\secret-vault\INDEX.md`  
**Protection:** DPAPI CurrentUser + ACL locked to Prekzursil only  
**Round-trip verified:** 46/46 containers decrypt successfully  
**Git-tracked secrets:** NONE (verified: no credential files in git ls-files)  

## Browser Residual Status

| Browser | Session Status | Procs | Notes |
|---|---|---|---|
| Chrome | **WEB_SESSION_OK** | 48 | CDP broker alive on :9340, Default profile, user=prekzursil1993@gmail.com |
| Edge | **WEB_SESSION_OK** | 80 | Default profile, CDP via junction |
| Comet (Perplexity) | **WEB_SESSION_OK** | 51 | Default profile, direct CDP |
| Firefox | **WEB_SESSION_OK** | 0 | k4cy1nuq.default-release, Selenium inject, not currently running |

All 4 browsers successfully restored after session kills. Session restore report confirms
backups created and preferences_patched=true for all targets.

## Top 5 Next Fixes (by owner value)

| # | Fix | Why | Effort |
|---|---|---|---|
| 1 | **Push local commits** to remote branch | HEAD=55e2149 but remote=26be01d — 4+ local commits not pushed, risk of loss | 1 min |
| 2 | **Fix poll_fresh / start live bridge poller** | readyz=NOT_READY blocks any automation that checks readyz; auth is green but poller is stale | 5 min |
| 3 | **Refresh expired cookies** | 6 cookies expired (_cfuvid, oai-gn, csrf-token) — session still works but Cloudflare may start challenging | 10 min |
| 4 | **Clean dirty tree** (35 files) | 24 untracked + 11 modified — risk of accidental `git add .` exposing desktop_cdp_cookies JSON | 5 min |
| 5 | **Rotate Codex id_token** | Expired 94.6h ago — not blocking API calls now but may break flows that validate identity claims | 2 min (re-login) |

> **No secrets appear in this file.** All values are in DPAPI-protected containers only.
> Scorecard generated 2026-07-23 18:00 by Antigravity E2E evaluation.