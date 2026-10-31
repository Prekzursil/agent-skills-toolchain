---
title: canonical-vs-reality
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/audit/canonical-vs-reality
---

# Canonical MCP registry vs machine reality

Date: 2026-09-29. Auditor lane: canonical-vs-reality.

Sources diffed:

- **Canonical registry**: `C:\Users\prekzursil\source\agent-skills-toolchain\tools\mcp\canonical-mcp-servers.json` (read in full, 437 lines, 51 entries under `mcpServers`, lines 2–435).
- **Policy inventory**: `C:\Users\prekzursil\.agents\agents.json` `mcp.servers` (lines 36–2585, ~70 entries) plus the stray top-level `mcpServers` duplicate at lines 2605–2623.
- **Live client registries used as reality cross-reference**: `C:\Users\prekzursil\.claude.json` (top-level `mcpServers`, 86 keys listed via Python json parse) and `C:\Users\prekzursil\.codex\config.toml` (`[mcp_servers.*]` sections at lines 166, 1064–1127).

Checks actually run (all this session):

1. Directory/file existence for every local stdio path in both registries — `for p in ...; do [ -e "$p" ] ...` bash loops (two batches, ~70 paths).
2. `find C:/Users/prekzursil/.local C:/Users/prekzursil/source D:/opt D:/mcp-servers -maxdepth 4 -iname` for each ghost's script/exe name — confirmed no alternate install exists anywhere.
3. Port liveness: `netstat -an | grep LISTEN` for 8765, 8812, 8890, 18765, 18812, 24680, 31100–31119, 7870, 8888, 9222, 9876, 8089, 4000. **Listening: 8888 (jupyter), 18765 (basic-memory real port), 31100 (cyberstrike-gateway). Everything else dead**, including canonical's 8765/8812.
4. npm registry: `npm view <pkg> version` for all 27 npx-based packages across both registries. All exist **except `libgen-mcp`** (npm error; agents.json documents this as a deliberate placeholder).
5. PyPI: JSON API via Python urllib for 10 uvx packages — all exist, including the canonical `tooluniverse==1.2.4` pin (1.2.4 resolves; latest is 1.5.4).
6. Remote endpoints: TCP connect via Python sockets — deepwiki, exa, figma, huggingface, tavily, linear, notion, context7, githubcopilot, brightdata, api.z.ai, developers.openai.com, mcp.apify.com all reachable. `sci-hub.se` **DNS-fails** (getaddrinfo).
7. Launcher resolution: `which npx uvx uv node bun gh-cli-mcp` — npx 11.19.0, uvx 0.12.20, uv, node present; **`bun` and `gh-cli-mcp` NOT found** (PATH listing captured; global npm dir `AppData/Roaming/npm` also lacks gh-cli-mcp).

---

## 1. Canonical registry vs reality

### 1a. Canonical entries that are GHOSTS (registered, install gone) — 12 of 51

| Canonical entry | Registered launch config (file:line) | Reality check |
|---|---|---|
| `apktool-mcp` | canonical:7–11 → `C:/Users/Prekzursil/.local/opt/apktool-mcp-server/.venv/Scripts/python.exe` | `.local/opt` listing contains no `apktool-mcp-server`; `find` for `apktool_mcp_server.py` across `.local`, `source`, `D:/opt` returns nothing |
| `cloud-audit` | canonical:37–42 → `bun run C:/Users/Prekzursil/.local/opt/cloud-audit-mcp/src/index.ts` | Dir missing AND `bun` not on PATH. The live form is the cyberstrike HTTP hub `http://127.0.0.1:31118/mcp` (agents.json:1295–1311) — but 31118 has no listener either; only the 31100 gateway is up |
| `fb-messenger` | canonical:141–145 → `C:\Users\prekzursil\source\repos\fb-messenger-mcp\.venv\Scripts\python.exe` | `source/repos` contains only `mattpocock-skills`. Source tree exists at `tools/mcp/fb-messenger-mcp` (server.py present) but has **no venv** (ls -a) — not launchable as registered |
| `github_cli` | canonical:203–210 → command `gh-cli-mcp` | `which gh-cli-mcp` fails; not in `AppData/Roaming/npm` global installs. Same dead command in agents.json (enabled=true) and `.claude.json` |
| `jadx-mcp` | canonical:242–246 → `C:/Users/Prekzursil/.local/opt/jadx-mcp-server/...` | Dir missing from `.local/opt`; no alternate found |
| `ocr-suite` | canonical:267–271 → `D:/mcp-servers/abbyy-finereader-ocr-mcp/...` | `D:/mcp-servers` does not exist at all |
| `openmm-md` | canonical:273–277 → `D:/micromamba/envs/openmm-md/python.exe` + `source/repos/openmm-md-mcp/server.py` | Both missing. Source exists at `tools/mcp/openmm-md-mcp` (server.py) but no venv and no conda env |
| `paper-search` | canonical:293–295 → `D:/ReverseTools/mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe` | `D:/ReverseTools` is gone entirely |
| `perplexity` | canonical:308–310 → `D:/ReverseTools/mcp/perplexity-web-mcp/.venv/Scripts/pwm-mcp.exe` | Same — `D:/ReverseTools` gone |
| `rdkit` | canonical:352–356 → `C:/Users/Prekzursil/source/repos/rdkit-mcp-server/...` | Missing; no rdkit MCP install found anywhere searched |
| `schrodinger` | canonical:374–378 → `C:/Users/Prekzursil/source/repos/schrodinger-mcp/.venv/...` | Missing. Source exists at `tools/mcp/schrodinger-mcp` (server.py) but no venv |
| `agent-mail` | canonical:3–5 → `http://127.0.0.1:8812/mcp` | Nothing listens on 8812 (netstat). Worse: the *actual* install `.local/opt/mcp_agent_mail` (referenced by codex config.toml:222) is also gone, and even the real port 18812 (agents.json:1224) is dead. Full ghost in both registries |

