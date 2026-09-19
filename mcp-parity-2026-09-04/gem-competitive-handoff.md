# UNIT-COMPLETE: gem-competitive

Date: 2026-09-04. disk-verified. Full writeup: gem-competitive.md
Focus: native MCP managers vs this estate. NATIVE-vs-BUILD.
OAuth (Grok red auth required), plugin vs registry, one Grok SSOT merge.

## Live evidence (two signals)

- VALID_TARGETS = claude, codex, zcode, hermes (mcp_control_plane.py:15). agents.json has 0 grok and 0 oauth.
- sync_shared_state.ps1:179-216 merges Codex, Claude, Cursor, ZCode, Hermes. No Grok. No merge_generated_grok_mcp.py.
- Cursor ~/.cursor/mcp.json = 6 G-6 servers (agent-mail :18812, BM stdio shim :18765, chrome-devtools, context7 Bearer env, firecrawl Bearer env, playwright). Not 13 (that was a same-day backup).
- Grok config.toml:307-314 BM still http://127.0.0.1:8765/mcp; agent-mail :8812 enabled=false. Contract and merged runtimes use :18765 / :18812.
- Codex config.toml:54 mcp_oauth_credentials_store = keyring.
- Grok /mcps key i is native OAuth (07-mcp-servers.md:210,239-241).
- Grok compat.claude/cursor mcps default true (07-mcp-servers.md:224-235). Proof: disabled_mcp_servers lists Claude-only names (angr, excel, ralph-orchestrator) not in Grok's 22 TOML servers.

LITERAL-SECRET-PRESENT NEVER-ROTATE: grok mcphub.headers Authorization; codex mcphub mcp-remote Authorization; grok mcp_credentials.json access_token/refresh_token (cloudflare-api, cloudflare-bindings, cloudflare-builds, cloudflare-observability, exa, figma). Blast: those files plus bak.

Do not re-propose: 2nd orchestration runtime, Mem0/Graphiti, Cursor BYOK, OpenRouter MCP.
PLANNED-unbuilt: grok VALID_TARGET + merge_generated_grok_mcp.py.

## Findings

### 1. GROK-OAUTH-RED-AUTH-REQUIRED
- what: Red auth required is native OAuth (/mcps key i). URL-only remotes need browser grant. mcp_credentials.json already has 6 working OAuth clients.
- why-this-estate: TOML mounts github/notion/linear/huggingface without oauth tables. disabled_mcp_servers conflicts with enabled=true. Red UI is expected, not a merge bug.
- how: Keep url-only. Authenticate with i or disable. Do not stamp GITHUB_MCP_PAT onto Grok. Do not copy mcp_credentials.json into agents.json.
- source: 07-mcp-servers.md:210,239-241; config.toml:321-344
- value x effort: high x S
- NATIVE-vs-BUILD: NATIVE-use

### 2. SSOT-HAS-NO-OAUTH-SCHEMA
- what: Cursor auth object; Grok oauth* keys; Claude --client-id; Codex mcp login+keyring. agents.json is stdio|http + headers + x_codex.bearer_token_env_var only.
- why-this-estate: Notion/Linear already url + empty credentialNames (OAuth-ready). GitHub/HF/Apify are PAT. Naive Grok merge cloned from Codex would PAT-stamp OAuth remotes.
- how: Add authMode oauth|bearer|none before merge_generated_grok_mcp.py. oauth=url-only. bearer=${ENV} only.
- source: https://cursor.com/docs/mcp ; 26-config-reference.md:329-332; agents.json github:490-518 notion:800-815 linear:657-672
- value x effort: high x M
- NATIVE-vs-BUILD: BUILD schema so NATIVE OAuth can be selected

### 3. GROK-SSOT-MERGE
- what: Only unbuilt merge among in-use coding CLIs. Cursor is also not VALID_TARGET but HAS merge_generated_cursor_mcp.py.
- why-this-estate: G-11 keepers were BM+agent-mail. Rail migrate 2026-09-04 updated merged runtimes to :18765/:18812. Grok still dials closed :8765/:8812. That is the load-bearing reason, not more servers.
- how: VALID_TARGETS += grok. Codex-shaped TOML merge. BM http://127.0.0.1:18765/mcp raw HTTP. agent-mail :18812 enabled=true. Hard-pin [compat.claude] mcps=false and [compat.cursor] mcps=false or Claude 74 still appears. Plugin skip-set. oauth url-only. ${ENV} for mcphub. Wire sync_shared_state.ps1. Do not use Claude-compat ingest as fake SSOT.
- source: mcp_control_plane.py:15; sync_shared_state.ps1:179-216; mcp-grok-parked_2026-08-27.toml:1-5; config.toml:307-315; memory-contract.md:10-11
- value x effort: high x M (THE planned-unbuilt item)
- NATIVE-vs-BUILD: BUILD merge + NATIVE grok mcp doctor

### 4. PLUGIN-MCP-VS-REGISTRY
- what: Claude skip-set CLAUDE_PLUGIN_PROVIDED_SERVERS (9 names, mcp_control_plane.py:25-36). Cursor tavily skip is stale (plugin off). ZCode UI Configured vs Plugin. Grok 19 plugin MCP names, empty exact intersect with 22 TOML, functional dup plugin firecrawl OAuth vs firecrawl-hub :31414.
- why-this-estate: official_marketplace_auto_installed=true plus plugins.enabled 44 fights G-11.
- how: GROK_PLUGIN_PROVIDED_SERVERS from enabled plugin .mcp.json. Do not flatten plugins into agents.json.
- source: merge_generated_claude_mcp.py:27-31; merge_generated_cursor_mcp.py:110-113; 09-plugins.md:3,154
- value x effort: high x S-M
- NATIVE-vs-BUILD: NATIVE plugin surface + BUILD skip-set

