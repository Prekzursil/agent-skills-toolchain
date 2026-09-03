# MCP / Tool inventory + dedup map (2026-09-03)

Machine-wide inventory of MCP servers, agent tools, and skill roots across C: and
D:, with per-item canonical-home decisions. Generated during the 2026-09-03
ZCode-SSOT + cyberstrike reconcile session. Refresh by re-listing the roots below.

## Roots

| Root | Role |
|---|---|
| `tools/mcp/*` (this repo) | **SSOT source** for first-party MCP tools |
| `C:\Users\Prekzursil\.agents\skills` | **SSOT vault** for skills (358; ZCode/Claude read natively) |
| `skills/`, `.agents/skills/` (this repo) | Repo mirror of the skill vault (deploy target lineage) |
| `C:\Users\Prekzursil\.local\opt\*` | Deployed Python tool runtimes (venv installs) |
| `C:\Users\Prekzursil\AppData\Roaming\npm\*.cmd` | Deployed npm tool shims (27 MCP-related) |
| `D:\opt\cyberstrike-mcp` | CyberStrike engagement kit — deployed runtime |
| `D:\opt\{bolt,cs-tools,metasploit*,sliver,search-hub-pr310}` | D-side runtimes/data |
| `D:\tools\*` | Standalone tools (llama-cpp, mcp-manager, reframe, apk workflow…) |
| `C:\Users\Prekzursil\.codex\mcp-wrappers` | Codex-side stdio wrappers (kaggle) |
| `tools/mcp/cyberstrike-mcp-kit` (this repo) | **SSOT source** of the engagement kit (added 2026-09-03) |

Doctrine: **repo = source, the rest = deployed runtimes.** A tool appearing in both
a repo path and `.local\opt`/npm/`D:\opt` is NOT a duplicate unless the non-repo
copy has drifted (uncommitted local edits). The registry
(`.agents/agents.json`, 56 servers) names the runtime path each entry launches.

## Duplicate / reconcile matrix

| Tool | Repo source | Runtime(s) | Decision (2026-09-03) |
|---|---|---|---|
| hexstrike-ai | `tools/mcp/hexstrike-ai` | `.local\opt\hexstrike-ai` (venv) | Keep pattern; verify runtime matches repo (orphaned server process killed 03.09; auto-start reviewed) |
| mcp-http-host | `tools/mcp/mcp-http-host` | `.local\opt\mcp-http-host` | Keep pattern (host infra, deployed lineage) |
| nuclei-mcp | `tools/mcp/nuclei-mcp/server.py` | kit `.cmd` → launches repo server.py directly | Single source already; kit cmd is a thin launcher ✔ |
| github-security-mcp, cve-mcp, osint-mcp-server, firecrawl-mcp, hacktricks-mcp-server | none (upstream npm packages) | npm global shims + kit `node_modules` copies | Upstream packages, not first-party: runtime-only is correct. Kit keeps its own node_modules (excluded from repo) |
| cloud-audit-mcp | **none** | `.local\opt\cloud-audit-mcp` (bun src) | ⚠ source lives only in opt — candidate to move into `tools/mcp/` (pending; registry entry `cloud-audit` points here) |
| biomni-hub | none (repo has `tools/mcp/cloud-hub` broker suite) | `.local\opt\biomni-hub` | Related but distinct layers (hub client vs cloud-hub broker); document-only |
| glm53-space | `tools/mcp/glm53-space` | `.local` uv-run from repo path | **DEPRECATED 2026-09-02** (registry disabled 03.09); removal awaits D1-D13 replacement wave |
| sliver / sliver-mcp | none | `.local\opt\sliver` (→ D:\opt\sliver), `.local\opt\sliver-mcp`, kit scripts | Engagement runtime; source upstream (BishopFox); no repo tracking needed |
| mitmproxy-mcp | none | `.local\opt\mitmproxy-mcp` | Runtime-only (registry entry `mitmproxy`) |
| mcphub | none | `.local\opt\mcphub` | Runtime-only; zcode entry holds an inline bearer token — stays zcode-local, never enters the synced registry |
| cyberstrike kit | `tools/mcp/cyberstrike-mcp-kit` ✔ (36 files) | `D:\opt\cyberstrike-mcp` (renamed from `cs-mcp` 03.09) | Source now tracked; D:\opt stays deployed runtime (node_modules/logs excluded) |
| kaggle wrapper | none | `.codex\mcp-wrappers\kaggle_mcp_stdio.py` (registry `kaggle`, disabled) | Runtime-only; single copy |

## Skills SSOT (no action needed)

ZCode, Claude (`.claude\skills` junction chain), and Codex all resolve to the
`~\.agents\skills` vault; the repo `skills/` + `.agents/skills/` mirror carries the
lineage (sync-shared-state enforces). `.grok\skills` is grok-local; duplicates of
vault skills there are grok-managed (parked set `mcp-grok-parked_2026-08-27.toml`).

## Space actions taken (2026-09-03)

C: was at 7.6 GB free. Moved (not deleted) to `D:\relocated\2026-09-03\`:
Temp big items (~24 GB incl. cursor WAL/auth-probe scratch), `.claude` finished-wave
artifacts (rf-w4/w5/w6, scratch, harness-restore, salvages ~6 GB), agent-worktrees
untouched >14d, file-history/jobs >30d, old deploy backups/logs, Goose installer
duplicate. uv cache cleaned (~2 GB). See session report for Downloads/Cowork
options (owner decision required — personal/project data).