### 1b. Canonical entries that are STALE (wrong endpoint, capability alive)

- `basic-memory` — canonical:13–15 says `http://127.0.0.1:8765/mcp`; netstat shows 8765 dead while **18765 IS listening** (the port agents.json:774, `.claude.json` and codex config.toml:1089–1091 all use). Canonical URL is simply wrong.
- `ghidra-mcp` — install intact (verified exe + `bridge_mcp_ghidra.py`), but its runtime dependency `--ghidra-server http://127.0.0.1:8089/` (canonical:189–190) has nothing listening. Installed, runtime-dead.
- `searxng` — package `mcp-searxng@1.8.0` exists on npm (registry check), but its required backend `SEARXNG_URL=http://127.0.0.1:8890` (canonical:404–406) is not listening.
- `tooluniverse` — pin `==1.2.4` still resolves on PyPI (verified), but machine reality moved on: `.claude.json` runs 1.5.0 and PyPI latest is 1.5.4. Works, but 3 versions behind.

### 1c. Canonical entries VERIFIED GOOD — 34 of 51

- Local stdio with intact exe+script: `cheatengine`, `cloud-hub`, `codex-fleet-github`, `hexstrike-ai`, `ida-pro-mcp`, `linkedin`, `markitdown`, `proxy-mcp`, `qdx-rush`, `qlty`, `ralph-orchestrator`, `scholarly-access`, `search-hub`, `social-hub` (all path checks EXISTS; launcher `C:\Python314\python.exe` and `uv.exe`/`node.exe` verified present).
- npx on-demand: `binary-ninja-mcp`, `chrome-devtools-mcp`, `context7`, `cve-mcp`, `figma-rest`, `firecrawl-mcp`, `frida-mcp`, `github-security-mcp`, `gitlab`, `osint-mcp-server`, `pdf-reader`, `playwright-mcp`, `repomix` — npx 11.19.0 present, every package confirmed on npm (versions captured).
- uvx on-demand: `docker` (docker-mcp 0.2.0), `elevenlabs` (0.12.2), `excel` (excel-mcp-server 1.1.1), `tooluniverse` — uvx 0.12.20 present, all PyPI packages confirmed.
- Remote HTTP: `deepwiki`, `exa`, `figma`, `huggingface`, `tavily` — all TCP-reachable on 443.

Bottom line for canonical: **12 ghosts, 4 stale, 34 good** (51 total).

---

## 2. Good installs the canonical registry does NOT know about

Real, launchable-looking installs found on disk that no canonical entry points at:

