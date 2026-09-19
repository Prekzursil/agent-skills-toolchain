# Claude MCP surface — UNIT-COMPLETE: runtime-claude (2026-09-04)

Disk receipt. Counts from key-line grep + `inventory.json` name arrays (two probes).
Did not dump `.claude.json` bodies (headers/env). No secrets.

**Widest registered MCP names: YES.**
Live top-level **74** > Grok 22 (+34 plugins = 56) > `~/.mcp.json` **21** > ZCode 20 > Codex 7 > Cursor 6.
Peer counts from re-read `inventory.md:27-36` (not re-enumerated this unit).

**Second runtime surface:** Grok.
**Second-config:** YES — `C:\Users\Prekzursil\.mcp.json` (merge writes only `.claude.json`).

## Surface counts

| Layer | N | Evidence |
|---|---|---|
| generated `claude.mcp.json` | **51** | 51 keys `:3-413`; writer `publish_reference_views.py:45` |
| live `.claude.json` top-level `mcpServers` | **74** | object `:6823-7447`; 74 keys `:6824-7437` |
| `~/.mcp.json` | **21** | keys `:3-152` |
| mcp.json extras vs generated | **8** | list below |
| live extras vs generated | **23** | generated 51 ⊂ live 74 |
| mcp.json absent from live | **3** | brightdata, playwright-cdp, playwright-extension |
| registry claude-targeted / enabled | **54 / 51** | `inventory.md:12`; 3 parked `enabled:false` |

Name-OR grep on `.claude.json` returned **76** hits; **2** are `skillUsage` dupes (`qdx-rush:7541`, `figma:7613`) → **74** live MCP keys.

Generated 51: agent-mail, angr, apify, basic-memory, bedrock-claude, binary-ninja-mcp, browserstack, cheatengine, chrome-devtools, claude-code-mcp, cloud-audit, codacy, codecov, context7, cve-mcp, deepscan, deepsource, digitalocean, docker, excel, firecrawl, frida-mcp, ghidra-mcp, github, github-security, github_cli, hexstrike-ai, huggingface, ida-pro-mcp, linear, linkedin, mcp-graphql, mitmproxy, notion, nuclei, osint, pdf-reader, playwright, postgres, qlty, ralph-orchestrator, repomix, scrapegraph, semgrep, sentry, sonarqube, tavily, web-reader, web-search-prime, zai-vision, zread.

Live extras (23): McpHub, apktool-mcp, cloud-hub, codex, elevenlabs, fiddler, figma, figma-rest, gitlab, jadx-mcp, mcp-windbg, ocr-suite, openmm-md, paper-search, perplexity, qdx-rush, rdkit, schrodinger, search-hub, searxng, serena, social-hub, tooluniverse.

`~/.mcp.json` extras vs generated (8): brightdata `:113`, cloud-hub `:7`, figma `:26`, playwright-cdp `:104`, playwright-extension `:96`, schrodinger `:37`, search-hub `:57`, social-hub `:43`.

Parked (targeted, not generated): glm53-space `agents.json:609`, markitdown `:718`, meta-tool `:1121` — all `enabled: false`.
Plugin skip set: `mcp_control_plane.py:25-36`. gitlab is **not** in the 54 targeted list but **is** live `:6918`.
`VALID_TARGETS` includes claude (`mcp_control_plane.py:15`).
Sync still runs Claude merge (`sync_shared_state.ps1:64`).
Merge preserves non-registry live extras; pops registry names not in generated (`merge_generated_claude_mcp.py:104-119`).

## Detector miss — `disabledMcpServers`

Inventory `claude_live_top_level.disabled: []` only checked per-entry `disabled`/`enabled` flags.
Live array `.claude.json:7763-7895` has **131** names (`:7764-7894`).
**55/74** live keys appear there.
**19 UI-enabled:** agent-mail, basic-memory, bedrock-claude, cloud-audit, fiddler, figma, github, github-security, huggingface, linkedin, McpHub, mitmproxy, nuclei, osint, playwright, web-reader, web-search-prime, zai-vision, zread.

Registered width still Claude. UI-on native MCP (19) is slightly below Grok’s 20 enabled of 22.

## Memory path

HTTP `http://127.0.0.1:18765/mcp`
- generated `claude.mcp.json:18-21`
- live `.claude.json:6850-6852`
- contract `.agents/memory-contract.md:10-11`

Merge pops stdio `"memory"` (`merge_generated_claude_mcp.py:181`).
No second semantic writer in generated view.
Inventory BM hub DOWN; TCP `:8765` closed (contract port is **18765**, not 8765). Do not restart BM.
agent-mail live `:7108-7110` is `http://127.0.0.1:18812/mcp/`.

## vs 2026-08-27 (`CROSS-RUNTIME-SCORECARD_2026-08-27.md:10`)

- Then: Claude merge **40/40**, Gaps “None found”.
- Now: generated **51** (growth, not shrink). Completeness 51/54 only because 3 registry-disabled.
- **Regressions:**
  1. 23 unmanaged live extras vs SSOT 51
  2. mass `disabledMcpServers` so UI-on ≈19, contra scorecard “none”
  3. `~/.mcp.json` 8 extras not merged; 3 of them not even in live
  4. inventory skipped `disabledMcpServers`

UNIT-COMPLETE: runtime-claude
disk-verified: this file
