# MCP Fleet Operational Triage — OFFLOAD-W2025

- **Date:** 2026-09-23
- **Host:** OFFLOAD-W2025 (Windows Server 2025 Datacenter 10.0.26100), user `prekzursil`
- **Scope:** READ-ONLY triage. No config edited, no service started/stopped, no install performed.
- **Config parsed:** `C:\Users\prekzursil\.claude.json` (268 KB; user-scope `mcpServers` = **88 servers**)
- **Evidence labels:** `VERIFIED` (exact path / command output / session signal) · `INFERRED` · `COULD NOT DETERMINE` (CND)
- **Secret policy:** no token/key/password value is printed anywhere below; only field *names* and presence.

---

## 0. Headline findings (read this first)

1. **The whole fleet is being launched at this cwd because the curation is bypassed by a path-case collision.** `VERIFIED`
   The 120-entry `disabledMcpServers` curation lives under the project key `C:/Users/Prekzursil` (capital **P**). The session's actual cwd is `C:\Users\prekzursil` (lowercase **p**, per the environment block), whose project key exists but carries **no** `disabledMcpServers` list. Windows treats these as the same directory; Claude Code treats them as **two distinct project keys**. Net effect: at this cwd nothing is disabled, so all ~88 user-scope servers are launched — which is why ~30-46 fail this session and why startup token cost is high. This is the same "`~/.mcp.json`/HOME-cwd loads as PROJECT scope — injection path" class the owner recorded in the 2026-09-19 estate audit.
   → **This single fix (apply the curation to the lowercase-`p` project key) saves more startup cost than any individual prune.**

2. **All 10 local HTTP MCP daemons are down** (`VERIFIED` — no listener on any port): basic-memory `:18765`, agent-mail `:18812`, McpHub `:24680`, biomni `:7870`, and the security cluster `github-security:31110`, `cve-mcp:31111`, `osint:31112`, `firecrawl:31114`, `nuclei:31117`, `cloud-audit:31118`. Ports are in the correct live `311xx` band (the dead `314xx` band was already re-pointed on 2026-09-19); the daemons simply are not running.

3. **~11 stdio servers point at files that did not survive the machine migration** (`VERIFIED` on-disk MISSING). One (`breach-intel`) has a **corrupted path** — a literal `\b` backspace control character (`0x08`) where `D:\opt\breach-mcp\...` was intended.

4. **`FIX-MCP-CURATION.py` no longer exists** anywhere on disk (`VERIFIED` — stale MEMORY.md reference). The live curation tooling is the **`promote-mcp-userscope.ps1`** script + **`mcp-fleet-curation`** skill + the **`~/.agents/agents.json`** canonical registry with its sync rails.

5. **basic-memory is registered but not actually installed** post-migration (`VERIFIED`): `~/.local/bin/basic-memory.exe` is a uv-tool trampoline whose target venv is gone ("uv trampoline failed to canonicalize script path"); `uv tool list` = "No tools installed". Its config dir `C:\Users\prekzursil\.basic-memory` is absent. The vault at `D:\basic-memory` is intact (**716 .md**, 713 already carrying `permalink:` frontmatter).

---

## Part 1 — Inventory & triage

### Summary counts (of 88 user-scope servers)

| Class | Count | Meaning |
|---|---|---|
| WORKING | 40 | Connected/usable this session (tools surfaced), incl. remotes that loaded but await OAuth |
| FIXABLE | 16 | Dead now, specific known fix restores it |
| DEFER | 23 | On-demand backend (RE/Docker/compchem/security-hub) — not a defect, just not running; incl. 3 CND verify |
| PRUNE | 9 | Dead migration casualty / duplicate / banned — removing reduces startup cost |

Transport split: **68 stdio**, **20 http/sse** (10 local-daemon + 10 remote).

### 1a. WORKING (40) `VERIFIED` via surfaced `mcp__<server>__*` tools this session

`annas-archive`, `arxiv`, `binary-ninja-mcp`, `browserstack`, `chrome-devtools`, `cloud-hub`, `codecov`, `crossref`, `deepscan`, `deepsource`, `digitalocean`, `excel`, `figma-rest`, `gitlab`, `linkedin`, `mcp-graphql`, `mcp-windbg`, `openalex`, `pdf-reader`, `playwright`, `playwright-cdp`, `playwright-extension`, `pubmed`, `qlty`, `repomix`, `scrapegraph`, `search-hub`, `searxng`, `sci-hub`, `sentry`, `social-hub`, `tavily`, `tooluniverse`, `video-agent-kit`, `zai-mcp-server` — plus remote connectors `brightdata`, `context7`, `figma`, `linear`, `notion` (loaded; some await OAuth `authenticate`).