### 5. GROK-COMPAT-MCP-DEFAULT-ON
- what: Grok scans ~/.claude.json and ~/.cursor/mcp.json unless [compat.x] mcps=false.
- why-this-estate: Merge that only rewrites [mcp_servers] still loads Claude 74. How G-11 keepers died.
- how: Pin both mcps=false. Keep skills/rules/agents compat on.
- source: 07-mcp-servers.md:224-235; 05-configuration.md:378-406; config.toml:1-19 vs 307+
- value x effort: high x XS (prerequisite to 3)
- NATIVE-vs-BUILD: NATIVE-use

### 6. ENABLE-DISABLE-KNOB-NOT-IN-SSOT
- what: Claude disabledMcpServers 131 including claude.ai connectors. Grok disabled_mcp_servers vs per-server enabled conflict. Cursor approvals gate attach-all-safe.
- why-this-estate: Sync that re-enables everything fights /mcp and /mcps.
- how: agents.json owns bodies. Native owns session on/off. Do not wipe disabled_mcp_servers.
- source: .claude.json:7763; config.toml:1-19 vs 307+; merge_generated_cursor_mcp.py:23-27,57-65
- value x effort: medium-high x S
- NATIVE-vs-BUILD: NATIVE enablement; BUILD do-not-clobber

### 7. CODEX-KEYRING-OAUTH-UNDERUSED
- what: keyring already on. github still GITHUB_MCP_PAT. mcphub still npx mcp-remote plus literal Authorization (Grok docs forbid that wrapper).
- why-this-estate: Same token class as Grok mcphub literal (two-file blast).
- how: Recode mcphub to url + bearer_token_env_var. Leave Codex github as PAT. Do not copy PAT onto Grok.
- source: .codex/config.toml:54,987-1015; 07-mcp-servers.md:168
- value x effort: medium x S
- NATIVE-vs-BUILD: NATIVE-use

### 8. GROK-MCP-DOCTOR-UNUSED
- what: grok mcp doctor --json diagnoses config and connectivity. grok inspect shows origin.
- why-this-estate: Closed :8765 survived rail migrate because sync has no Grok step.
- how: Fail-closed keeper probe in sync. Do not auto-restart daemons.
- source: 07-mcp-servers.md:127-131,370-375
- value x effort: medium x S
- NATIVE-vs-BUILD: NATIVE-use inside existing sync

### 9. ZCODE-NATIVE-AGENTS-MCP-JSON
- what: ZCode natively reads ~/.agents/mcp.json. Estate already built merge_generated_zcode_mcp.py.
- why-this-estate: zcode merge is DEDUP BUILT. integrations.enabled [] avoids agents__ prefixes.
- how: Keep zcode merge. Never enable integrations.enabled. No second live writer.
- source: https://zcode.z.ai/en/docs/mcp-services ; merge_generated_zcode_mcp.py:1-17
- value x effort: low-medium x do-not-rebuild
- NATIVE-vs-BUILD: NATIVE covered by BUILT merge

### 10. HOSTED-CONNECTORS-VS-HAND-FIGMA
- what: Grok __managed_gateway_connectors = figma, canva, heygen plus TOML figma enabled=false plus OAuth token plus Claude claude.ai Figma.
- why-this-estate: Three Figma paths vs G-11 hubs only.
- how: Pick one path. Do not add figma to agents.json grok targets.
- source: config.toml:428-433; .claude.json:7773+
- value x effort: medium x XS
- NATIVE-vs-BUILD: NATIVE-use

### 11. CURSOR-NATIVE-OAUTH-NOT-RENDERED
- what: Cursor HTTP/SSE is OAuth-capable (auth object). Live G-6 firecrawl/context7 use Bearer env keys.
- why-this-estate: Cursor merge has no auth renderer. G-6 survived approval-gating.
- how: Do not change G-6 this wave.
- source: https://cursor.com/docs/mcp ; ~/.cursor/mcp.json:24-34
- value x effort: medium x later
- NATIVE-vs-BUILD: NATIVE exists; BUILD later if SSOT must project auth

### 12. DEFERRED-CATALOG-VS-SURFACE-SIZE
- what: Grok already search_tool/use_tool. Claude Tool Search. Cursor loads all tools (hexstrike OOM -> CURSOR_RETIRED_SERVERS).
- why-this-estate: Miss is Grok surface size (20 extra TOML + 19 plugin MCP + Claude-compat 74) while keepers are wrong-port/disabled. Not a new router.
- how: Shrink via findings 3-5 and 10. Leave Cursor G-6. Do not remount hexstrike.
- source: 07-mcp-servers.md:215-218; merge_generated_cursor_mcp.py:120-127
- value x effort: high x follows 3-5
- NATIVE-vs-BUILD: NATIVE catalog; BUILD shrink connected set

## Sequence

1. NATIVE now: pin [compat.claude] mcps=false and [compat.cursor] mcps=false. Disable non-keepers. Fix agent-mail URL then enable. NEVER-ROTATE.
2. NATIVE now: /mcps i or drop OAuth remotes. No PAT on Grok github.
3. BUILD planned-unbuilt: grok VALID_TARGET + merge_generated_grok_mcp.py + skip-set + authMode + BM/mail :18765/:18812 + env mcphub.
4. NATIVE in sync: grok mcp doctor --json fail-closed on keepers.
5. Do not: second control plane, flatten plugins, integrations.enabled, copy mcp_credentials.json, Cursor BYOK, OpenRouter MCP, Mem0/Graphiti.
