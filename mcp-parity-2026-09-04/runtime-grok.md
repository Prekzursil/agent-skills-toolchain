# Grok runtime MCP lens — 2026-09-04

**UNIT-COMPLETE: runtime-grok**
Receipt: this file. Live `~/.grok/config.toml`, plugin registry, parked TOML, Grok MCP/plugin docs, control plane, agents.json, sync script, memory contract, 2026-08-27 scorecard, plugin `.mcp.json` files re-read this unit. No mcphub Authorization values copied.

## Surface counts
- `config.toml` `[mcp_servers.*]`: **22** names, **20** enabled, **2** disabled (`config.toml:307-419`).
- Marketplace plugin IDs: **34** unique keys (`installed-plugins/registry.json`).
- Plugin-provided MCP names (Grok-native `.mcp.json` `mcpServers`): **19**.
- `[plugins].enabled`: **44** entries (`config.toml:47-93`). `confidence` is enabled (L74) but not in the registry 34.
- Merge script: **NO** (`merge_generated_grok_mcp.py` missing). `sync_shared_state.ps1` grok hits: **0**.
- `VALID_TARGETS`: `{claude, codex, zcode, hermes}` — **grok absent** (`mcp_control_plane.py:15`).
- `agents.json`: **no** `grok` string (grep = 0). Registry targets observed: claude/codex/hermes/zcode only.

## Dual surface (config.toml vs marketplace plugins)
**YES — two independent MCP load paths.**

Surface 1 — user TOML: `07-mcp-servers.md:19` (`[mcp_servers.<name>]` in `~/.grok/config.toml`).
Surface 2 — trusted plugin `.mcp.json`: `07-mcp-servers.md:141` (plugin MCP in `grok mcp enable` discovery); `09-plugins.md:3,:154,:346` (plugin bundles MCP; trusted `.mcp.json` attaches like other MCP config).
Third (compat, not the dual-surface pair): Claude/Cursor/project `.mcp.json` (`07-mcp-servers.md:224-233`). `[claude_compat] imported = true` (`config.toml:422-423`).

**config.toml names (22):** agent-mail, apify, basic-memory, brightdata, cloud-audit-hub, cve-mcp-hub, deepwiki, fiddler, figma, firecrawl-hub, github, github-security-hub, hacktricks-hub, hexstrike-ai-hub, huggingface, linear, mcphub, notion, nuclei-hub, osint-hub, search-hub, semgrep-hub.
Disabled: **agent-mail** (`config.toml:312-315` `enabled = false`), **figma** (`:317-319`).

**Plugin IDs (34):** astronomer-data, boltz, browser-use, carbone-skill, chrome-devtools-mcp, claude-code-setup, claude-md-management, claude-security, cloudflare, cockroachdb, code-modernization, code-review, code-simplifier, codex, codspeed, context7, convex, crowdstrike-falcon-foundry, crowdstrike-falcon-fusion, cwc-makers, dash0-agent-plugin, databricks, datarobot-agent-skills, deepeval, desktop-commander, discord, duende-skills, exa, explanatory-output-style, expo, firecrawl, superpowers, tavily, tinyfish.

**Plugin MCP names (19, from `.mcp.json`):** browser-use, cloudflare-api, cloudflare-bindings, cloudflare-builds, cloudflare-docs, cloudflare-observability, cockroachdb-cloud, cockroachdb-toolbox, cockroachdb-toolbox-http, CodSpeed, context7, convex, desktop-commander, discord, exa, expo, firecrawl, tavily, tinyfish.

Exact name ∩ with config.toml: **empty**. Near-overlap: plugin `firecrawl` vs config `firecrawl-hub`.
`chrome-devtools-mcp` ships `gemini-extension.json` `mcpServers.chrome-devtools` but **no** `.mcp.json` (Grok plugin MCP is `.mcp.json` per `09-plugins.md:346`). Not counted in the 19.

## second-config
**YES.** The marketplace `.mcp.json` surface is a second MCP config, not generated from `agents.json` and not merged by `sync_shared_state.ps1`. There is no `merge_generated_grok_mcp.py`.

## Memory path
Grok BM is **raw HTTP**, not a Cursor stdio shim: `url = "http://127.0.0.1:8765/mcp"`, `type = "http"`, `enabled = true` (`config.toml:307-310`).
Contract SSOT is `http://127.0.0.1:18765/mcp` (`memory-contract.md:10-11`). **Port mismatch vs contract.** 2026-08-27 keepers also used `:8765` (`mcp-grok-parked_2026-08-27.toml:4`).
Inventory.md L72 claiming Grok BM `:18765` is wrong vs disk. `inventory.json` `memory.grok.url` correctly records `:8765`.

## agent-mail
`[mcp_servers.agent-mail] enabled = false` (`config.toml:312-315`), url `http://127.0.0.1:8812/mcp`. G-11/G-99 keeper is present but off.

## Grok absent from VALID_TARGETS
Four independent signals: (1) `mcp_control_plane.py:15` set has no grok; (2) `agents.json` grok = none; (3) `sync_shared_state.ps1` grok = none; (4) `merge_generated_grok_mcp.py` does not exist.

## vs 2026-08-27
Parked G-11/G-99 keepers were **basic-memory + agent-mail only** (`mcp-grok-parked_2026-08-27.toml:1-5`). Scorecard: hand-maintained, not in sync (`CROSS-RUNTIME-SCORECARD_2026-08-27.md:13`).
Live regressions: **20 extra** config servers beyond keepers; agent-mail disabled; 34 plugin IDs + 19 plugin MCP names; still no grok target/merge.
Restored into live config vs parked: huggingface, apify, figma, github, linear, notion, deepwiki, search-hub, fiddler, brightdata, plus new `*-hub` HTTP wrappers.
Plugin-side return of parked names: context7, firecrawl, tavily, browser-use.
Scorecard `[paths]` L239–240 stale; live `[paths]` is `config.toml:284-286`.
TCP not re-probed this unit; inventory receipt claims `:8765`/`:8812` closed, `:24680` open.

## Secrets
LITERAL-SECRET-PRESENT: `config.toml` `[mcp_servers.mcphub.headers]` key `Authorization` (value not echoed). Blast radius this lens: that file. NEVER-ROTATE.

## Evidence (file:line)
- config.toml:47-93 plugins.enabled; :284-286 paths; :307-310 BM raw HTTP :8765; :312-315 agent-mail enabled=false; :317-319 figma off; :358-361 mcphub sse :24680; :366-419 hubs; :422-423 claude_compat.
- 07-mcp-servers.md:19 TOML surface; :141 plugin MCP in enable/doctor; :224-233 compat merge.
- 09-plugins.md:3 plugin bundles MCP; :154 trusted `.mcp.json` attaches; :346 MCP servers = `.mcp.json`.
- Plugin examples: context7 `.mcp.json:2-5`; `firecrawl-grok-plugin-ba077673/.mcp.json:2-5`.
- mcp_control_plane.py:15 VALID_TARGETS (no grok).
- mcp-grok-parked_2026-08-27.toml:1-5 G-11/G-99 keepers BM+agent-mail on :8765/:8812.
- CROSS-RUNTIME-SCORECARD_2026-08-27.md:13 Grok MCP not fed from agents.json, not in sync.
- memory-contract.md:10-11 BM HTTP `http://127.0.0.1:18765/mcp`.
- inventory.md:27-31,66-72; inventory.json grok_vs_policy + memory.grok.url :8765.

UNIT-COMPLETE: runtime-grok
