---
title: home-configs
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/audit/home-configs
---

# Home-configs audit — `~/.agents` (agents.json, skills, secrets) and `~/.zcode`

Date: 2026-09-29. Auditor: subagent "Auditor: home-configs" (authorized private-estate VM, read-only).
Working dir: `C:\Users\prekzursil\.zcode\workspace\default`. All findings verified this session.

## Method / commands actually run

- Full read of `C:\Users\prekzursil\.agents\agents.json` (2621 lines) + `json.load` parse check → **valid JSON, 98 servers in `mcp.servers`, 46 enabled**.
- `out/audit/check_servers.py` (written this session, run with `C:/Python314/python.exe`): for every server — stdio command/arg/env absolute-path existence, PATH resolution (`shutil.which`), control-char scan of all strings, TCP connect probe of every `127.0.0.1` http/sse URL, requiredEnv/env `${VAR}` inventory.
- Cross-checks: `netstat -ano` port sweep; `reg query HKCU\Environment` and `HKLM\...\Environment`; `ls` of `D:\opt`, `D:\opt\cyberstrike-mcp`, `~\source\`, `~\source\agent-skills-toolchain\tools\{,mcp\}`, `.agents\secrets`, `.agents\skills` (418 dirs vs `skills-index.md` 413 entries); reads of `.agents\AGENTS.md`, `AGENTS-RUNTIME.md`, `state\mcp-supervisor.json`, `knowledge\{OPEN-LOOPS.md, MCP-UNIFICATION-CENSUS-2026-09-29.md, INVENTORY.md}`, `.agents\local.json`, `.zcode\v2\*`, `.zcode\cli\config.json`, `.agents\generated\claude.mcp.json`.

Caveat: two early heredoc probes were mangled by shell backslash handling; every number above comes from the script-file run (`check_servers.py`) or an explicit micro-test, which agree with each other.

## Context that reframes severity

`knowledge/MCP-UNIFICATION-CENSUS-2026-09-29.md` (same day) and `knowledge/OPEN-LOOPS.md` D-06/L-32/A-03 establish: the 2026-09-24 McpHub consolidation deliberately parked ~30 stdio servers as `enabled=false` ("consume via McpHub SSE :24680"), and McpHub restart-vs-retire is a pending owner decision (L-32, due 2026-10-04). Disabled-entry breakage below is therefore mostly *known*; **enabled**-entry breakage is not tracked anywhere (INVENTORY.md has zero mentions of the broken servers, despite AGENTS-RUNTIME.md §1d requiring the inventory register to track every MCP).

## Findings

### 1. HIGH — Enabled registry entries point at installs that do not exist on this machine

From `check_servers.py` output (all `ENABLED`):

| Server | agents.json | What is missing (verified) |
|---|---|---|
| `dbx-ai` | agents.json:1349-1372 | `C:\Users\prekzursil\source\agent-skills-toolchain\tools\mcp\dbx-ai\dbx-ai-mcp-server.py` — dir `tools\mcp\dbx-ai` absent (full `ls` of `tools/mcp/`); census calls it "BACKEND-ON-DEMAND (python child)" but there is nothing to start |
| `biomni-hub` | agents.json:1469-1493 | args[0] `...\biomni-hub-mcp\hub\server.py` absent — `hub\` contains only `.venv`, `__pycache__`, `adapters`, `features`, `tests` (`find … -name server.py` matches only venv site-packages). Half-finished install: venv exists, entrypoint never landed |
| `lifesciences` | agents.json:2535-2560 | `--directory C:\Users\Prekzursil\source\lifesciences-research` — dir absent from `ls ~/source/` (only Airline-…, Personal-…, agent-skills-toolchain, open-coscientist, repos) |
| `cursor-bridge` | agents.json:1774-1793 | args[0] `D:\opt\cursor-bridge\cursor_bridge_mcp.py` — `os.listdir('D:/opt')` has no `cursor-bridge` |
| `zai-lane-a` | agents.json:2364-2386 | args[0] `D:/bolt/enum/pulls/zai-entitlement-fuzz_2026-09-19/zai-anon-mcp.py` — `D:\bolt` does not exist (`ls /d/bolt` → No such file) |
| `breach-intel` | agents.json:2387-2407 | args[0] is control-char-corrupted (see #2) *and* the intended `D:\opt\breach-mcp` is absent, *and* the keys file `D:\bolt\credentials\breach-vendor-keys.json` from its description is on the missing `D:\bolt` |
| `burp` | agents.json:1526-1549 | command `C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot\bin\java.exe` missing (`C:\Program Files\Microsoft` does not exist; `where java` finds nothing) + args[1] `...\BurpSuite\mcp-proxy\mcp-proxy-all.jar` missing + SSE :9876 closed |
| `github_cli` | agents.json:509-543 | command `gh-cli-mcp` not on PATH (`shutil.which`/`command -v` both fail) |

Disabled-but-also-missing (lower priority, hub-moved residue per D-06): `kaggle` (venv python in `Downloads\bionlp` gone), `paper-search` (`D:/ReverseTools/...exe` gone), `deepscan` (env `DEEPSCAN_JAVA_BIN` → missing jdk-17; also requires `DEEPSCAN_CLI_JAR` which nothing defines).

### 2. HIGH — Literal backspace control characters corrupt paths in agents.json

`check_servers.py` control-char scan:
- `breach-intel.args[0]` = `'D:\\opt\x08reach-mcp\x08reach_intel_mcp.py'` — the author wrote single `\b` in JSON, which is a valid escape for backspace. The launch path can never resolve.
- Same corruption in `burp.description` (`D:\opt\x08urp\launch_burp_headless.ps1`) and `breach-intel.description` (`D:\x08olt\\credentials\x08reach-vendor-keys.json`).
This is a recurring authoring hazard for any path containing `\b`, `\f`, `\n`, `\r`, `\t` segments (`\bolt`, `\burp`, `\reach`, `\temp`…).

### 3. HIGH — Stale env vars: live environment no longer satisfies `requiredEnv` of enabled servers

`secrets/env-backups/2026-09-29/machine.env` (created today 15:53) holds **214** machine-scope vars (GITHUB_MCP_PAT, GH_TOKEN, MCPHUB_TOKEN, HUGGINGFACE_TOKEN, CONTEXT7_API_KEY, BRIGHTDATA_TOKEN, LINKEDIN_*, JUPYTER_TOKEN, SENTRY_*, DATABRICKS_*, JAVA_HOME, …). Live `HKLM\...\Environment` + `HKCU\Environment` + current process contain almost none of them (`env | grep -cE '^(GITHUB_MCP_PAT|MCPHUB_TOKEN|HUGGINGFACE_TOKEN|CONTEXT7_API_KEY|BRIGHTDATA_TOKEN|LINKEDIN_ACCESS_TOKEN|JUPYTER_TOKEN|GH_TOKEN)='` → **0**). Consistent with this VM being (re)provisioned today (`~/.zcode` tree created 12:26, `.agents` copied ~14:09) with the old machine's env not restored.

Enabled servers whose `requiredEnv` is therefore unsatisfiable (all verified `enabled=true` via json parse): `github` (agents.json:476-508), `github_cli` (:509), `context7` (:262), `huggingface` (:564), `brightdata` (:2159), `linkedin` (:669), `jupyter` (:2506), `McpHub` (:2472). Note the census separately records huggingface as AUTH-BROKEN (401) — here the var is not even set.

Also broken at the value level in `HKCU\Environment`: `FIRECRAWL_API_KEY_2` = literal unexpanded `${FIRECRAWL_API_KEY_2}` (self-referential placeholder), `TAVILY_API_KEY` and `TAVILY_API_KEY_2` = empty strings. `ZAI_API_KEY` is present (user scope) and the Z.AI zcode lane works (web-search-prime / web-reader / zread tools live in this session).

### 4. HIGH — McpHub lane is doubly dead (known decision + new auth loss)

`McpHub` (agents.json:2472-2505, enabled, 7 targets) → `http://127.0.0.1:24680/sse` closed (socket probe + netstat). The ~30 "parked-stdio-use-mcphub" servers all say "consume via mcphub SSE :24680". Restart-vs-retire is pending (OPEN-LOOPS L-32) — known — **but** `MCPHUB_TOKEN` no longer exists in live env (only in the machine.env backup), so even the restart branch of L-32 cannot authenticate without restoring env first. A-03 also records `RailHealthGuard` probing with an unexpanded `${MCPHUB_TOKEN}`.

