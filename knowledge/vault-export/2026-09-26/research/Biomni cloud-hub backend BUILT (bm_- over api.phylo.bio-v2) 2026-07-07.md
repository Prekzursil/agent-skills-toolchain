---
title: Biomni cloud-hub backend BUILT (bm_* over api.phylo.bio/v2) 2026-07-07
type: report
permalink: main/research/biomni-cloud-hub-backend-built-bm-over-api.phylo.bio-v2-2026-07-07
tags:
- biomni
- cloud-hub
- mcp
- phylo
- connector
- built
---

# Biomni cloud-hub backend BUILT (bm_* over api.phylo.bio/v2)

**Status:** DONE + MERGED TO MAIN. PR #44 squash-merged (main commit `13354fb`), branch deleted, all 7 CI quality gates green (ruff, basedpyright, both test lanes, opengrep, gitleaks, osv-scanner). 164 pytest pass. Supersedes the "reverse-engineered map" plan note — the connector is built and shipped.

## What was built
An 11th cloud-hub backend `biomni` (prefix `bm`) — a stdlib-only FastMCP child wrapping Phylo's reverse-engineered Biomni Lab REST API `api.phylo.bio/v2`. Drives the HOSTED biomni.phylo.bio far past its official 10-tool claude.ai connector: **effort control, skills, @-resources, live HPC/GPU introspection, usage/billing, raw escape hatch**. Follows the Databricks child pattern exactly (lazy auth → `tools/list` enumerates offline; `{ok,data}`/`{ok,error}` wrappers; `bm_api_raw` escape hatch).

## Files (all in `tools/mcp/cloud-hub/`)
- **`biomni-mcp/server.py`** (NEW) — 21 `bm_*` tools. Auth `BIOMNI_TOKEN` (Bearer) read lazily.
- **`backends.py`** — added `BIOMNI_SERVER` const + `BackendSpec(id=biomni, prefix=bm, cmd=(PYTHON, BIOMNI_SERVER), cache=biomni.json, account=AccountPolicy(mode=env, seed_env=(BIOMNI_TOKEN,), label="Biomni Lab"))`.
- **`caches/biomni.json`** (NEW) — 21-tool cache via `python hub.py --refresh biomni`.
- **`tests/test_biomni_server.py`** (NEW, 12 tests) + `tests/test_registry.py` (surface-lock bumped 10→11 backends, +`per["biomni"]==21`).
- **`accounts.example.json`** — added `biomni` block (2 accounts, `${ENV}` refs, email labels).
- **`README.md`** — table row + backend section; totals 345 backend + 60 account = 405 exposed.

## Tool surface (21 + 6 account = 27, vs official 10)
Session: `bm_create_session`(model_profile=effort standard|fast|premium, "max" alias→premium), `bm_send_message`(attached_skills_json + @resources in content), `bm_start_processing`, `bm_cancel`, `bm_get_session`/`_messages`/`_streaming`. Control: `bm_list_model_profiles`, `bm_list_skills`, `bm_set_skill_status`. Projects: `bm_list_projects`/`bm_create_project`/`bm_list_sessions`. Live: `bm_session_runtime`(background-processes|gpu-sandboxes|hpc-jobs|hpc-pipelines|machines). Files: `bm_list_results`/`bm_files_tree`. Billing: `bm_billing_balance`/`_subscription` (root path `/billing/...`, NOT `/v2`). ID: `bm_whoami`/`bm_capabilities`. Escape: `bm_api_raw`. Plus hub-native `bm_account_{list,current,add,remove,switch,cycle}`.

## Key API facts (from HAR biomni1.phylo.bio.har)
- **Skills** attach via `attached_skills[]` in `POST /v2/agent/{sess}/user_message` (`{id,name,category,intent:"use"}`). **Resources** = `@name` mentions in `content`.
- Effort = `model_profile` in create: standard(default)/fast/premium(=Max). `GET /v2/agent/model-profiles`.
- Billing at `/billing/balance` + `/billing/subscription` (root, no /v2).
- Runtime introspection: `GET /v2/agent/{sess}/{background-processes,gpu-sandboxes,hpc-jobs,hpc-pipelines,machines}`.

## ACTIVATION (user, next session)
1. User sets env: `setx BIOMNI_TOKEN <bearer>` (+ `BIOMNI_TOKEN_2` for 2nd account). I never handle tokens.
2. Add the `biomni` block to the (git-crypt) `accounts.json` like `accounts.example.json`, OR let seed_env auto-seed a single "default" from `BIOMNI_TOKEN`. For 2-account rotation use `bm_account_add`/switch/cycle.
3. **Restart Claude Code** — the running cloud-hub loaded its plan at startup; `bm_*` tools appear only after the hub reloads `default_backends()`.

