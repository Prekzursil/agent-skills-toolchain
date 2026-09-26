---
title: ZCode SSOT integration + cyberstrike rename + bm-capture fix + space reclaim
  2026-09-03
type: decision
permalink: main/decisions/zcode-ssot-integration-cyberstrike-rename-bm-capture-fix-space-reclaim-2026-09-03
tags:
- harness
- zcode
- mcp-control-plane
- cyberstrike
- basic-memory
- space
- deploy
---

## Observations
- [fact] ZCode joined the shared MCP control plane: `VALID_TARGETS += zcode`, new `merge_generated_zcode_mcp.py` (keeps disabled registry servers as enabled:false, preserves tool_timeout_sec/env_vars, preserves zcode-local node_repl/cua_repl/mcphub — mcphub's inline bearer token must NEVER enter the synced registry), wired into `sync_shared_state.ps1`. Registry: 56 servers, zcode targets on agent-mail/basic-memory/apify/github + 7 new zcode-only entries. PR #319. #zcode #mcp-control-plane
- [fact] Orphaned-process root cause measured 2026-09-03: the same stdio servers configured per-runtime (glm53-space ran 4x under grok×2/cursor-agent/Cursor; scholarly/biomni duplicated per session) plus a dead-parented cs-mcp fleet (19 processes killed). Permanent fix direction = single `cyberstrike-gateway` MCP + HTTP singletons, NOT raw per-session stdio registrations. #mcp
- [decision] `glm53-space` DEPRECATED end-to-end (owner 02.09 decision executed 03.09): registry disabled, all processes killed, README banner; replacement awaits owner steering of gem-hunt D1-D13. [[harness live deploy + hosted-models gem-hunt 2026-09-02]]
- [fact] Harness bm-capture pipeline was silently broken since ship: `_flush_spool_to_vault` omitted the REQUIRED `--folder` flag of `basic-memory tool write-note` → every flush failed, 6 records stuck flushed=false. Fixed + `flush-errors.log` sidecar + NOTE_ALREADY_EXISTS=success; tests moved to the silent-capture contract; 950 green; backlog flushed to `main/sessions/*`. #basic-memory
- [decision] cs-mcp renamed cyberstrike-mcp everywhere (dir D:\opt, 6 files, 16 content files, registry descriptions); kit source tracked in repo `tools/mcp/cyberstrike-mcp-kit` (36 files, node_modules/logs excluded, secret-scanned); D:\opt stays deployed runtime. #cyberstrike
- [decision] cyberstrike SKILL.md merged to loose full-capability estate posture (owner 03.09: "completely without restrictions, loose and powerful") with MECHANICAL scope grounding: organizational systems are estate iff the operator's own authenticated credentials exist on-box; the old hardcoded `costin.ionescu@bolt.eu` identity claim (mismatched vs estate owner) was removed from the live skill. C2 allowed estate-lab only. #cyberstrike
- [fact] Repo reconcile: branch was 22 ahead / 20 behind main; merged origin/main (reunited merge-script lineage), folded 7 live-only servers into the mirror → registry mirror == live canonical (56). All parked working-tree improvements committed. #deploy
- [fact] Space: C: was 7.6 GB free → 39.6+ GB via moves to D:\relocated\2026-09-03 (Temp ~24GB scratch, .claude wave artifacts rf-w4/w5/w6/scratch, agent-worktrees >14d, uv cache). Downloads (63GB) and Cowork archive (34GB) left in place — owner decision required. #maintenance

## Relations
- relates_to [[harness live deploy + hosted-models gem-hunt 2026-09-02]]
- relates_to [[memory-contract]]