### 5. MEDIUM — CyberStrike 311xx band down; documented launcher script does not exist

Socket probes (this session): :31110 github-security, :31111 cve-mcp, :31112 osint, :31113 hexstrike-ai, :31117 nuclei, :31118 cloud-audit, :31119 semgrep — **all closed**, for both the claude entries and the hermes `*-hub` twins (agents.json:1274-1327, 1634-1773 — 14 enabled entries on 7 dead ports). Only the gateway :31100 is listening. Today's census classified 31110-31117 as "HEALTHY-LOCAL-BAND (400=live)" and hexstrike/cloud-audit/semgrep as dead backends staged for owner — the band has since gone down wholesale. Additionally, every one of these entries' descriptions cites supervisor script `D:\opt\cyberstrike-mcp\start-cyberstrike-mcp-http.ps1`, which does not exist; `D:\opt\cyberstrike-mcp\` contains `cyberstrike-launch.ps1` instead — the documented recovery path is stale.

### 6. MEDIUM — biomni fleet down again

`biomni` http://127.0.0.1:7870 closed (agents.json:2408-2425, enabled; census says superseded by cloud-hub-first but still enabled); brokers :18787-18789 and Chrome CDP :9222 all closed, despite the census's "REVIVED-TONIGHT" — nothing kept them up. `biomni-hub` (stdio, enabled, zcode) would spawn but its `BIOMNI_API_BASE` :18787 backend is down and its `server.py` is missing (#1).

### 7. MEDIUM — `agent-mail` coordination bus down

agents.json:1210-1237, enabled, targets codex/claude/zcode/hermes → `http://127.0.0.1:18812/mcp/` closed. Nothing restarts it.

