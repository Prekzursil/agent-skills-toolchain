---
title: social-hub lazy MCP multiplexer (built 2026-07-03)
type: config
permalink: main/projects/social-hub-lazy-mcp-multiplexer-built-2026-07-03
tags:
- mcp
- social
- lazy-proxy
- harness
- ram-reduction
---

# social-hub lazy MCP multiplexer (built 2026-07-03)

BUILT + TESTED + COMMITTED (feat/social-hub-mcp, commit a5bcd1b, NOT pushed, NOT wired to live config). Fronts 4 social MCPs + fb-reels behind ONE lazy, name-preserving MCP slot. Generalizes `~/.local/opt/mcp-shims/lazy_proxy.py` (single child) to N children.

## Location & launch
- Hub: `C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/social-hub/` (Python, stdlib only). NOTE: built in the git repo under tools/mcp/ (where fb-reels already lived), NOT the literal `.local/opt/mcp-shims/social-hub/` from the task — that path is non-git and the task required a commit. Orchestrator wires whatever launch path is reported.
- Launch: `C:\Python314\python.exe C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\social-hub\hub.py`
- Modes: runtime (default) | `--refresh [ids]` regen caches | `--print-plan` summary.

## Mechanism
- initialize + tools/list served from committed `caches/*.json` (lazy_proxy shape {initialize,tools}) with ZERO backends spawned. tools/call resolves owner, lazily spawns ONLY that child once (kept alive), rewrites collision-renamed name back to original, forwards, pumps response back. Children inherit os.environ (session/cookies/IG_APP_VERSION/proxies pass through). Fail-safe: broken backend => isError result for ITS tools only, hub never crashes.
- Files: backends.py (registry), registry.py (pure plan/collision), hub.py (io+refresh), e2e_live.py, caches/, tests/.

## Merged surface = 60 tools
insta 36, tiktok 9, fb 5, wa 7, fbreels 3. Sole cross-backend collision = `search_messages` (fb + wa) => `fb_search_messages` / `wa_search_messages`. Everything else keeps EXACT original name.

## Backends
- insta: `node .../insta-mcp/dist/index.js` (auths at startup; session.json fresh so live-enumerated real schemas)
- tiktok: venv python .../tiktok-mcp/server.py (keyless)
- fb: venv python .../fb-messenger-mcp/server.py (cookies; enumerates offline)
- wa: `node .../whatsapp-mcp/src/main.ts` (parked POC; QR at startup => STATIC hand-authored cache, degrades gracefully)
- fbreels: `node .../fb-reels-uploader/fb-reels-mcp.mjs` (NEW wrapper; SDK 1.29 + zod4; refactored CLI to export runBatch; non-blocking jobId + fb_reels_status over .fb-posted.json; FB profile pre-auth ONCE via CLI)

## Tests (all pass)
10 pytest (collision/merge/routing + lazy-spawn integration w/ fake+broken backends). e2e_live.py: routed tiktok_trending through live hub subprocess => real data, tools/list spawned 0 backends, call lazily spawned tiktok. ruff clean, bandit only 2 Low subprocess-launch (hardcoded registry, no shell=True; same as lazy_proxy).

## Orchestrator TODO (later)
ADD social-hub entry to ~/.mcp.json; REMOVE direct entries `insta-mcp`, `tiktok`, `fb-messenger` (now fronted lazily; wa+fbreels come free). Then restart CC.

Relates to [[social_mcp_toolchain]], [[project_unified_mcp_gateway]] (rejected name-mangling funnel), [[mcp_fleet_state]].
