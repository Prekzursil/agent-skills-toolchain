# HERMES-HARMONIZATION_2026-09-03

**Status: COMPLETE (disk-verified).** Hermes Agent is now a first-class member of the
shared control plane. Grill decisions G-1..G-4 captured below; all changes verified by
live execution, not assertion.

## Grill decisions (owner-locked 03.09.2026)

- **G-1 MCP surface = HTTP hubs only (chosen).** Hermes gets registry servers that expose
  an HTTP endpoint: estate daemons + remote HTTP-native + cyberstrike mcp-proxy hubs.
  No stdio spawns from Hermes, ever (orphan prevention).
- **G-2 Orphan cleanup = aggressive reap (chosen).** Kill all dead-parented MCP processes
  except estate daemons (:8765/:8812/:8317/:4096/cc-529/live CLIs).
- **G-3 Skills = sync materialization (chosen over junction).** robocopy /MIR vault ->
  Hermes skills dir, wired into sync_shared_state.ps1.
- **G-4 Grok TUI = stays parked (timed out; safer default).** Unpark procedure: review
  `mcp-grok-parked_2026-08-27.toml`, convert entries to hub URLs, add `grok` to VALID_TARGETS
  in mcp_control_plane.py, add a merge step or extend deploy_hermes-style deployer.

## What changed (artifacts on disk)

1. `agents.json` — 61 -> 68 servers:
   - `VALID_TARGETS` extended in `scripts/mcp_control_plane.py`: now {claude, codex, zcode, hermes}.
   - `hermes` target added to: basic-memory, agent-mail, context7, deepwiki, exa,
     openaiDeveloperDocs, web-search-prime, web-reader, zread, firecrawl.
   - NEW hub entries (targets=hermes): github-security-hub :31410, cve-mcp-hub :31411,
     osint-hub :31412, hexstrike-ai-hub :31413, nuclei-hub :31417, cloud-audit-hub :31418,
     semgrep-hub :31419 (schema-normalized: tags/credentialNames/requiredEnv/label/singletonKey).
   - **Cyberstrike stdio->HTTP conversion (root-cause fix for orphan fleets):** the five
     registry entries that spawned a raw stdio process per Claude session (github-security,
     cve-mcp, osint, nuclei, cloud-audit) now point at their mcp-proxy hub URLs. This is the
     config-level fix for the "duplicated orphaned processes" symptom.
   - z.ai endpoints (web-reader/web-search-prime/zread): explicit
     `Authorization: Bearer ${ZAI_API_KEY}` header added (previously zcode-merer-injected only).
2. `scripts/deploy_hermes_mcp.py` — NEW. Idempotent deployer: agents.json -> Hermes
   `config.yaml` `mcp_servers:` (HTTP only, backup-first, manual entries preserved,
   SUCCESS: sentinel).
3. `scripts/sync_hermes_skills.ps1` — NEW. robocopy /MIR materialization of the skills
   vault into `%LOCALAPPDATA%\hermes\skills` (381 SKILL.md files verified).
4. `scripts/sync_shared_state.ps1` — extended with the two Hermes steps above.
5. Hermes `%LOCALAPPDATA%\hermes\config.yaml` — 17 mcp_servers deployed.
   Hermes `.env` — CONTEXT7_API_KEY, FIRECRAWL_API_KEY, ZAI_API_KEY added (values never logged).
6. Cyberstrike hub started: `D:\opt\cyberstrike-mcp\start-cyberstrike-mcp-http.ps1`
   (background supervisor; 9/10 fronts live — metasploit :31416 needs msf creds, intentional).

## Verification (live-measured 03.09.2026 ~19:2x)

- validate_mcp_control_plane: SUCCESS servers=68.
- sync_shared_state.ps1: full green run ending SUCCESS:shared-state-sync.
- Hermes MCP probe: 17/17 servers connect, 529 tools total
  (basic-memory 21, agent-mail 40, hexstrike 150, github-security 39, cve 41, osint 37,
  cloud-audit 38, firecrawl 26, semgrep 1, nuclei 3, context7 2, deepwiki 3, exa 2,
  openaiDeveloperDocs 5, web-reader 1, web-search-prime 1, zread 3).
- Orphans: 27 stray dead-parented processes killed (biomni x5, scholarly-access x4,
  bedrock-claude x2, zcode plugin fleet x16). Post-fix: 0 stray orphans; remaining
  dead-parented processes are the named daemons + hub supervisor children (by design).
- MCP handshake verified against cve-mcp-hub (JSON-RPC initialize 200 OK).

## Operational notes

- Hermes restart required for the new mcp_servers to load in a live session (no hot reload).
- The cyberstrike hub supervisor is demand-start; if ports 314xx are down, re-run
  `start-cyberstrike-mcp-http.ps1`. Hermes/Claude get a clean connect error, not orphans.
- Never re-add raw stdio cyberstrike entries for claude/hermes targets — that regenerates
  the orphan fleet (measured twice: 19 procs 2026-09-03 morning, 27 procs this session).