- `tools/mcp/patent-search-mcp/` — server.py, requirements.txt, pyproject, tests. In neither canonical nor agents.json.
- `tools/mcp/tiktok-mcp/` — server.py, requirements. In neither registry.
- `tools/mcp/hacktricks-mcp-server/` — full npm package (package.json + node_modules + dist). agents.json only knows `hacktricks` as a dead HTTP port 31115 (agents.json:2323–2341); the local install is unreferenced by canonical.
- `tools/mcp/fb-reels-uploader/` — fb-reels-mcp.mjs + node_modules. Unreferenced.
- `tools/mcp/openmm-md-mcp/`, `tools/mcp/schrodinger-mcp/`, `tools/mcp/fb-messenger-mcp/` — sources exist HERE while the canonical entries point at the deleted `source/repos/*` copies; they lack venvs, so re-pointing canonical at these would still need env rebuilds.
- `tools/mcp/mcp-http-host/`, `tools/mcp/mcp-host-supervisor/` — MCP hosting/supervision infra, unreferenced.
- `.local/opt/angr/` — `angr-mcp.exe` verified present; known to agents.json (disabled) but absent from canonical. Canonical `frida-mcp` uses the npx form while `.local/opt/frida-mcp/.venv/Scripts/frida-mcp.exe` (the agents.json form) also exists — two parallel installs, canonical knows only one.
- `.local/opt/deepsource-mcp-server/deepsource-mcp-wrapper.mjs` — verified present; in agents.json (disabled), not in canonical.
- `~/.agents/mcp-servers/video-agent-kit/mcp/video_edit_server.py` — verified present; wired into agents.json, codex and `.claude.json`; absent from canonical.
- `source/open-coscientist/mcp_server_stdio.py` + `.venvs/opencoscientist-mcp` — verified present; in agents.json/codex, absent from canonical.
- `D:/opt/cyberstrike-mcp/` gateway — **the only live security hub** (31100 listening); in agents.json as `cyberstrike-gateway`, absent from canonical.
- `D:/opt/hexstrike-ai/` (launcher + repo) and `D:/opt/mcp/cheatengine/MCP_Server/` — second copies of installs canonical points at via `.local/opt`.
- Global npm (`AppData/Roaming/npm`): `chrome-devtools-mcp`, `openalex-mcp`, `pdf-reader-mcp`, `playwright-mcp`, `cyberstrike` (@cyberstrike-io) — globally installed; canonical only knows the npx forms.
- `.claude.json`-only registrations absent from canonical: `serena` (uvx git+https://github.com/oraios/serena), `zai-mcp-server` (npx `@z_ai/mcp-server` — confirmed on npm, 0.1.5), `codex` (`codex mcp-server`; codex.cmd present in global npm).
- codex config-only: `apify` (https://mcp.apify.com/ — reachable; not in canonical).

Gutted/stub dirs that are NOT good installs (so no canonical entry is missing anything): `tools/mcp/looker-mcp` (only `__pycache__`), `tools/mcp/cyberstrike-mcp-kit` (only package-lock.json), `tools/mcp/digitalocean-mcp` (README/scripts/validation, no server), `.local/opt/ghidra-bridge` (empty).

---

## 3. agents.json `mcp.servers` ghosts

### Enabled=true and dead (worst class — these will be spawned/connected and fail)

| Entry (agents.json line) | Config | Why dead |
|---|---|---|
| `github_cli` (512) | `gh-cli-mcp` | command unresolvable on PATH and global npm |
| `zai-lane-a` (2367) | `D:/bolt/enum/pulls/.../zai-anon-mcp.py` | script missing; `D:/bolt` does not exist |
| `breach-intel` (2390) | `D:/opt/breach-mcp/breach_intel_mcp.py` | script missing (D:/opt listing has no breach-mcp) |
| `cursor-bridge` (1777) | `D:/opt/cursor-bridge/cursor_bridge_mcp.py` | script missing |
| `dbx-ai` (1352) | `tools/mcp/dbx-ai/dbx-ai-mcp-server.py` | dir missing from tools/mcp |
| `biomni-hub` (1472) | `tools/biomni-hub-mcp/hub/.venv/.../python.exe` + `server.py` | venv EXISTS but `server.py` missing — install gutted |
| `lifesciences` (2538) | `source/lifesciences-research/...gateway.py` | `source/lifesciences-research` does not exist |
| `burp` (1529) | jdk-21 java.exe + `AppData/Roaming/BurpSuite/mcp-proxy/mcp-proxy-all.jar` | BOTH missing |
| `McpHub` (2475) | sse `http://127.0.0.1:24680/sse`, enabled for 7 targets | nothing listening on 24680 — every "[consume via McpHub :24680]" STICKY note across ~20 parked entries currently points at a dead gateway |
| `agent-mail` (1213) | `http://127.0.0.1:18812/mcp/` | port dead AND install `.local/opt/mcp_agent_mail` gone |
| `biomni` (2411) + duplicate top-level `mcpServers.biomni` (2605) | `http://127.0.0.1:7870/mcp` | port dead (WSL server not running) |
| `nuclei` (31117), `osint` (31112), `github-security` (31110), `cloud-audit` (31118), `cve-mcp` (31111), `hexstrike-ai` (31113), `semgrep` (31119) — all enabled=true | cyberstrike mcp-proxy hubs | **none** of 31110–31119 listening; only gateway 31100 is up. Same for the 7 hermes `*-hub` mirror entries (1637–1776) |
| `sci-hub` (1819) | npx sci-mcp-server@1.0.0 + `SCIHUB_MIRROR=https://sci-hub.se` | package exists, but mirror DNS-fails — degraded/unusable |

### Disabled and stale (registry rot, lower urgency)

- `glm53-space` (596) — `tools/mcp/glm53-space/` contains only `__pycache__` and `tests`; `mcp_server.py` gone.
- `kaggle` (1497) — `Downloads/bionlp/.venv/Scripts/python.exe` missing (wrapper script `.codex/mcp-wrappers/kaggle_mcp_stdio.py` still exists).
- `deepscan` (1185) — `DEEPSCAN_JAVA_BIN` jdk-17 path missing.
- `libgen` (1863) — npm package `libgen-mcp` does not exist (npm error). agents.json itself documents this as a deliberate placeholder, so this is *known* rot, not accidental.
- `firecrawl` (415) — 31114 dead; description already says PARKED/dead with revival plan. Consistent with reality.

### Verified good in agents.json (spot-checked)

`jupyter` (uvx 2.2.3 + :8888 listening ✓), `video-agent-kit` ✓, `open-coscientist-lit-review` ✓, `markitdown`/`meta-tool`/`qlty`/`ralph-orchestrator`/`ghidra-mcp`/`ida-pro-mcp`/`cheatengine`/`frida-mcp`/`angr`/`mitmproxy`/`deepsource` (exes verified), `github`/`linear`/`notion`/`context7`/`huggingface`/`brightdata`/`exa`/`deepwiki`/`openaiDeveloperDocs`/`web-search-prime`/`web-reader`/`zread` (remotes TCP-reachable), `basic-memory` (18765 listening), `cyberstrike-gateway` (31100 listening), `scholarly-access`/`linkedin` (files verified), all parked npx/uvx entries (packages confirmed on npm/PyPI).

---

## 4. Extra observations

- `.codex/config.toml` has its own ghosts not present in either audited registry: `node_repl` (runtimes exe `.../cua_node/a708e72b10c27b59/bin/node_repl.exe` missing) and `firecrawl-kit` → dead 31114.
- The canonical registry is a Codex-flavored snapshot (unpinned `npx -y pkg` forms, `${ENV}` interpolation) that has drifted from the agents.json policy layer (pinned versions, HTTP-hub conversions). Example: canonical `cloud-audit` is still the dead bun/stdio form while agents.json moved it to HTTP 31118 (itself now down); canonical `osint`/`github-security`/`cve-mcp` are npx forms while agents.json uses hubs.
- `D:/ReverseTools` and `D:/mcp-servers` were whole-directory removals — they took 3 canonical entries down at once (paper-search, perplexity, ocr-suite).
- Duplicate/legacy: agents.json carries `biomni` twice (`mcp.servers.biomni` and top-level `mcpServers.biomni`), and `github-security-hub` vs `github-security`, `cve-mcp-hub` vs `cve-mcp`, etc. duplicate the same dead ports for different targets.

## Commands run (exact)

- `for p in ...; do if [ -e "$p" ]; then echo EXISTS ...` (two batches covering all stdio paths in both registries)
- `ls` of: `.local/opt`, `tools/mcp` (+ 15 subdir inspections), `source/repos`, `D:/opt`, `D:/opt/mcp`, `D:/opt/cyberstrike-mcp`, `D:/opt/hexstrike-ai`, `D:/ReverseTools/mcp`, `D:/mcp-servers`, `.agents/mcp-servers`, `AppData/Roaming/npm`, `tools/biomni-hub-mcp/hub`, `tools/mcp/glm53-space`, `source/lifesciences-research`
- `netstat -an | grep LISTEN | grep -E ":(8765|8812|8890|18765|18812|24680|31100|31101|31110-9|7870|8888|9222|9876|8089|4000)"`
- `npm view <pkg> version` × 27; `python -c` PyPI JSON API × 10 + `tooluniverse/1.2.4` pin; `python -c` socket connect × 14 hosts
- `which npx uvx uv bun gh-cli-mcp node`; `npx --version`; `uvx --version`
- `python -c` json parse of `.claude.json` mcpServers; `grep -n` of `.codex/config.toml`
- `find .local source D:/opt D:/mcp-servers -maxdepth 4 -iname` × 7 ghost names (all empty)

Not run / not possible: no MCP handshake (tools/list) probes against the live ports — the ask scoped the diff to registration vs install existence; handshake probing of authenticated remote endpoints was out of scope. Windows-service-level checks for agent-mail/basic-memory singletons were not enumerated beyond port checks.