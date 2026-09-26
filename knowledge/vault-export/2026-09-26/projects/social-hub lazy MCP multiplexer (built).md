---
title: social-hub lazy MCP multiplexer (built)
type: report
permalink: main/projects/social-hub-lazy-mcp-multiplexer-built
tags:
- mcp
- social
- harness
- lazy-proxy
- ram-reduction
---

# social-hub lazy MCP multiplexer (built 2026-07-03)

Lazy, NAME-PRESERVING MCP hub fronting the 4 social backends + fb-reels behind ONE MCP slot. Extends `~/.local/opt/mcp-shims/lazy_proxy.py` (single-child) to N children. BUILT + TESTED, NOT yet wired into live config (orchestrator wires later).

## Location & launch
- Built in the git repo (NOT `.local/opt/mcp-shims/` which is non-git): `C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/social-hub/` (canonical, committable, next to existing `tools/mcp/fb-reels-uploader/`). Branch `feat/social-hub-mcp`, commit a5bcd1b.
- Launch (stdio, stdlib-only Python): `C:\Python314\python.exe C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\social-hub\hub.py`
- Modes: runtime (default) · `--refresh [ids]` (regenerate caches) · `--print-plan`.

## Mechanism
- initialize + tools/list served from committed `caches/*.json` (lazy_proxy shape) with ZERO backends spawned. tools/call resolves owner, lazy-spawns ONLY that child once, forwards. Children inherit os.environ (session/cookies/IG_APP_VERSION/proxies pass through). Fail-safe: broken backend => clear per-tool isError, hub never crashes.
- 60 tools = insta 36, tiktok 9, fb-messenger 5, whatsapp 7, fb-reels 3.

## Collision map (only one)
`search_messages` in BOTH fb-messenger + whatsapp => exposed as `fb_search_messages` / `wa_search_messages`. All other 58 keep EXACT original names. Non-colliding tiktok_* etc untouched.

## Per-backend enumeration facts
- tiktok (keyless FastMCP) + fb-messenger (no startup auth) + fb-reels: enumerate offline via `--refresh`.
- insta: auths at startup; session.json was valid so live refresh got real 36-tool schemas.
- whatsapp: connects/QR at startup => CANNOT enumerate offline => hand-authored static cache (7 tools from src/mcp.ts); degrades gracefully on call.

## fb-reels wrapper
`tools/mcp/fb-reels-uploader/fb-reels-mcp.mjs` (MCP SDK 1.29 + zod, installed there; node_modules+package-lock gitignored). Refactored `fb-reels-upload.mjs` to export runBatch/waitForLogin/setAudience/uploadOneReel (main() guarded so import doesn't launch browser). Tools: fb_upload_reel, fb_upload_reels_from_folder, fb_reels_status. Non-blocking: returns jobId, poll status over `.fb-posted.json` + `.fb-reels-jobs.json`. One-time human FB login via the CLI first.

## Orchestrator wiring (later)
- ADD to ~/.mcp.json: `social-hub` (command above). 
- REMOVE the 3 direct social entries it replaces: `insta-mcp`, `tiktok`, `fb-messenger`. (whatsapp + fb-reels were never registered — come free through the hub.)

## Tests (all pass)
10 pytest (registry collision/merge/routing + hub lazy-spawn integration w/ fake+broken backends) + `e2e_live.py` routed tiktok_trending through a live hub subprocess: 60 tools listed, 0 backends spawned on list, real trending JSON returned. Quality: ruff clean, bandit only 2 Low subprocess-launch (inherent to a launcher, same as lazy_proxy).

Relations: extends [[social_mcp_toolchain]], [[project_workspace_curation]] (MCP de-bloat), [[opus_clip_and_fb_reels_tools]] (fb-reels CLI origin).