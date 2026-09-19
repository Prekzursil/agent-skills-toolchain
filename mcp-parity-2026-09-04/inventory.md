# MCP runtime parity inventory — 2026-09-04

Run id: `mcp-parity-2026-09-04`. Mechanical. No secret values.

## Registry (agents.json)
- servers: **68**
- observed targets: claude, codex, hermes, zcode
- grok in registry targets: **False**
- cursor in registry targets: **False**

Per-target enabled counts:
- `claude`: 51 enabled / 54 targeted
- `codex`: 4 enabled / 4 targeted
- `hermes`: 17 enabled / 17 targeted
- `zcode`: 14 enabled / 16 targeted

## Merge scripts present
- claude: YES
- codex: YES
- cursor: YES
- zcode: YES
- hermes: YES
- grok: NO
- goose: NO
- agy: NO

## Live surfaces (names only)
- Grok config.toml: 22 — agent-mail, apify, basic-memory, brightdata, cloud-audit-hub, cve-mcp-hub, deepwiki, fiddler, figma, firecrawl-hub, github, github-security-hub, hacktricks-hub, hexstrike-ai-hub, huggingface, linear, mcphub, notion, nuclei-hub, osint-hub, search-hub, semgrep-hub
- Grok disabled: agent-mail, figma
- Grok plugins (marketplace): 34 — astronomer-data, boltz, browser-use, carbone-skill, chrome-devtools-mcp, claude-code-setup, claude-md-management, claude-security, cloudflare, cockroachdb, code-modernization, code-review, code-simplifier, codex, codspeed, context7, convex, crowdstrike-falcon-foundry, crowdstrike-falcon-fusion, cwc-makers, dash0-agent-plugin, databricks, datarobot-agent-skills, deepeval, desktop-commander, discord, duende-skills, exa, explanatory-output-style, expo, firecrawl, superpowers, tavily, tinyfish
- Cursor mcp.json: 6 — agent-mail, basic-memory, chrome-devtools, context7, firecrawl, playwright
- Cursor extra vs G-6 core: (none)
- Claude generated view: 51
- Claude live top-level: 74
- ~/.mcp.json: 21
- Codex config.toml: 7 — agent-mail, apify, basic-memory, cua_repl, github, mcphub, node_repl
- ZCode cli/config.json: 20 — agent-mail, apify, basic-memory, bedrock-claude, biomni-hub, burp, consult-offsec, cua_repl, deepwiki, exa, github, kaggle, mcphub, node_repl, openaiDeveloperDocs, scholarly-access, web-reader, web-search-prime, zai-vision, zread
- Hermes config exists: True
- Goose config exists: True
- Gemini skills dir exists: True

## Hubs
- basic-memory: DOWN (HTTPError)
- agent-mail-health: UP (200)
- github-security-hub: DOWN (URLError)
- cve-mcp-hub: DOWN (URLError)
- osint-hub: DOWN (URLError)
- hexstrike-ai-hub: DOWN (URLError)
- firecrawl-hub: DOWN (URLError)
- hacktricks-hub: DOWN (URLError)
- nuclei-hub: DOWN (URLError)
- cloud-audit-hub: DOWN (URLError)
- semgrep-hub: DOWN (URLError)
- mcphub-sse: DOWN (HTTPError)
- fiddler: DOWN (URLError)
- auth2api: DOWN (HTTPError)

## TCP
- :8765: closed
- :8812: closed
- :8317: closed
- :24680: open
- :8868: closed

## Findings
- **GROK-NO-MERGE** (P0): No merge_generated_grok_mcp.py; grok is not a VALID_TARGET in mcp_control_plane.py
- **GROK-NOT-IN-AGENTS-JSON** (P0): agents.json mcp.servers has zero targets containing 'grok'
- **GROK-POLICY-REGRESSION** (P1): G-11/G-99 keepers were basic-memory+agent-mail; live grok config has extra: ['apify', 'brightdata', 'cloud-audit-hub', 'cve-mcp-hub', 'deepwiki', 'fiddler', 'figma', 'firecrawl-hub', 'github', 'github-security-hub', 'hacktricks-hub', 'hexstrike-ai-hub', 'huggingface', 'linear', 'mcphub', 'notion', 'nuclei-hub', 'osint-hub', 'search-hub', 'semgrep-hub']
- **GROK-AGENT-MAIL-DISABLED** (P1): Grok [mcp_servers.agent-mail] enabled=false
- **GROK-PLUGIN-MCP-SURFACE** (P0): Second MCP surface: 34 installed Grok plugins (marketplace), independent of config.toml mcp_servers
- **CURSOR-BM-STDIO-SHIM** (P2): Cursor basic-memory is x_cursor.stdio_bridge (bm_cursor_http_session.py), not raw HTTP
- **GROK-BM-RAW-HTTP** (P0): Grok basic-memory is raw HTTP to :18765; this session handshake failed (WorkerTransport streamable HTTP). Cursor needed a stdio shim for the same daemon.
- **BM-DOWN** (P0): 127.0.0.1:18765 TCP closed
- **ZCODE-SECOND-MEMORY** (P1): ZCode has C:\Users\Prekzursil\.zcode\cli\memories in addition to basic-memory HTTP — parallel memory store
- **CLAUDE-DOT-MCP-JSON** (P1): ~/.mcp.json extra vs generated Claude view: ['brightdata', 'cloud-hub', 'figma', 'playwright-cdp', 'playwright-extension', 'schrodinger', 'search-hub', 'social-hub']

## vs 2026-08-27 scorecard
- Cursor was 6 enabled; live is 6.
- Grok MCP was hand-maintained / parked to BM+agent-mail; live config has 22 plus plugin surface.
- sync_shared_state then: claude+codex+cursor; now also zcode+hermes; still **not grok**.

UNIT-COMPLETE: mcp-parity-2026-09-04
