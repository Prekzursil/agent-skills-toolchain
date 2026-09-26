---
name: tiktok-schrodinger-mcp-expansion
description: 2026-06-06 build session — TikTok MCP built (read-only public scraper)
  + Schrodinger MCP expanded to a full docking pipeline; the non-obvious gotchas of
  each
metadata:
  node_type: memory
  type: project
  originSessionId: 0d02c989-c946-4f88-98b0-1c889787bc73
permalink: main/claude-memory/root/project-tiktok-schrodinger-expansion
---

2026-06-06, on `agent-skills-toolchain` branch `feat/drug-discovery-stack`, two MCPs shipped. Non-obvious facts worth keeping:

**TikTok MCP** (`~/source/repos/tiktok-mcp`, git-backed local-only, no remote) — FastMCP over `TikTokApi==7.3.3`, registered user-scope as `tiktok` (✓ Connected). 9 read-only tools.
- **`tiktok_trending` works KEYLESS; everything else (user/hashtag/video/comments/search) bot-walls with `EmptyResponseException` until `TIKTOK_MS_TOKEN` is set** (the `msToken` cookie from a logged-in tiktok.com session — a nonce, NOT login). `TIKTOK_BROWSER=webkit` did NOT fix the keyless block — ms_token is the real lever. `TIKTOK_PROXY` only needed on datacenter/cloud egress.
- **TikTok-Api 7.x has NO generic video search** — `api.search` exposes `users` only. Video discovery = `tiktok_hashtag`/`tiktok_trending`. (Don't write a `tiktok_search(videos)` — it doesn't exist.) Verified by introspecting the installed lib, not memory.
- server.py has a tiny `.env` loader so the registered MCP picks up `TIKTOK_MS_TOKEN`/`PROXY`/`BROWSER` from a gitignored `.env` (NOT baked into `~/.claude.json`). ms_token stored gitignored; session cookies the user pasted were NOT stored.

**Schrodinger MCP** (`~/source/repos/schrodinger-mcp`) — expanded 9→12 tools: added `prepwizard`, `glide_grid`, `prime_mmgbsa`. Now a full in-server pipeline: prepwizard → glide_grid → ligprep → glide_dock → prime_mmgbsa → qikprop. Two gotchas found by a LIVE 3PTB run (not by compile/handshake):
- **`prepwizard` lives in `$SCHRODINGER/utilities/`, not the root** — `_driver()` now falls back to utilities/.
- **`ligprep` rejects an absolute `-omae`** ("not under the current working directory", esp. with an 8.3 `PREKZU~1` short path) → pass the **basename** + run in the output dir.
- **`glide_dock` needs `POSE_OUTTYPE poseviewer`** to emit the `*_pv.maegz` (receptor+pose complex) that `prime_mmgbsa` consumes; default output is `*_raw.maegz` (ligand-only).
- **Grid methodology:** centering on a co-crystal ligand's *coordinates* while the ligand stays in the receptor blocks the pocket → `NO GOOD POSES FOUND`. Use `glide_grid(ligand_molnum=N)` — it centers on AND excludes that molecule. Repo skill: `structure-based-screening`.
- qikprop_admet verified live on warfarin (rc 0, full ADMET CSV).

Both documented in `agent-skills-toolchain`: skills `tiktok-public-research`, `structure-based-screening`, updated `social-media-toolchain` + `schrodinger-maestro-driver`, `docs/social/TIKTOK-MCP.md`. Relates to [[social-mcp-toolchain]].