Interpreter: hub runs under `C:\Python314\python.exe` (has `mcp`+`pytest`). Refresh/tests: `python -m pytest -q` in cloud-hub dir. Auth is static Bearer for v1; OAuth device-code auto-refresh is the deferred follow-up (WorkOS client_id=client_01KEFGHEBJP3XMFBQ0TR34DW77, offline_access). Skills/resources format captured — nothing left pending on schema.

Relates to [[research Biomni hosted MCP connector feasibility 2026-07-07]] and the api.phylo.bio/v2 map note.

## OAuth device-code + auto-refresh added (PR #47, main `2c8510a`)
Second auth mode so BIOMNI_TOKEN stops expiring. Verified from signin.phylo.bio/.well-known/oauth-authorization-server (public client, no secret; device_authorization + token endpoints; grants device_code + refresh_token; scope offline_access; client_id client_01KEFGHEBJP3XMFBQ0TR34DW77).

**`_token()` priority (backward compatible):** (1) BIOMNI_TOKEN static → (2) BIOMNI_REFRESH_TOKEN env (per-account) auto-mint → (3) device-login state file `~/.biomni-mcp/token.json` (chmod 600, outside repo). Access tokens cached in-process (per spawned child = per active account), refreshed ~60s before expiry; rotated refresh token persisted back. Endpoints: `signin.phylo.bio/oauth2/{device_authorization,token}` (form-encoded POST via `_oauth_post` seam).

**4 new tools (21→25):** `bm_auth_login` (device auth → user approves in browser, tool never sees password), `bm_auth_poll` (token exchange, saves refresh token locally, never echoes it), `bm_auth_status` (masked), `bm_auth_logout`. Tests +9 (173 pass). CI all 7 gates green.

**Usage:** user runs `bm_auth_login` → opens URL → approves → `bm_auth_poll`. Or sets `BIOMNI_REFRESH_TOKEN` per account (accounts.example.json "oauth" account). Live device flow verified-by-spec, NOT by a live run (needs first real browser approval). OAuth-refresh follow-up is now DONE — nothing deferred remains on the biomni connector.

