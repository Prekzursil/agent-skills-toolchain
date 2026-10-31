---
title: MAX-EFFORT-PLUGIN-CLEANUP_2026-08-27
type: note
permalink: dqverify-repo-20261013/skills/openrouter-routing/max-effort-plugin-cleanup-2026-08-27
---

# Max Effort plugin cleanup (2026-08-27)

Date: 27.08.2026  
Follows: `MAX-EFFORT-PLUGIN-DIAGNOSIS.md` (Wave 0, read-only). This file is the **do** track.

Hard rules kept: no Cursor logout, no storage/cookie/auth wipe, no OpenAI API key / Override Base URL, no catalog cache wipe, no permanent deletes, remotes left installed, no git writes.

---

## What I changed

### 1. Backups (before any live edit)

Folder: `C:\Users\Prekzursil\.agents\backups\cursor-plugin-cleanup-20260827-041500\`

| File | Role |
| --- | --- |
| `settings.json` | Pre-edit copy of `~\.cursor\settings.json` (41 plugins, all false) |
| `mcp.json` | Pre-edit copy of `~\.cursor\mcp.json` (six always-on servers) |

No cache folders were moved. Nothing was permanently deleted.

### 2. Enable-map pins (live `~\.cursor\settings.json`)

Added explicit `"enabled": false` (same JSON shape as existing entries) for cache-only / missing-from-map suspects:

| Plugin id | Before | After |
| --- | --- | --- |
| `compound-engineering` | absent from map (cache present) | **pinned false** |
| `astronomer-data` | absent (cache present) | **pinned false** |
| `canva` | absent (cache present) | **pinned false** |
| `tavily` | absent (was last known-on; cache present) | **pinned false** |

Map size: **41 → 45**. Every entry is `enabled: false`. No `enabled: true` was invented.

Left **unpinned** (documented only):

- `continual-learning` — first-party; hook state at `~\.cursor\hooks\state\continual-learning.json` (`lastRunAtMs` present, `turnsSinceLastRun: 4`). Overlaps conceptually with basic-memory + `AGENTS.md`, but it is **not** proven to duplicate the vault and is **not** proven to be the Max Effort break. Not disabled.
- Bolt team ids still missing from the map (`comms-privacy-dev`, `analytics-engineering-tooling`, `micromobility-supply-chain-team`, `talent-management`, `central-fp-a`) — team override **NOT-CHECKED**; not in the requested pin list.

### 3. Dedup vs shared harness

- **Skills SSOT** remains `C:\Users\Prekzursil\.agents\skills` (materialized into `~\.claude\skills`). Vault has `playwright` / `playwright-interactive` / `firecrawl` skills. No vault folders named `compound-engineering`, `astronomer-data`, `canva`, `tavily`, or `continual-learning`. Those four marketplace packs stay **plugin-false**; they are not copied into the vault.
- **MCP SSOT for Cursor** remains the G-6 keep-list in `merge_generated_cursor_mcp.py` / live `mcp.json`: `agent-mail`, `basic-memory`, `chrome-devtools`, `context7`, `firecrawl`, `playwright`. Plugin ids `playwright`, `firecrawl`, `context7-plugin` were already false and stay false. Did **not** add plugin MCP (Canva remote, Tavily) into `mcp.json`. Did **not** add OpenRouter MCP. Did **not** re-enable `integrations.enabled` in `agents.json` (still `[]`).
- Parked 31 stay in `.agents\mcp-cursor-parked-31.json`, not in live `mcp.json`.

### 4. Cache

Three cache roots exist: `cursor-public`, `bolt-ai-marketplace-ai-marketplace-public`, `ai-marketplace-github`. `plugins\local` is empty.

Each of the four suspects has **one** unpacked hash under `cache\cursor-public\<id>\` only. Same ids are **absent** from the other two cache roots. **No true duplicate (same id+version in two roots) to move.** Catalog (~174 under `cursor-public`) left intact.

### 5. What was refused

- Entire `plugins\cache\cursor-public` catalog — marketplace index, not “174 installed plugins.”
- Anysphere remotes (`remote-wsl` 1.0.13, `remote-ssh` 1.1.14, `remote-containers` 1.0.39).
- AppData User settings / `state.vscdb` / cookies / auth.
- OpenAI / OpenRouter BYOK fields (none present; not added).
- Disabling `continual-learning`.
- Expanding Cursor always-on MCP beyond the six.
- Git writes.

---

## Harness verification (after `sync_shared_state.ps1`)

Ran `C:\Users\Prekzursil\.agents\scripts\sync_shared_state.ps1` because this track wrote under `.agents`. Result: **SUCCESS:shared-state-sync**.

| Check | Result |
| --- | --- |
| Skills resolve from `.agents\skills` | `.claude\skills.daily` → `.agents\skills`; `.claude\skills` → `.claude\skills.daily` |
| MCP registry | 40 servers; Claude targets 40; Codex targets 4; `integrations.enabled` still `[]` |
| Cursor MCP merge | `enabled=6` `parked_skips=31` `plugin_skips=1` (tavily) `denied_skips=2`; always-on set **not** expanded |
| `~\.cursor\mcp.json` | valid JSON; same six servers: agent-mail, basic-memory, chrome-devtools, context7, firecrawl, playwright |
| `~\.cursor\settings.json` | valid JSON; 45 plugin ids, all `enabled: false` |
| Codex top-level `model` | still `gpt-5.6-sol` |
| `[model_providers.openrouter]` | still present; used only via `[profiles.openrouter]`, not the default model |
| Anysphere remotes | still installed: remote-wsl 1.0.13, remote-ssh 1.1.14, remote-containers 1.0.39 |

### Remaining user click

**Restart the Cursor GUI** (this agent cannot restart it). New chat, then re-test Max Effort. Stale MCP tool schemas from the previous process will survive `mcp.json` / plugin-map edits until that restart.

---

## Second pass — recovery run, 27.08.2026 ~04:50 (UTC+3)

The first run was reported canceled; this pass recovered instead of redoing. Verified on disk: all four pins present in `~\.cursor\settings.json` (45 entries, valid JSON, all false); `mcp.json` still exactly the six servers; backups `cursor-plugin-cleanup-20260827-041500\{settings.json, mcp.json}` intact. Re-ran `sync_shared_state.ps1` (exit 0, `SUCCESS:shared-state-sync`; cursor merge enabled=6 / parked=31 / plugin_skips=1 / denied_skips=2) and re-confirmed Codex `model = "gpt-5.6-sol"` + `[model_providers.openrouter]` non-default (only via `[profiles.openrouter]`). The verification table above matches both runs. Note: the table itself appeared on disk between this pass's first read and its sync — the canceled sibling's write flushed late, consistent with this box's known transcript-flush lag; contents agree with independently measured state, so kept as-is.

Part B artifacts written this pass: `.agents\CURSOR-CUSTOMIZE-AUDIT_2026-08-27.md` (Customize inventory, MCP scope-collapse map, marketplace enumeration, tiered queue) and `.agents\CURSOR-MARKETPLACE-VISITED_2026-08-27.md` (visited-set: 25 Bolt ids @ rev edb0999…, 181 cursor-public ids).