### 8. MEDIUM — Three drifting MCP config surfaces + schema debris in agents.json

- `mcp.servers`: 98 entries (current, edited today 17:33).
- `generated/claude.mcp.json`: 74 servers, mtime 2026-09-22 18:30 — a week stale; predates the 2026-09-24 STICKY notes visible in agents.json.
- `~/.claude.json`: 37 user-scope servers per the census — the surface Claude actually consumes.
- Stale top-level `mcpServers` key in agents.json (lines 2602-2620) holding only a divergent duplicate of `biomni` (older description, extra `registered-2026-09-20` tag) alongside schemaVersion-3 `mcp.servers` — legacy-schema residue that can mislead any consumer still reading the old key.
- `lastSync: 2026-06-15T14:35:24` (line 2600) — 3.5 months old.

### 9. MEDIUM — Supervision policy gaps

- `mcp.policy.toolAllowlist: ["*"]` (agents.json:23-25) + `approvalMode: "native"` (line 26) + the AGENTS.md contract "Start Claude Code in bypassPermissions" (C:\Users\prekzursil\.agents\AGENTS.md:11) ⇒ no tool-level gate anywhere in the MCP policy layer.
- `linkedin` (agents.json:669-707) is `enabled=true` while tagged `unapproved`, `default-off`, `owner-present-write` — the description says "Runtime approval … granted per session by the manager", but nothing in the config encodes or enforces that gate; the tags are inert metadata.
- Resource ceilings (`maxPrivateBytes`, agents.json:27) apply to spawned stdio servers only; the http/sse twins and hub entries (incl. the 7-clone hermes fleet on identical ports) carry no ceiling, and `duplicatePolicy: report-unless-exact-process-tree` (line 34) explicitly tolerates them.
- `state/mcp-supervisor.json`: `sessionId: "acceptance-20260711"`, `failures: {}`, `quarantined: []` — the supervision state has recorded nothing through the current outage of 20+ enabled endpoints.
- `knowledge/INVENTORY.md` (the §1d SSOT that must flag any MCP that disappears as UNEXPLAINED) contains no mention of dbx-ai, biomni-hub, McpHub, breach-intel, cursor-bridge, or lifesciences (grep returned nothing) — the register is not being maintained for the MCP fleet.