Notes:
- `sci-hub` is mounted and connected, but the `scholarly-access` skill policy is **never call `mcp__sci-hub__*`** (quarantined). Consider PRUNE on policy grounds even though it "works".
- `scrapegraph`/`searxng`/`mcp-graphql` load but need their env (`SGAI_API_KEY` / `SEARXNG_URL` / `ENDPOINT`) to do real work.
- `binary-ninja-mcp` connects, but actual RE ops need the Binary Ninja app.

### 1b. FIXABLE (16) — dead now, specific fix

| Server | Transport | Purpose | State / evidence | Fix |
|---|---|---|---|---|
| **basic-memory** | http `:18765` | Semantic memory (keystone) | `VERIFIED` port not listening; pkg not installed (see Part 3) | Reinstall pkg + init `~/.basic-memory` + start HTTP daemon (Part 3) |
| **agent-mail** | http `:18812` | Claude↔Codex peer mailbox | `VERIFIED` port not listening | `Start-ScheduledTask MCPAgentMailSupervisor` (self-heals in ~10s) |
| **McpHub** | sse `:24680` | MCP multiplexer/hub | `VERIFIED` not listening; header `Authorization` set | Start the McpHub service |
| **github** | remote | GitHub Copilot MCP | `VERIFIED` session err 400 "Authorization header is badly formatted" | Owner fixes/refreshes the `Authorization` header (raw `${VAR}` hygiene). **Do not rotate** (§9) |
| **huggingface** | remote | HF Hub MCP | `VERIFIED` session err 401 AUTH_HEADER_REJECTED | Owner refreshes HF token header. **Do not rotate** |
| **web-reader** / **web-search-prime** / **zread** | remote (z.ai) | Z.AI web read/search/zread | `INFERRED` down (not surfaced); audit 2026-09-19 recorded z.ai trio shared credential **expired (401)** | Owner refreshes the z.ai credential |
| **codacy** | stdio npx | Codacy quality MCP | `VERIFIED` failed CONNECTION_CLOSED; `CODACY_*` env named | Verify tokens present at MCP-read scope / npx cold-start; re-probe |
| **codex** | stdio `codex mcp-server` | Codex fan-out rail (multi-AI mingle) | `VERIFIED` failed; `codex` resolves to a **systemprofile** npm path (`C:\Windows\System32\config\systemprofile\...\codex.CMD`) — suspicious | Repoint `codex` to the user-scope CLI / reinstall codex for this user |
| **cursor-bridge** | stdio py | Cursor bridge | `VERIFIED` script MISSING (`D:\opt\cursor-bridge\...`; `D:\opt` absent). Audit says re-vendored 2026-09-19 | Repoint config to the vendored copy |
| **dbx-ai** | stdio py | Databricks AI MCP | `VERIFIED` script MISSING (toolchain `dbx-ai\` dir empty). Audit says "A2 vendored" | Restore/repoint the vendored server |
| **breach-intel** | stdio py | Breach-intel OSINT | `VERIFIED` path CORRUPTED — `0x08` backspace in `D:\opt\...` → resolves to `D:\optreach-mcpreach_intel_mcp.py`; `D:\opt` absent | Fix JSON escaping to `D:\\opt\\breach-mcp\\breach_intel_mcp.py` **and** restore the file (else PRUNE) |
| **rdkit** | stdio py | Cheminformatics (RDKit) | `VERIFIED` venv MISSING (`source/repos/rdkit-mcp-server/.venv`) | Recreate the venv / reinstall |
| **elevenlabs** | stdio uvx | TTS | `VERIFIED` failed CONNECTION_CLOSED (uvx); needs API key | Provide key + uvx cold-start; else DEFER |
| **github_cli** | stdio `gh-cli-mcp` | GitHub via gh CLI | `VERIFIED` failed; `GH_TOKEN`/`GITHUB_MCP_PAT` named, not set in probe subprocess | Confirm PATH for `gh-cli-mcp` + token at MCP-read scope |

### 1c. DEFER (23) — exist but need their app/daemon; not defects (keep configured, load on demand)

**RE backends** (binary present, need GUI/server running) `VERIFIED` on-disk EXISTS, failed because backend off:
`cheatengine`, `frida-mcp`, `ghidra-mcp` (needs Ghidra `:8089`), `ida-pro-mcp` (needs IDA `:13337`), `hexstrike-ai`, `mitmproxy`.

**Docker-dependent** (need Docker Desktop running): `docker`, `postgres`, `sonarqube`.

**Local security cluster** `:311xx` (registry has these `enabled=false` by design — should be off unless an engagement needs them): `github-security`, `cve-mcp`, `osint`, `firecrawl` (local; distinct from the working claude.ai Firecrawl connector), `nuclei`, `cloud-audit`.

**Heavy/on-demand science & misc**: `biomni` (WSL2 gradio `:7870`), `biomcp` (uvx cold-start; dup of tooluniverse/pubmed), `qdx-rush` (uv `--locked`, compchem; script `VERIFIED` present), `open-coscientist-lit-review` (script present), `serena` (uvx-from-git cold clone).

**CND — on-disk present, not surfaced, no failure shown → verify next session**: `scholarly-access` (exe present), `semgrep` (exe present; audit moved it to native `semgrep mcp`), `ralph-orchestrator` (`ralph.exe` present).

### 1d. PRUNE (9) — dead casualty / duplicate / banned (removing cuts startup cost)

| Server | Why prune | Evidence |
|---|---|---|
| **paper-search** | Dead venv exe (`D:\ReverseTools\mcp\paper-search-mcp\...`); duplicated by `scholarly-access`/`pubmed`/`arxiv` | `VERIFIED` cmd MISSING |
| **perplexity** | Dead venv exe (`D:\ReverseTools\mcp\perplexity-web-mcp\...`); duplicated by `search-hub`/`tavily` | `VERIFIED` cmd MISSING |
| **ocr-suite** | Dead (`D:\mcp-servers\abbyy-...`); already parked in `.mcp-disabled-defaults.json` | `VERIFIED` cmd MISSING |
| **openmm-md** | Dead micromamba env; compchem, reinstall only on demand | `VERIFIED` cmd MISSING |
| **apktool-mcp** | Dead (`.local\opt\apktool-mcp-server` gone); RE, reinstall on demand | `VERIFIED` cmd+script MISSING |
| **jadx-mcp** | Dead (`.local\opt\jadx-mcp-server` gone); RE, reinstall on demand | `VERIFIED` cmd+script MISSING |
| **zai-lane-a** | Dead one-off artifact (`D:\bolt\enum\pulls\zai-entitlement-fuzz_2026-09-19\...`) | `VERIFIED` script MISSING |
| **angr** | Documented dead/parked ("verified dead 2026-07-18") in `.mcp-disabled-defaults.json`; disabled in every list | `VERIFIED` exe present but parked; failed this session |
| **claude-code-mcp** | Owner has a **standing `claude-code-mcp` ban** (delegate-primitive skill); already in disabled list | `INFERRED` (policy) |

**Top prune candidates by startup-cost saving** (each removes a failing launch + a catalogue entry): `paper-search`, `perplexity`, `ocr-suite`, `zai-lane-a`, `apktool-mcp`, `jadx-mcp`, `openmm-md`, `angr`, `claude-code-mcp`.
Caveat: with `ENABLE_TOOL_SEARCH=auto:5`, tool *schemas* already load on demand, so the dominant per-session cost is the **count** of listed/attempted servers. The largest single reduction is **Headline #1** (apply the existing curation to the lowercase-`p` cwd), which prunes the launched set to the owner's intended tier without deleting anything.

---

## Part 2 — The owner's existing curation tooling

### Where it lives / what it does / ready to run?

| Tool | Path | What it does | Ready? |
|---|---|---|---|
| **promote-mcp-userscope.ps1** | `C:\Users\prekzursil\.claude\hooks\mcp-userscope-sync\promote-mcp-userscope.ps1` | Promotes the canonical set from `~/.mcp.json → mcpServers` into **user scope** of `~/.claude.json`, so the fleet is drive/tree-independent. **Drift-safe by design**: edits only top-level `mcpServers` via a System.Text.Json DOM (preserves case-distinct project keys, `projects`, and per-project `disabledMcpServers`), backs up first, self-verifies, aborts on mismatch. Refuses to run while `claude` is open (in-memory clobber guard). | **NOT ready as-is** — its SSOT `~/.mcp.json` was **deliberately removed** on 2026-09-19 (audit decision D9, to kill the HOME-cwd injection path). `VERIFIED` `~/.mcp.json` absent. |
| **agents.json (canonical registry)** | `C:\Users\prekzursil\.agents\agents.json` (73 KB) | Current SSOT. Keys: `mcp` (`policy`/`supervision`/`servers` — **94 servers**), `mcpServers`, `syncMode: source-only`, `lastSync`, `lastSyncSourceHash`. Supersedes the `~/.mcp.json` flow. | Present; edited in-place per the 2026-09-19 audit |
| **sync rails** | `C:\Users\prekzursil\.agents\scripts\sync_shared_state.ps1`, `sync-rules.ps1` | Sync the canonical registry + rules out to the per-surface configs (claude/gemini/zcode/hermes). | Present |
| **mcp-fleet-curation (skill)** | `C:\Users\prekzursil\.agents\skills\mcp-fleet-curation\SKILL.md` | Doctrine: disable at **user scope** (`claude plugin disable <name>@<mkt> --scope user`), NOT the UI toggle (writes project scope, returns on cwd change). Park/restore MCP via `~/.mcp.json`↔`~/.mcp.disabled.json`. | Present (advisory) |
| **`.mcp-disabled-defaults.json`** | `C:\Users\prekzursil\.claude\.mcp-disabled-defaults.json` | "Two-Tier MCP" reference curation (Tier-1 always-on = tavily + github_cli; Tier-2 on demand). Own `disabledMcpServers` list + parked-dead notes (angr, etc.). | Present (reference) |
| **mcp_doctor.py** | documented `~/.local/opt/re-harness/mcp_doctor.py` (`status`/`audit`/`reap`) | Liveness table, drift audit vs budget manifest, registry-gated dup-killer (protects GUI IDA `:13337`). | **CND** — `~/.local/opt/re-harness` is **absent** at the documented path on this box; location did not survive migration or moved. |
| **FIX-MCP-CURATION.py** | — | Referenced in MEMORY.md ("--apply pending"). | **Does not exist** anywhere on disk (`VERIFIED`). Treat the MEMORY reference as stale. |

### ⚠ What would DESTROY the load-bearing enabled/disabled curation (flag)

- **PowerShell `ConvertFrom-Json` round-trip on `~/.claude.json`.** It throws on the case-colliding keys (`C:/Users/Prekzursil` vs `.../prekzursil`) and, with `-AsHashtable`, would **collapse one of the two project entries** — silently dropping a whole project's `disabledMcpServers` curation. Always edit via a case-preserving DOM (the promote script's System.Text.Json approach). Observed live this session.
- **Editing `~/.claude.json` while Claude Code is open.** A running session rewrites the file on exit and **clobbers** any external edit (the promote script guards against this; ad-hoc `sed`/`jq` edits do not).
- **Deleting a registry row expecting the surface to prune.** Audit 2026-09-19: "deleting a registry row does NOT prune materialized surfaces — fix URLs + sync FIRST, then hand-prune."
- **Wiping `disabledMcpServers`/`enabledMcpjsonServers` on a schema warning.** Owner rule (MEMORY): the enabled/disabled curation is load-bearing; schema warnings are not license to wipe it.
- **The safest curation move here is additive, not destructive:** copy the existing 120-entry `disabledMcpServers` from the `C:/Users/Prekzursil` project key onto the `C:/Users/prekzursil` (lowercase) key (Headline #1), rather than deleting servers from `mcpServers`.

---

## Part 3 — Recover the basic-memory service

### State (all `VERIFIED`)
- Vault `D:\basic-memory` intact: **716 `.md`** (713 already carry `permalink:` frontmatter). `.hf` cache = **14 GB** — this is the global HF model cache, **do not delete**.
- Config dir `C:\Users\prekzursil\.basic-memory` **absent** → no `config.json`, no `memory.db` (SQLite index), no `bm-http-server.ps1` launcher.
- Package **not installed**: `~/.local/bin/basic-memory.exe` is an orphaned uv-tool trampoline (target venv gone); `uv tool list` empty.
- Contract (`~/.agents/memory-contract.md`, SSOT 2026-08-28): transport is **HTTP `http://127.0.0.1:18765/mcp` only**; **never `uvx`/pip stdio spawn**; "do not restart the daemon unless the owner asks; never bind `:18765` yourself." (Config already correctly uses the HTTP URL.)

### Reconciliations (older docs vs current truth)
- The 2026-07-17 "re-add" note (`claude mcp add ... -- basic-memory mcp`, port **8765**) is **superseded**: `8765` is the dead old port, and stdio spawn is banned. Use the **HTTP daemon on 18765**.
- The `mcp-fleet-curation` skill's `:8765` / `bm-http-server.ps1` mentions are pre-migration; defer to the contract + WHERE-map (`~/.agents/memory-map.md`): config `~/.basic-memory\config.json`, index `~/.basic-memory\memory.db`, vault `D:\basic-memory`.

### Files needed in `C:\Users\prekzursil\.basic-memory` to initialize
1. `config.json` — projects map with `main → D:\basic-memory` and `default_project: main` (basic-memory writes this on first init).
2. `memory.db` — SQLite index, **rebuilt from the markdown** by a sync (created on init).
3. (`logs\`, and the launcher/scheduled-task wiring `BasicMemory-HTTP-MCP` + `BasicMemory-Watchdog` if the always-up loop is wanted.)

### Is re-indexing safe for the 713 notes?
**Yes — low risk, effectively idempotent.** Re-index reads markdown and writes the SQLite DB; it does **not delete** notes and does not alter note **bodies**. Because 713/716 notes **already carry basic-memory's `permalink:` frontmatter** (`VERIFIED`), the vault is already in basic-memory's canonical on-disk form, so a re-sync should not churn frontmatter.
**Caveat (honest):** basic-memory's sync *can* normalize/write frontmatter (permalink/updated timestamps) into `.md` files. Since permalinks already exist here the delta should be nil, but the cautious move is a **one-time copy of `D:\basic-memory` (excluding the 14 GB `.hf`) before the first sync**. Confidence the notes' content is safe: **high (~90%)**; that no `.md` file is touched at all: **moderate**.

### Exact ordered commands the owner would run (DO NOT run these here)
```powershell
# 0) Pre-flight: confirm nothing already holds the port, and back up the vault (content-only).
Get-NetTCPConnection -State Listen -LocalPort 18765 -ErrorAction SilentlyContinue
robocopy D:\basic-memory D:\basic-memory-backup-2026-09-23 /E /XD .hf .models   # cautious one-time copy

# 1) Reinstall the package (uv tool; version last documented = 0.22.1). Pin if desired.
uv tool install basic-memory
#   verify:
basic-memory --version

# 2) Point basic-memory at the existing vault (creates ~/.basic-memory\config.json + memory.db).
$env:BASIC_MEMORY_HOME = 'D:\basic-memory'
$env:FASTEMBED_CACHE_PATH = 'D:\basic-memory\.models'
$env:DO_NOT_TRACK = '1'
basic-memory project add main D:\basic-memory      # or `basic-memory project default main`

# 3) Build the index from the markdown (non-destructive read -> DB write).
basic-memory sync                                   # re-index the 713 notes

# 4) Start the HTTP daemon directly + detached on the CANONICAL port 18765 (owner action).
Start-Process basic-memory.exe `
  -ArgumentList 'mcp','--transport','streamable-http','--host','127.0.0.1','--port','18765','--path','/mcp' `
  -WindowStyle Hidden -PassThru -RedirectStandardError "$env:USERPROFILE\.basic-memory\logs\bm-http.err.log"

# 5) Verify liveness (HTTP 401/handshake on the port == alive), then re-enable the watchdog/self-heal.
Get-NetTCPConnection -State Listen -LocalPort 18765
#   Optional: restore the BasicMemory-HTTP-MCP scheduled task + BasicMemory-Watchdog once a daemon holds the port.
```
Notes: run the daemon **directly** first (proves binary health, decouples from the launcher kill-on-free-port race that caused the historical `:8765` restart-thrash). The daemon needs `BASIC_MEMORY_HOME=D:\basic-memory`, `FASTEMBED_CACHE_PATH=D:\basic-memory\.models`, `DO_NOT_TRACK=1`. Exact flag names (`project add`, `sync`) should be confirmed against `basic-memory --help` of the installed version before running.

---

## Appendix — measurement method
- Config parsed with `C:\Python314\python.exe` (PowerShell `ConvertFrom-Json` fails on case-colliding keys — itself a finding).
- Ports checked with `Get-NetTCPConnection -State Listen` (24680, 18812, 18765, 7870, 31110-31118, 8089, 9009, 9222, 13337 — none listening).
- stdio existence checked with `os.path.exists` on each `command`/first script arg; launchers (`cmd`/`npx`/`uvx`/`uv`/`python`/`node`/`docker`/`codex`/`gh-cli-mcp`) resolved via `shutil.which`.
- Session-state cross-checked against the harness "failed to connect" reminder and the surfaced `mcp__<server>__*` tool list.
- No secret values read or printed; env presence probed with `bool(os.environ.get(...))` only.
