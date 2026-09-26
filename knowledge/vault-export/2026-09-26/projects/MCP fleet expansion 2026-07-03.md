---
title: MCP fleet expansion 2026-07-03
type: note
permalink: main/projects/mcp-fleet-expansion-2026-07-03
tags:
- mcp
- cloud-hub
- social-hub
- gitlab
- fb-messenger
- schrodinger
- openmm
- figma
- preservation
---

Big MCP consolidation+expansion, 2026-07-03 ("this session owns MCP"). All on branch `feat/cloud-hub-mcp` (agent-skills-toolchain, PUSHED to origin — strict superset of `feat/social-hub-mcp`).

- **cloud-hub** (`tools/mcp/cloud-hub/`) — 227 tools, 7 platforms (RunPod/Azure/GCloud/Kaggle/rclone/Modal/Lightning), lazy name-preserving multiplexer, 0 collisions. Reusable `tools/mcp/_shared/accounts.py` multi-account+cycling (env-mode + az/gcloud cli-profile). accounts.json gitignored. **+Lightning upgrade (commit 768e125): `lightning_studio_switch_machine` + `lightning_studio_upload_file` (progress_bar=False for stdio safety), cache regen 7→9, tests green.**
- **social-hub** (`tools/mcp/social-hub/`) — 88 tools, IG(insta-mcp private-API)+FB(fb-messenger)+TikTok+WhatsApp behind one lazy multiplexer. Sole collision `search_messages`→fb_/wa_. **IG/FB "best-of-both" = NO code dedup needed (surface already non-colliding); docs reconciled (commit c182352): README 60→88/fb 5→33, personal(insta private-API)-vs-business(fb ig_graph_*) IG map, FB E2EE-DMs + fbreels-is-now-an-MCP.**
- **gitlab** — 170-tool GitLab MCP (github-parity), user-scope; needs user PAT.
- **fb-messenger-mcp** (branch feat/instagram-parity-expansion) — Graph API + E2EE (fbchat-v2 AGPL Go bridge); FB_DM_PROXY scoped via _proxy_env(); E2EE needs `fr` cookie (missing).
- **openmm-md-mcp** — FREE Windows-native CUDA MD, deliberate LESSER alt to Desmond (Linux-only); env D:\micromamba\envs\openmm-md.
- **figma** (mcp.figma.com OAuth) + **figma-rest** (FIGMA_API_KEY=${FIGMA_ACCESS_TOKEN}) user-scope.

⭐ **Vendoring (commit 487c090):** 4 local-only-repo MCPs (fb-messenger/schrodinger/openmm-md/tiktok, NO remote = single-copy risk) vendored into `tools/mcp/` via `git archive` (secret-safe: only cookies.json.example template + loader code, no real secrets/venvs). PRESERVED; the CUTOVER (repoint backends.py + ~/.mcp.json, recreate venvs, restart) is the follow-up. teammateMode=auto. Program docs in ~/.claude/harness-gemhunt-2026-07-03/.