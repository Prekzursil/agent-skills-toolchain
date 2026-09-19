# Dual-config hunt — MCP definition files per runtime

**UNIT-COMPLETE: dual-config**
Date: 2026-09-04. Provenance: disk-verified (named files re-read; not the inventory digest alone).
No secret values. LITERAL-SECRET-PRESENT keys noted without values.

Goal: every MCP *definition* surface, not just the merge target. A surface can exist as a file even when it is not currently loaded.

SSOT registry: `C:\Users\Prekzursil\.agents\agents.json` (68 servers).  
`VALID_TARGETS` (`mcp_control_plane.py:15`): claude, codex, zcode, hermes. **Not** grok, cursor, goose, agy.  
`sync_shared_state.ps1` merges: Codex, Claude, Cursor, ZCode, then Hermes deploy. Native `integrations.enabled: []`.  
No `merge_generated_grok_mcp.py`.

## Table

| runtime | surface-1 (merge target / primary map) | surface-2 (second definition file) | extra surfaces | owner |
|---|---|---|---|---|
| **Grok** | `~\.grok\config.toml` `[mcp_servers.*]` — 22 names, 20 enabled. **No merge.** BM `http://127.0.0.1:8765/mcp`; agent-mail `:8812` **enabled=false**. | `~\.grok\installed-plugins\` — `registry.json` 34 plugin IDs; Grok-native `.mcp.json` MCP names **19** (context7, firecrawl, tavily, exa, discord, …). Independent of TOML. | (3) `[plugins].enabled` 44 entries in same TOML (hand). (4) `disabled_mcp_servers` array L1–19 (hand; conflicts with some `enabled=true` blocks: huggingface/notion/linear/brightdata). (5) parked `~\.agents\mcp-grok-parked_2026-08-27.toml` (not loaded). (6) `[claude_compat] imported=true`. | **hand** (config.toml) + **plugin** (marketplace `.mcp.json`). Not registry-merged. |
| **Claude Code** | `~\.claude.json` top-level `mcpServers` L6823 — **74** names. Merge writes this file (`merge_generated_claude_mcp.py`). Generated view 51; **23 hand extras** preserved (not in registry). | `~\.mcp.json` — **21** names. **Not** a merge target. 8 extras vs generated; 3 of those (brightdata, playwright-cdp, playwright-extension) are **absent from live `.claude.json`**. | (3) `~\.claude\settings.json` `enabledPlugins` (most false; true: codex, hookify, ralph-loop, remember, skill-creator, superpowers, claude-reflect, metaswarm, modern-web-guidance). (4) plugin cache `.mcp.json` (context7, cloudflare, notion, …) — **plugin**, loaded only if enabled. (5) `disabledMcpServers` array in `.claude.json` L7763 — **131** names; 55 of 74 live keys listed → UI-on ≈19. (6) `~\.agents\generated\claude.mcp.json` reference-only. (7) `~\.claude-runtime\local-mcp-marketplace\plugins\local-mcp-bridge\.mcp.json` **missing** (dir is README only; `sync_local_bridge_mcp.py` skips). | **merge** (51 registry) + **hand** (23 extras + `~\.mcp.json`) + **plugin** (skip-set `CLAUDE_PLUGIN_PROVIDED_SERVERS` + enabledPlugins). |
| **Claude Desktop** | `~\AppData\Roaming\Claude\claude_desktop_config.json` `mcpServers` — **burp only** (hand). | `Claude Extensions\` + `Claude Extensions Settings\` — MCPB installs (filesystem, windows-mcp, apify, boltz, docling, kubernetes, shadcn, pdf-filler, tooluniverse, desktop-commander, …). | Logs show many more named mcp-server-* (not definition files). Separate product from Claude Code. | **hand** + **plugin** (MCPB). Not in `sync_shared_state.ps1`. |
| **Cursor** | `~\.cursor\mcp.json` — **6** G-6 (agent-mail, basic-memory stdio shim, chrome-devtools, context7, firecrawl, playwright). Merge target (`merge_generated_cursor_mcp.py`). Cursor ∉ VALID_TARGETS; merge mirrors claude then parks to G-6. | `~\.cursor\settings.json` `plugins` — marketplace plugin enable-list including `tavily` L135, `mixpanel-mcp` L3, firecrawl/playwright/github/… **all `enabled: false`**. Not a second server map *today*, but it **is** a second MCP definition surface. Merge still skips `tavily` as `CURSOR_PLUGIN_PROVIDED_SERVERS` (comment claims plugin enabled — **stale** vs live false). | (3) `~\.cursor\plugins\marketplaces\**\mcp.json` / `.mcp.json` — cached plugin MCP defs (context-mode, conversational-analytics). Loaded only if plugin enabled. (4) `~\.agents\mcp-cursor-parked-31.json` — 32 keys, **not loaded**. (5) same-day `mcp.json.bak-*` held 13 (G-6 + 7 hubs) — history, not live. | **merge** (mcp.json G-6) + **plugin** (settings.json + marketplace cache; currently all off). |
| **Codex** | `~\.codex\config.toml` `[mcp_servers.*]` — **7** names. Merge replaces 4 registry (agent-mail, apify, basic-memory, github). Preserves 3 **local-only**: node_repl, cua_repl (disabled), mcphub. | `features.plugins = true` (config.toml:84) + `~\.codex\plugins\cache\**\.mcp.json` (openai-curated github/figma/build-ios-apps, claude-plugins-official cds-mcp/adobe, …). Plugin MCP defs exist; not the merge target. | (3) `~\.codex\mcp-configs\mcp-servers.json` — hand **template** (`YOUR_*_HERE`; includes retired stdio `memory`). Not live. (4) `~\.agents\generated\codex.config.toml` reference-only (4 HTTP). (5) profile tomls (`cursor`/`max`/`balanced`/`strict`) — **0** mcp_servers. | **merge** (4) + **hand/local-preserve** (node_repl, cua_repl, mcphub) + **plugin** (cache `.mcp.json` when plugins=true). |
| **ZCode** | `~\.zcode\cli\config.json` `mcp.servers` — **20** names. Merge target. 16 registry-targeted + 4 local-preserved. | Same file `plugins.enabledPlugins` — **9** official plugins. Plugin cache `.mcp.json`: android-emulator, ios-simulator, video2code (`runtime`), video-agent-kit (`video-edit`), mimosa, cloudbase-skills, document-skills. Third load path: plugin MCP, not the merge map. | (3) Native z.ai **inside surface-1** (also registry-targeted): web-reader, web-search-prime, zai-vision, zread. (4) Preserved local **inside surface-1**: node_repl, cua_repl, mcphub, **consult-offsec** (live-only; extra vs merge docstring trio). (5) `~\.zcode\v2\config.json` / `v2\setting.json` — **no** mcp keys. | **merge** (16 registry) + **hand/local** (4 leftovers) + **plugin** (enabledPlugins + cache `.mcp.json`). z.ai natives are merge-owned URLs, not a separate file. |
| **Hermes** | `%LOCALAPPDATA%\hermes\config.yaml` `mcp_servers:` L188 — **17 HTTP** (registry hermes targets). `deploy_hermes_mcp.py` (HTTP-only). | Vendor catalog `hermes-agent\optional-mcps\` (65 yaml) + `hermes-agent\plugins\` — **not** auto-merged into live unless listed in config.yaml. | Skills `/MIR` to `%LOCALAPPDATA%\hermes\skills`. Native `memory_enabled` + `memories\MEMORY.md` parallel to BM. | **merge** (17) + **vendor catalog** (optional-mcps; not live unless copied). |
| **Goose** | `%APPDATA%\Roaming\Block\goose\config\config.yaml` `extensions:` — BM + agent-mail HTTP plus bundled platform extensions. **No merge.** | XDG `~\.config\goose\config.yaml` (G-12 SSOT). Peer rest-lens: identical children; junction-vs-copy not proven. | Duplicate YAML keys for BM/agent-mail (`url:` then later `uri:`). Builtin memory extension **false**. | **hand**. goose ∉ VALID_TARGETS. |
| **Gemini / Agy** | `~\.gemini\settings.json` `mcpServers` — **33** (mostly stdio; includes `@modelcontextprotocol/server-memory` → `~\.gemini\memory.jsonl`). **No merge.** | `~\.gemini\config\mcp_config.json` **and** `~\.gemini\antigravity-cli\mcp_config.json` — same 3: agentchattr (disabled), chrome-devtools (disabled), monk (enabled). Dual copies. | Extensions `chrome-devtools-mcp`, metaswarm, superpowers (`gemini-extension.json` may carry mcpServers). No BM/agent-mail. | **hand** + **plugin/extension**. agy ∉ VALID_TARGETS. |
| **VS Code** | `%APPDATA%\Roaming\Code\User\mcp.json` `servers` — gallery + hand (markitdown, context7, playwright, github-mcp-server, chrome-devtools, serena, unity-mcp, firecrawl, desktop-commander, notion, sentry, BrowserStack, sonarqube, netlify, terraform, wallaby, datacloud_* …). | `%APPDATA%\Roaming\Code\User\mcp\` per-package `manifest.json` gallery cache. | `User\sync\mcp\` sync copy. Not Cursor; not in agents.json targets. | **hand** + **gallery**. |

## Intra-file duals (same file, two knobs)

| runtime | knob A | knob B | conflict |
|---|---|---|---|
| Grok | `[mcp_servers.X] enabled=` | top-level `disabled_mcp_servers = [...]` | huggingface, notion, linear, brightdata listed disabled **and** `enabled=true` in their tables. agent-mail/figma agree (both off). |
| Claude | top-level `mcpServers` (74) | `disabledMcpServers` (131) | 55 of 74 live keys also in the disable array → UI-on ≈19. Inventory `disabled: []` missed this array. |
| Cursor merge script | `CURSOR_PLUGIN_PROVIDED_SERVERS={"tavily"}` (skip because “plugin enabled”) | `settings.json` `tavily.enabled: false` | Stale skip: tavily is **not** live-mounted from either surface. |

## Port split (Grok vs rest)

Rail migrate 2026-09-04: BM `8765→18765`, agent-mail `8812→18812`.  
**Live Grok TOML still uses `:8765` / `:8812`.** Claude/Cursor/Codex/ZCode/Hermes/Goose live maps use `:18765` / `:18812`. Inventory.md L72 “Grok BM :18765” is wrong vs disk (`config.toml:307-315`); `inventory.json` memory.grok.url records `:8765`. TCP inventory: `:8765` closed, `:8812` closed, `:24680` open.

## Secrets (no values)

- LITERAL-SECRET-PRESENT key=`Authorization` in `~\.grok\config.toml` `[mcp_servers.mcphub.headers]`.
- LITERAL-SECRET-PRESENT key=`Authorization` in `~\.codex\config.toml` `[mcp_servers."mcphub"]` args (`mcp-remote` header). Same class as Grok mcphub. NEVER-ROTATE. Blast radius: those two files (+ backups).

## What is *not* a second live map

- `~\.agents\generated\*.mcp.json` / `codex.config.toml` — reference views (`publish_reference_views.py`).
- Cursor/Grok parked JSON/TOML — rollback snapshots.
- Codex `mcp-configs\mcp-servers.json` — template.
- ZCode `v2\config.json` — no MCP.
- Claude nested per-project `"mcpServers": {}` empties inside `.claude.json` (dozens) — not extra servers.

## Peer-lens alignment

- Grok dual **YES** (TOML vs plugin `.mcp.json`) — agrees `runtime-grok.md`.
- Claude dual **YES** (`.claude.json` vs `~\.mcp.json`) — agrees `runtime-claude.md`; this unit also lists plugins + `disabledMcpServers` + Desktop.
- Cursor: `runtime-cursor.md` says second-config **No** meaning no second *loaded* server map. This hunt still records `settings.json` plugins + marketplace `.mcp.json` as definition surfaces (all currently off).
- Codex: `runtime-codex.md` says no second live config file; this hunt records plugin-cache `.mcp.json` + unused template.
- ZCode: `runtime-zcode.md` says one MCP map; this hunt records plugin `.mcp.json` as a second definition surface, with z.ai + local leftovers **inside** the merge file.

UNIT-COMPLETE: dual-config
disk-verified: this file