### 10. MEDIUM — Skills inventory drift

418 skill dirs on disk vs 413 entries in `skills-index.md` (regeneration stamp 2026-08-27; regenerator: `.agents/scripts/gen_skills_index.ps1`). Unindexed: `gcp-compute-foothold` (added 2026-09-29), `langfuse`, `run-taskwatch_monitor`, `crcp-health`, `synced`. `crcp-health` and `synced` have **no SKILL.md** (crcp-health holds only two monitor scripts; `synced` is a sync-artifact bucket dir) — pseudo-skills polluting the vault. No index entry points at a missing dir (that direction is clean).

### 11. LOW — Planned integrations never finished (deliberate, recorded)

- `integrations.enabled: []` (agents.json:7) — no integration ever enabled.
- `libgen` (agents.json:1860-1882) — explicit placeholder ("flips on if a package appears"; package verified absent 2026-09-21).
- `glm53-space` (agents.json:593-628) — DEPRECATED 2026-09-02 pending a "registry-driven model integration layer … build wave pending owner steering of D1-D13".
- `figma` gemini targeting "deferred to owner (B3)" (agents.json:2188).

### 12. LOW — Miscellaneous wiring risks

- `github` header (agents.json:505-507) is `"Authorization": "${GITHUB_MCP_PAT}"` with **no `Bearer ` prefix**, unlike context7/huggingface/zai entries and unlike the same server's override in `.agents/local.json` (`"Bearer ${GITHUB_MCP_PAT}"`). Copilot MCP expects a Bearer token.
- AGENTS.md contract states "Python is C:\Python314\python.exe" (AGENTS.md:10) but bare `python` resolves to `C:\Python312\python.exe` (3.12.10). Enabled servers launched with bare `python`: `video-agent-kit`, `zai-lane-a`, `breach-intel` — they run on 3.12, contradicting the stated toolchain.
- Secrets layout: `.agents/secrets/README.md` documents 3 items; the directory holds 16 (abliteration.env, civo.env, cs-api-cookies.txt, daria-codeg-token.txt, elevenlabs.env, figma-rest.env, zai-*.env/txt, cookie jars, env-backups). Plaintext is estate-permitted; the gap is that most of the layout is undocumented and `machine.env` (214 credentials) is a single ungoverned copy.

### Checks that passed (run this session)

- agents.json parses as valid JSON (98 servers, 46 enabled).
- Local services up: basic-memory :18765, jupyter :8888, cyberstrike-gateway :31100.
- Stdio targets present on disk: linkedin, scholarly-access (exe), open-coscientist-lit-review (venv python + server), video-agent-kit (server + plugin root env), meta-tool/qlty/deepscan wrapper scripts + tsx loader, `.codex\mcp-wrappers\kaggle_mcp_stdio.py`, `.cargo\bin\ralph.exe`, `.local\bin\{uvx,uv,markitdown-mcp}.exe`, `.local\opt\*` venvs (cheatengine, frida, ghidra, ida-pro, mitmproxy, angr).
- Z.AI zcode lane functional in-session (web-search-prime, web-reader, zread) with `ZAI_API_KEY` present.
- `.zcode` config itself is clean: `v2/setting.json` (zai individual-coding-plan, glm CLI provider), `provider_config.json` (GLM-5.3 / -Flash rules), encrypted `credentials.json` (enc:v1), `cli/config.json` enabling 6 official plugins (computer-use, android-emulator, ios-simulator, restore-legacy-sessions, video2code, video-agent-kit) — no dangling references found. `github` targets zcode but carries `x_zcode.enabled=false` (agents.json:502-504), which appears deliberate (Z.AI-lane tools are used instead).

### Not verified

- Whether `~/.claude.json`'s 37 entries carry inline tokens (census says "92 keys intact") — out of this lane's scope (.agents/.zcode only); the agents.json-side requiredEnv breakage stands regardless.
- Remote HTTPS MCP endpoints (context7, linear, notion, exa, deepwiki, brightdata…) were not probed — env staleness (#3) already makes the credentialed ones unusable.