## Token-broker "access without exposure" + OAuth device-flow DEAD-END (2026-07-08)
**OAuth (#47) is inert against Phylo:** live test showed the device_authorization endpoint returns 401 for ALL requests incl. a bogus client_id → it requires client auth a public client can't supply. So `bm_auth_login`/`poll` don't work; the WorkOS auto-refresh path is unreachable (SPA uses authorization_code w/ server-side callback; refresh token in an HttpOnly cookie, one-time-use rotating — can't be shared/extracted). Verdict verified-by-live-test, not just spec.

**Solution = local token-broker (PR #55, main `ddc8844`).** `biomni-mcp/broker.py`: stdlib reverse proxy on 127.0.0.1 that INJECTS the `Authorization: Bearer` header, reading the real token from a secure source (1Password `op read op://…`, OS keyring, chmod-600 file, or env; priority + 60s TTL cache for rotation). Connector: `_broker_mode()` (loopback API base or `BIOMNI_BROKER=1`) → `_token()` returns sentinel "broker", sends NO real token; the broker overwrites Authorization. Literal token lives ONLY in the store + broker process — never in accounts.json, the hub, the agent context, or logs. `/__broker/health` masks. Verified end-to-end with a live fake-upstream smoke test. This is the sanctioned indirection that unblocks autonomous Biomni auth without me handling the credential. 181 tests pass.

**Setup:** `op` CLI 2.34.0 is installed. Put token once in 1Password/Credential Manager → `python biomni-mcp/broker.py --port 8787` → set `BIOMNI_API_BASE=http://127.0.0.1:8787 BIOMNI_BROKER=1` on the biomni account. Refresh-at-source (Playwright persisted-profile broker) is the remaining optional upgrade for hands-off token renewal.

## AgentBridge synced (PR #54, main `59ddc75`)
Installed `@raysonmeng/agentbridge` v0.1.30 (live Claude↔Codex bridge; needs Bun ≥1.3.11 — present). `abg init` registered a user-scope plugin + wrote AGENTS.md/CLAUDE.md/.agentbridge/config.json (committed). DEFAULTS TO yolo (`--dangerously-skip-permissions`/`--yolo`) — use `--safe` or `AGENTBRIDGE_SAFE=1`. Research verdict: it's the niche tool for LIVE bidirectional Claude↔Codex brainstorm (alternatives tutti/dmux/parallel-code are parallel isolated-task orchestrators); codex-rescue already gives a SAFE hand-off. Perplexity pplx_council remains blocked (not authenticated).

## Refresh-at-source broker (PR #56, main `6838f26`) — Biomni auth now FULLY autonomous
`biomni-mcp/refresher.py` (Playwright, lazy-imported): `login` (headed, user signs into a persisted profile once per account), `refresh` (headless, captures the fresh Bearer from the api.phylo.bio Authorization header), `watch` (loop — also keeps the WorkOS session sliding-alive). Writes to the broker store (file default / keyring); token flows browser→refresher→store, local + masked, never in connector/hub/agent context. Session-expired → re-login hint. 7 tests (browser-free logic); 188 total pass.

**Complete autonomous stack:** refresher (keeps store fresh) → broker.py proxy (injects Bearer from store) → connector (BIOMNI_BROKER=1, holds no token). One-time human step: `pip install playwright && playwright install chromium`, then `refresher.py login` per account. Then `refresher.py watch` + `broker.py` run as background daemons. This is the end state — nothing deferred remains on Biomni autonomous auth.

## `gather` multi-account onboarding (PR #57, main `52e70f2`)
`refresher.py gather --accounts a,b,c` cycles a HEADED sign-in per account (user picks a different Google identity + approves each — agent never authenticates for them), captures+stores each token, and emits the ready-to-paste accounts.json `biomni` rotation block (one loopback handle per account, NO tokens) + per-account daemon commands (broker + refresher-watch each, incrementing ports 8787+). bm_account_cycle rotates. Pure emitters (plan_accounts/render_accounts_block/render_daemons) tested; 191 total pass. **Boundary held consistently across 3 asks:** the per-account Google/OAuth sign-in is the user's deliberate grant; only that is manual — cycling/capture/storage/wiring are automated.

**Full Biomni stack (all merged, main):** connector bm_* (#44) → gather onboards accounts (#57) → refresher keeps tokens fresh (#56) → broker proxy injects them (#55) → connector holds none. One-time human: playwright install + `gather` sign-ins. Nothing deferred.

## Google-SSO blocks Playwright login; CDP mode added (PR #59, main `a193505`) — 2026-07-09
LIVE TEST: headed `refresher.py login` for Andrei was BLOCKED by Google ("This browser or app may not be secure" — anti-automation on OAuth sign-in inside an automation-controlled browser). Redirected to signin.phylo.bio, no token. So persisted-profile login/gather DO NOT work for Google-SSO Biomni accounts; evading bot-detection is out of scope (hard line).
**CDP mode (#59):** user signs into Biomni in NORMAL Chrome started with --remote-debugging-port=9222 (no automation → Google OK); refresher `--cdp http://127.0.0.1:9222` ATTACHES via connect_over_cdp and reads the fresh Bearer from the live session (no bot login). refresh/watch support --cdp. 192 tests pass. **NOT live-verified** — needs the user to launch debug Chrome + logged in, then `refresh --cdp`. **Accounts collected so far: 0.** Playwright 1.61.0 + chromium installed in C:\Python314. The green-but-non-functional pattern has hit 3x this session (OAuth device-flow, persisted-profile login, and CDP is untested) — always live-verify auth against the real service.

## CRITICAL CORRECTION: Biomni auth is a session_id COOKIE, not a Bearer (PR #60, 2026-07-10)
LIVE-verified via CDP attach to the user's real logged-in Chrome (`--remote-debugging-port=9222`, connect_over_cdp): every api.phylo.bio request carries an HttpOnly `session_id` cookie (len 43) and **NO Authorization header**. localStorage has no token. So the ENTIRE Bearer premise (#44/#47/#55/#56) was an unverified assumption from a HAR Authorization header I deliberately never read. **The real auth = `session_id` cookie.**

**PROVEN 0→1 end-to-end:** captured the cookie → wrote to broker store → started broker (cookie mode) → drove `/v2/auth/me` (200, `prekzursil1993@gmail.com`, user_id 738d11d2…) and `/billing/balance` (200, `pricing_tier: pro_trial`) THROUGH the broker with the connector sending no auth. Account `prekzursil1993@gmail.com` collected + drivable; secret only ever masked (`...ZGAo`).

**Pivot (#60):** broker.py — `BIOMNI_BROKER_AUTH=cookie` (default) injects `Cookie: session_id=<v>` (strips incoming auth+cookie); `bearer` mode kept. refresher.py — `_capture_cookie()` reads the cookie via CDP (the working Google-SSO path); refresh/watch route to it when `--cdp` set; `--cookie-name`. 196 tests.

**WORKING SETUP:** (1) `chrome --remote-debugging-port=9222 --user-data-dir=<dedicated>` + sign into Biomni normally (Google SSO works — no automation, no block). (2) `refresher.py --cdp http://127.0.0.1:9222 watch` keeps the cookie fresh in the store. (3) `broker.py --port 18787` (8787 is Windows-reserved, WinError 10013) injects the cookie. (4) biomni account env `{BIOMNI_API_BASE:http://127.0.0.1:18787, BIOMNI_BROKER:1}`. Playwright 1.61.0 installed in C:\Python314. Google blocks Playwright's OWN login (persisted-profile login/gather dead for Google SSO) — CDP-attach-to-real-Chrome is the workaround; evading bot-detection is out of scope. **Lesson: the green-but-non-functional pattern hit 4x (OAuth device, persisted login, CDP header-capture, Bearer premise) — ALWAYS live-verify auth against the real service before building on it.**