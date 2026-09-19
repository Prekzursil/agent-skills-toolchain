# Cursor runtime MCP lens — 2026-09-04

**UNIT-COMPLETE: runtime-cursor**
Receipt: this file. Inventory claims re-read, then live mcp.json, merge script, parked catalog, BM shim, scorecard re-read.

## Surface counts
- Registry (`agents.json`): **68** servers. `cursor` is **not** a `VALID_TARGETS` member (`mcp_control_plane.py:15` = claude/codex/zcode/hermes).
- Merge: `merge_generated_cursor_mcp.py` **exists**; mirrors **claude** (`:373-378`), then parks to G-6. Docstring `:8-10` still says VALID_TARGETS `{claude, codex}` (stale vs control plane).
- Live (`~/.cursor/mcp.json`): **6 names, 0 disabled** — agent-mail, basic-memory, chrome-devtools, context7, firecrawl, playwright (`mcp.json:2-46`).
- G-6 core: same 6 (`CURSOR_DEFAULT_APPROVED_SERVERS` `:131-140`).
- SAFE_DEFAULT: G-6 ∪ `{glm53-space}` (`:147`). glm53-space **not live** (`agents.json:603-609` enabled=false, deprecated 2026-09-02).
- Parked catalog: **32** `mcpServers` keys in `mcp-cursor-parked-31.json` (file `_comment` still says 31).
- Inventory receipt: Cursor 6; extra vs G-6 **(none)** (`inventory.md:31-32`; `inventory.json:379-390`).

## 7 extra hubs — leftover, hand-edit, or later policy?
**Hand-edit of Hermes CyberStrike hubs, then later policy cleared it.** Not `--attach-all-safe`. Prompt “Cursor 13 / 7 extra” is **not live**.

Same-day backups still hold the 13-server state:
- `mcp.json.bak-park-hexstrike-20260904-165736:45-65`: G-6 + github-security-hub, cve-mcp-hub, osint-hub, **hexstrike-ai-hub**, nuclei-hub, cloud-audit-hub, semgrep-hub.
- `mcp.json.bak-20260904-222855:45-65`: G-6 + same except hexstrike-ai-hub replaced by **hacktricks-hub** (`:31415`).

Those hub names are registry **hermes-only** (`agents.json:1647-1776`, G-1 2026-09-03). `hacktricks-hub` is **absent** from `agents.json`. Merge default attaches only SAFE_DEFAULT (`:320-326`). Hermes hubs are governed-but-not-generated, so **both** default and `--attach-all-safe` drop them (`:346-365`: attach-all-safe keeps a live entry only if `name not in governed`). An `--attach-all-safe` leftover would look like parked-31 Claude names (apify, github, …). Live never had those today.

`sync_shared_state.ps1:186` runs merge `--write` **without** `--attach-all-safe` → SAFE_DEFAULT G-6 (`:46-55`). That is **later policy**, not leftover attach-all-safe.

## BM stdio shim — confirmed
**Yes.** Live `mcp.json:6-13` is `python.exe bm_cursor_http_session.py --stdio --url http://127.0.0.1:18765/mcp`. Registry `x_cursor.stdio_bridge` (`agents.json:790-798`). Renderer `:28-35,256-266`. Shim never binds/restarts `:18765` (`bm_cursor_http_session.py:6-8`). Contract SSOT remains HTTP `http://127.0.0.1:18765/mcp` (`memory-contract.md:10-11`); this is a Cursor HTTP session-refresh proxy, not a BM stdio spawn.

## hexstrike retired from Cursor — confirmed
**Yes.** Live has no hexstrike (`mcp.json` re-read). `CURSOR_RETIRED_SERVERS` = mixpanel, mixpanel-mcp, hexstrike-ai, hexstrike-ai-hub (`:120-127`); G-15/G-18 154-tool OOM park 2026-09-04. `hexstrike-ai` remains claude-targeted stdio in registry (`agents.json:555-561`) so `--attach-all-safe` would otherwise remount it; retired set blocks that (`:320-323`). Still in parked catalog as disabled (`mcp-cursor-parked-31.json:169-178`) — catalog only, not live.

## second-config
**No.** Single live MCP map: `~/.cursor/mcp.json`. Parked-31 is a rollback snapshot, not loaded. `settings.json` plugin enable-list exists (`mixpanel-mcp` L3, `tavily` L135) — both `enabled: false`. Not a second server map.

## memory path
Cursor → stdio shim → `http://127.0.0.1:18765/mcp`. Not `:8765`. Park bak had stale `:8765` / agent-mail `:8812`; live is `:18765` / `:18812`.

## vs 2026-08-27
- Then: 6 enabled, 0 disabled, 31 parked (`CROSS-RUNTIME-SCORECARD_2026-08-27.md:12,42`).
- Now: still 6 live (no count regression). Parked keys **32** (includes hexstrike-ai-hub). BM shim added (needed). hexstrike retired 2026-09-04. Transient same-day hand-edit of 7 Hermes hubs **cleared** by default merge. glm53-space listed in SAFE_DEFAULT but registry-disabled — not a live extra.

## Evidence (file:line)
- mcp_control_plane.py:15 VALID_TARGETS (no cursor).
- merge_generated_cursor_mcp.py:8-10,28-35,46-55,120-147,256-266,320-365,373-378.
- ~/.cursor/mcp.json:2-46 G-6 + BM shim.
- agents.json:555-561 hexstrike-ai claude stdio; :603-609 glm53-space disabled; :790-798 x_cursor.stdio_bridge; :1647-1776 hermes hubs.
- mcp-cursor-parked-31.json:169-178 hexstrike pair disabled.
- bm_cursor_http_session.py:6-8 never bind/restart :18765.
- sync_shared_state.ps1:186 merge --write (no --attach-all-safe).
- memory-contract.md:10-11 BM HTTP-only.
- CROSS-RUNTIME-SCORECARD_2026-08-27.md:12,42 Cursor 6+31.
- inventory.md:31-32,71; inventory.json:379-390,926-931.
- mcp.json.bak-park-hexstrike-20260904-165736:45-65; mcp.json.bak-20260904-222855:45-65.

UNIT-COMPLETE: runtime-cursor
