# Stack-wiring audit — D:\opt (cyberstrike-mcp, decepticon, decepticon-upstream, pentagi, hexstrike-ai)

Date: 2026-09-29. Method: file reads (path:line cited) + live read-only checks (exact command + output cited). All live checks were executed during this audit on the box itself. Nothing was modified.

Headline: the gateway is genuinely up and its lazy availability probe is honest, **but 13 of 43 SSOT rows are RPC backends the gateway cannot invoke at all** (dispatch is a stub), **14 of 18 module backends have no code on disk**, **hexstrike and caldera are double-booked on port 8888**, and three unauthenticated command-execution / offensive-tool surfaces (decepticon 3001-3003, hexstrike 8888, live streamlit 8501) are bound to `0.0.0.0` on a cloud VM while their docs claim loopback-only. PentAGI's staged `.env` mounts the raw host Docker socket into the agent container as root regardless of `DOCKER_INSIDE=false`, and its search keys are unexpanded `${...}` templates.

---

## 1. cyberstrike-mcp — mcp-ssot.json v4 vs gateway-server.py vs reality

### 1.1 VERIFIED-WORKING (live checks I ran)

- Gateway process: scheduled task `CyberStrikeGateway` State=Running (`powershell Get-ScheduledTask`; action `C:\Python314\python.exe "D:\opt\cyberstrike-mcp\gateway-server.py"`), pid 43456, listening on `127.0.0.1:31100` only (`netstat -ano`).
- `cd /d/opt/cyberstrike-mcp && C:\Python314\python.exe verify_stack.py` → `gateway tools: ['harness_bridge_status','harness_capabilities','harness_invoke']`, **FAILURES: none**; live invokes passed: exa.search (cloud 200), firecrawl.search (cloud 200), nuclei `-version` → v3.11.1, nmap `--version` → 7.97.
- Live `harness_capabilities`: **17 available / 26 unavailable** (full table captured below in §1.6). The lazy probe design (gateway-server.py:47-84) does reflect reality row by row.
- zai-keys live through the gateway: `harness_invoke(zai-keys, status)` → 2 keys (sha8 2cbe00c7 active / 2b98b9a3), state file `C:\Users\prekzursil\.agents\zai-key-state.json` (exists, mtime Sep 25 — the interop file).
- Client chain claim TRUE: `~/.config/cyberstrike/cyberstrike.json` has exactly one MCP registration `cyberstrike-gateway -> http://127.0.0.1:31100/mcp` (key `mcp`, not `mcpServers`), matching `apply-client-mcp-ssot.py`'s emit logic.
- Gateway entry in `~/.agents/agents.json` (line 2575, url `http://127.0.0.1:31100/mcp`) enabled for claude/codex/gemini/cursor — claim in OFFENSIVE-STACK.md:55-57 holds for the registration itself.

### 1.2 UNWIRED — `kind=rpc` dispatch is a stub; 13 backends can never be invoked through the gateway

gateway-server.py:382-385:

```python
if match["kind"] == "rpc":
    return json.dumps({"backend": backend, "tool": tool,
                       "error": "rpc dispatch not configured for this backend yet",
                       "rpc": match.get("rpc")})
```

Live proof (my run, MCP client against 127.0.0.1:31100/mcp):

```
--- decepticon-recon: {"backend": "decepticon-recon", "tool": "ping", "error": "rpc dispatch not configured for this backend yet", "rpc": {"host": "127.0.0.1", "port": 3001}}
--- hexstrike:        {"backend": "hexstrike", "tool": "ping", "error": "rpc dispatch not configured for this backend yet", "rpc": {"host": "127.0.0.1", "port": 8888}}
--- caldera:          {"backend": "caldera", "tool": "ping", "error": "rpc dispatch not configured for this backend yet", "rpc": {"host": "127.0.0.1", "port": 8888}}
```

Affected rows (mcp-ssot.json, kind=rpc ×13): metasploit (:43-51), sliver (:88-96), burp (:97-106), caldera (:144-152), havoc (:153-160), mythic (:161-169), ghidra (:220-228), ida (:229-238), jadx (:239-248), decepticon-recon/initial-access/terminal (:261-290), hexstrike (:291-300).

Consequence: OFFENSIVE-STACK.md:57 "every agent on the box can harness_invoke the 43-backend estate" is **not true for 13 of 43 rows** — including the stack's flagship integrations (hexstrike "150+ tools", all three decepticon fronts). The availability probe only does a TCP connect (gateway-server.py:70), so these rows read "available" while being non-invocable. OFFENSIVE-STACK.md:72-77 "AVAILABLE (11, verified live)" listing `hexstrike :8888 (150+ tools)`, the decepticon fronts and `caldera(rpc)` conflates reachability with usability.

### 1.3 MISWIRED — hexstrike and caldera double-booked on 127.0.0.1:8888

- mcp-ssot.json:144-152 `caldera` rpc port 8888; mcp-ssot.json:291-300 `hexstrike` rpc port 8888.
- Reality: 8888 is `hexstrike_server.py --port 8888` (pid 37476, `Get-CimInstance Win32_Process`).
- Live capability table shows `caldera  available  rpc 127.0.0.1:8888 reachable` — a **false positive**: CALDERA is not running; the probe is touching hexstrike's socket. Symmetrically, if caldera ever starts on 8888, hexstrike's row would flip meaning and one of the two cannot bind at all.

### 1.4 MISSING — 14 of 18 `kind=module` backends have no code

`ls D:\opt\cyberstrike-mcp\fronts\` → only `exa.py, firecrawl.py, search_common.py, tavily.py, zai_keys.py` (+`__init__.py`). SSOT declares 18 module rows; live import fails for 14 (verbatim from my `harness_capabilities` run): cloud-audit, github-security, cve-mcp, osint, dbx-ai, angr, jb-library, darknet, dns-security, mcp-scanner, satellite, steganography, supply-chain, hackbrowser — all `import failed: No module named 'fronts.<x>'`.

Only `cloud-audit`'s note admits it (mcp-ssot.json:19 "land the backend package in fronts/ and it self-registers"). The others are presented as existing capability — github-security ":26 note 39-tool backend", cve-mcp ":33 41-tool backend", osint ":40 37-tool backend". The runtime manifest is honest about it; the SSOT notes are not.

### 1.5 STALE — catalogs totals don't add up

mcp-ssot.json:369-372 claims `specialized_total: 34, legacy_total: 12` (sum 46). Actual (my `collections.Counter` over the file): **43 rows; legacy=9, specialized=20**, plus knowledge 1, own-task 1, re-static 2, decepticon 3, mcp-integration 1, search 2, llm-keys 1, re-dynamic 1, code-quality 1, browser 1. Kinds: module 18 / rpc 13 / binary 6 / mcp-stdio 6. OFFENSIVE-STACK.md's "43-backend estate" is right; the SSOT's own catalog numbers are wrong.

### 1.6 Live capability table (my run, abridged to status)

```
available (17):   binary-ninja(54 tools) caldera*(false-positive, see 1.3) cheatengine(43 tools)
                  chrome-devtools(30 tools) decepticon-initial-access decepticon-recon
                  decepticon-terminal exa firecrawl frida hacktricks(7 tools) hexstrike
                  mitmproxy nmap nuclei tavily zai-keys
unavailable (26): angr burp cloud-audit cve-mcp darknet dbx-ai deepsource dns-security ghidra
                  github-security hackbrowser havoc ida ida-pro jadx jb-library mcp-scanner
                  metasploit mythic osint radare2 satellite sliver steganography supply-chain windbg
```

Drift vs OFFENSIVE-STACK.md:72-77 ("AVAILABLE (11)"): nmap is now installed (`C:\Program Files (x86)\Nmap\nmap.exe`) so the doc's "Pending one-click items … nmap" (OFFENSIVE-STACK.md:126-128) is stale; hacktricks/cheatengine/chrome-devtools/binary-ninja/zai-keys light up too. Doc undercounts; its `caldera(rpc)` line was never true.

### 1.7 STALE notes inside the SSOT

- nuclei (mcp-ssot.json:57): "installed at D:/opt.bin" — live probe resolves `C:\Users\prekzursil\.local\bin\nuclei.exe` (D:\opt\bin\nuclei.exe exists but loses PATH order).
- deepsource (mcp-ssot.json:342): "server runs (v1.8.3) but DEEPSOURCE_API_KEY not on this box" — through the gateway the server does **not** run: probe shows `mcp-stdio failed: spawn failed: McpError: Connection closed`. I reproduced manually: `node C:\Users\prekzursil\.local\opt\deepsource-mcp-server\deepsource-mcp-wrapper.mjs` exits immediately with `MCPError: Configuration error: DeepSource API key is required but not configured`. Key confirmed absent in User/Machine/Process scopes.
- tavily (mcp-ssot.json:306): "TAVILY_API_KEY / TAVILY_API_KEY_2 (cloud, both present)" — **not present** in persisted scopes (PowerShell check: User=False Machine=False for both), and OFFENSIVE-STACK.md's own table says "key NOT on box". The front therefore runs keyless DDG fallback (fronts/tavily.py:26-29). SSOT contradicts both reality and the stack doc.
- hexstrike (mcp-ssot.json:299) and catalogs.policy (:372) reference `start-hexstrike.ps1` — no such file anywhere under D:\opt (`find /d/opt -iname "*hexstrike*" -name "*.ps1"` empty; /d/opt/bin holds only nuclei.exe/rg.exe; /d/opt/scripts only enable-nested-virt-and-docker.ps1). The server was evidently started by hand.
- Gateway probe branch `kind == "env"` (gateway-server.py:76-78) is dead code — no row uses kind=env (firecrawl's `env` value at :83 is a string but its kind is module; only hacktricks' dict-shaped `env` at :75-77 is consumed, by the stdio worker at :184-187).

### 1.8 STALE — old HTTP-hub fleet still enabled in ~/.agents/agents.json

13 entries with `enabled: true` point at dead hub ports (nothing listens on any 311xx except 31100 — netstat): 31110, 31111, 31112, 31113, 31117, 31118, 31119 (two duplicate sets; full list from my JSON walk). Their descriptions still cite `mcp-proxy supervisor D:\opt\cyberstrike-mcp\start-cyberstrike-mcp-http.ps1`, a file that no longer exists in the rebuilt kit. Includes both hexstrike entries (see §5.3). Any agent honoring these registrations gets connection-refused.

---

## 2. decepticon (D:\opt\decepticon) — dual-mode patches, .env

### 2.1 Dual-mode patch: REAL and correctly wired

`git status` → ` M src/tools/mcp/Initial_Access.py`, ` M Reconnaissance.py`, ` M terminal.py`, `?? src/tools/mcp/_exec.py`, `?? start-decepticon.ps1` (only commit: f3baf5a initial). The diffs replace the upstream docker-only bodies with `exec_command` from `_exec.py`. `_exec.py:57-61` resolves mode: `DECEPTICON_FORCE` pin, else kali iff the `attacker` container is running, else local Git Bash `sh -c` (`_exec.py:24-38`). terminal.py keeps tool parity in local mode (in-process session buffers + `exec_command`, timeout 900).

Docker engine is DOWN on this box right now (`docker ps` → `request returned 500 ... dockerDesktopLinuxEngine ... check if the server supports the requested API version`), so **all three servers are executing in LOCAL mode — commands run directly on the Windows host via Git Bash**, not in a kali sandbox. OFFENSIVE-STACK.md:87-89's description of the patch is accurate; the operational consequence (host-native execution) is worth stating plainly.

### 2.2 MISWIRED vs CLAIM — "loopback-only" script, 0.0.0.0-binding servers

- start-decepticon.ps1:1-4: "full local Decepticon stack, **loopback-only**".
- Reality (netstat): `0.0.0.0:3001`, `0.0.0.0:3002`, `0.0.0.0:3003` LISTENING (pids 20236/27612/10772 = the three MCP servers, verified via Win32_Process).
- Cause: the servers call `mcp.run(transport="streamable-http")` with no host override, and the installed SDK defaults to `host: str = "0.0.0.0"` (`D:\opt\decepticon\.venv\Lib\site-packages\mcp\server\fastmcp\server.py:90`, mcp 1.8.1). The script pins `--server.address 127.0.0.1` only for Streamlit (start-decepticon.ps1:29-30) — nothing pins the MCP servers.
- Exposure: these are **unauthenticated** streamable-http MCP servers whose headline tool is `command_execution(command)` (Reconnaissance.py), i.e. arbitrary command execution on the host, reachable from any interface the GCP firewall passes. Same class for 3002 (hydra/searchsploit) and 3003 (sessioned terminal).

### 2.3 Live-vs-staged drift on the UI

The running Streamlit (pid 32636, started 13:26) has command line `... -m streamlit run frontend/streamlit_app.py --server.headless true --server.port 8501 ...` — **no `--server.address`**, so it binds `0.0.0.0:8501` (netstat confirms; `[::]:8501` too). The staged script (mtime 13:53) would bind 127.0.0.1. The live process predates the staged wiring and was started by something else.

### 2.4 Minor

- `.env`: real OpenAI key present (estate plaintext, fine); `LANGGRAPH_API_URL=http://127.0.0.1:2024` — **nothing listens on 2024** (netstat). Whether the local swarm uses it was not exercised (I did not drive the UI/CLI agents).
- terminal.py:25 `_TMUX_TOOLS` defined, never used (dead).
- mcp_config.json is byte-identical to upstream HEAD (its odd "terminal" key naming under reconnaissance/initial_access is upstream's own, not a local miswire).

---

## 3. decepticon-upstream (D:\opt\decepticon-upstream) — .env staged, compose never verified

### 3.1 .env staging: TRUE on the checked claims

`.env` (20,284 B, mtime 13:40) covers every variable in `.env.example` plus `DO_NOT_TRACK` and `OLLAMA_API_BASE` (name-set diff, my run). Spot checks: `DECEPTICON_MODEL_PROFILE=max` (:202), `DECEPTICON_TELEMETRY=off` (:406), `DO_NOT_TRACK=1` (:407), `OLLAMA_API_BASE=http://host.docker.internal:11434` (:408), OpenAI key set (:12), `DECEPTICON_AUTH_PRIORITY=openai_api,openai_oauth,ollama` (:219), `DECEPTICON_AUTH_CHATGPT=true` (:233). Repo is at v1.1.47 (`git log -1` → a04f96b "release/oss-1.1.47-20260926") — OFFENSIVE-STACK.md:94 says v1.1.44 (stale number, CVE conclusion unaffected: still ≥ 1.1.17).

### 3.2 Compose verification status

- The ask's premise "compose never verified" holds: the engine is down, no containers exist; nobody could have brought it up.
- I ran the config-level check: `cd /d/opt/decepticon-upstream && docker compose -f docker-compose.yml --env-file .env config --quiet` → **VALID** (parses and interpolates cleanly with the staged .env). That is a parse validation only — it is NOT a bring-up, and I report it as such.

### 3.3 MISWIRED bring-up — `docker compose up -d` will not start the documented stack

Service profiles (parsed from compose): unprofiled = litellm, postgres, neo4j, sandbox, langgraph, skillogy; `web` behind profile `web` (compose :495-496); `cli` behind `cli` (:543-544); c2-sliver/ad/reversing likewise. `COMPOSE_PROFILES` is **unset** in `.env` (grep shows only commented examples at :317/:382). So OFFENSIVE-STACK.md:94 "Bring-up: `docker compose up -d`" starts only the 6 core services — **no web dashboard, no terminal CLI**, despite the same doc line 91-93 describing "real 7-service stack (PostgreSQL, LiteLLM, Neo4j KG, Kali sandbox, LangGraph runtime, web, terminal)". Upstream's own README (:76-79) says the launcher/CLI path (`decepticon`, `/web` slash command) is how web comes up. Also 'terminal' is not a compose service name (the cli service is, run via `docker compose run --rm cli` per its own comment).

### 3.4 Docker-socket note

The `cli` service mounts `/var/run/docker.sock:/var/run/docker.sock` (compose :531) — upstream's deliberate design for the `/web` command, documented in-line (:512-519, "OSS scope: user == host owner"). It only activates under profile `cli`. The kali `sandbox` drops ALL caps and adds back a bounded set (NET_RAW/NET_ADMIN/NET_BIND_SERVICE/SYS_PTRACE/SETUID/SETGID/CHOWN/DAC_OVERRIDE, compose :231-240) and gets no socket.

---

## 4. pentagi (D:\opt\pentagi) — DOCKER_INSIDE and socket exposure

### 4.1 The .env values (the ask's specific question)

- `.env:262` `DOCKER_INSIDE=false` — resolved by compose to the string `"false"` (inline `#` comment correctly stripped; verified in `docker compose config` output: `DOCKER_INSIDE: "false"`).
- `.env:263` `DOCKER_NET_ADMIN=true` → `DOCKER_NET_ADMIN: "true"` resolved.
- `.env:264` `DOCKER_SOCKET=/var/run/docker.sock`; `.env:273` `DOCKER_INSIDE_HOST=` (empty).
- `.env:165` `PENTAGI_DOCKER_SOCKET=` (empty).

### 4.2 THE CONCRETE DOCKER-SOCKET ESCAPE (still present with DOCKER_INSIDE=false)

docker-compose.yml:

- :206 `- ${PENTAGI_DOCKER_SOCKET:-/var/run/docker.sock}:/var/run/docker.sock` — with `PENTAGI_DOCKER_SOCKET` empty, the **raw host Docker socket is bind-mounted into the pentagi app container unconditionally**. `DOCKER_INSIDE` does not gate this mount; it only controls whether the socket/API access is passed on into agent-spawned *sandbox* containers (:187-192).
- :211 `user: root:root # while using docker.sock`
- :184 `- DOCKER_HOST=${DOCKER_HOST:-unix:///var/run/docker.sock}` — the daemon endpoint is explicitly handed to the app.

Resolved proof (my `docker compose -f docker-compose.yml --env-file .env config` run):

```
DOCKER_HOST: unix:///var/run/docker.sock
DOCKER_INSIDE: "false"
DOCKER_NET_ADMIN: "true"
DOCKER_SOCKET: /var/run/docker.sock
user: root:root
source: /var/run/docker.sock -> target: /var/run/docker.sock
```

Risk, concretely: the `pentagi` service is an **autonomous L-driven pentest agent that browses and executes on web-untrusted content**. Anything that gets code execution or prompt-injection inside that container — a served exploit, a malicious page, a poisoned tool result — reaches the host Docker daemon as root with no authentication and no socket proxy (`DOCKER_INSIDE_HOST` empty, the .env's own security note at :255-261 recommends a Tecnativa docker-socket-proxy but none is staged). Host takeover is one `docker run -v /:/host ...` away. On top: `DOCKER_NET_ADMIN=true` gives agent-spawned sandboxes CAP_NET_ADMIN (ARP-spoof/iptables on the shared bridge). The `.env` comment documents the DOCKER_INSIDE half of this risk but not the always-on app-container mount.

### 4.3 Claimed-but-not-true in the staged .env (OFFENSIVE-STACK.md:116-118 ".env FULL profile (OpenAI + Tavily/Firecrawl/Exa keys, Ollama, Graphiti KG on, loopback-only binding, hardened pg/scraper creds)")

- **OpenAI**: no `OPENAI*` variable exists in pentagi/.env (grep empty), docker-compose.yml references none, and `OPENAI_API_KEY` is unset in User/Machine/Process scopes (PowerShell check). No staged OpenAI key. (decepticon's .env has one; pentagi's does not.)
- **Tavily/Firecrawl**: `.env:215` `TAVILY_API_KEY=${TAVILY_API_KEY_2}` and `.env:219` `FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}` — unexpanded templates (the firecrawl one circularly self-referencing; tavily's references a `_2` variable that is not defined for compose). `docker compose config` resolves them to literal `${...}` strings (`TAVILY_API_KEY: $${TAVILY_API_KEY_2}`), i.e. the containers would receive junk keys and search would 401 at runtime. This is the exact `${…}` template bug class OFFENSIVE-STACK.md:83 says was "cleared" from the gateway tavily front — it lives on in pentagi.
- **Exa**: no EXA variable exists anywhere in pentagi (.env or compose).
- **loopback-only binding**: `.env:160` `PENTAGI_LISTEN_IP=0.0.0.0` — overrides the compose default `127.0.0.1` (compose :33 `${PENTAGI_LISTEN_IP:-127.0.0.1}`), so the PentAGI HTTPS UI (initial creds `admin@pentagi.com/admin` per bring-up.ps1's own output text) would publish on **all interfaces**. The other LISTEN_IP vars are empty → default to loopback.
- TRUE parts: `GRAPHITI_ENABLED=true` (:301), Ollama URLs at host.docker.internal:11434 (:85/:95), pg/scraper passwords randomized (`PENTAGI_POSTGRES_PASSWORD=Pg-38…`, `LOCAL_SCRAPER_PASSWORD=Sc-b44…`).

### 4.4 bring-up.ps1

Staged logic read (10-min engine wait, then base+langfuse+graphiti+observability compose layers, prints URLs). Not run — engine down. The `--pull missing` first run is several GB.

---

## 5. hexstrike-ai (D:\opt\hexstrike-ai)

### 5.1 Live state

- Server UP: `hexstrike_server.py --port 8888`, pid 37476, started 13:54 (Win32_Process), under the kit venv's base interpreter (`C:\Python312`, venv home per `.venv/pyvenv.cfg`).
- `curl http://127.0.0.1:8888/health` → HTTP 200; body reports `"all_essential_tools_available": false` (some tool venvs not yet installed — consistent with the documented lazy first-start installs). Root `/` → 404 (normal for the API).
- Pinned ref claim TRUE: `git -C repo log -1` → `8333779 Add MIT License` (matches mcp-ssot.json:299).

### 5.2 MISWIRED vs CLAIM — "localhost-only" server binds 0.0.0.0

- hexstrike_mcp_launcher.py:9 (docstring): "Ensures the **localhost-only** HexStrike HTTP server is healthy"; :27 `DEFAULT_HOST = 127.0.0.1`; :85-86 exports `HEXSTRIKE_HOST` to the child.
- hexstrike_server.py:99 reads `API_HOST = os.environ.get('HEXSTRIKE_HOST', '127.0.0.1')` but **never binds it** — it is only printed at :198. The actual bind is hardcoded at :17289: `app.run(host="0.0.0.0", port=API_PORT, debug=DEBUG_MODE)`.
- Netstat: `0.0.0.0:8888 LISTENING`. So `HEXSTRIKE_HOST` is decorative, the launcher's loopback claim is false, and an **unauthenticated offensive-tool API** (the SSOT's own words: "150+ offensive tools behind one HTTP surface") listens on every interface of a cloud VM. (The launcher itself never checks the bind — `ensure_server` uses TCP `port_open` only, launcher:108-113; its `healthy()` helper at :63-71 is never called.)

### 5.3 UNWIRED — the MCP front has no live registration anywhere

- Gateway row is kind=rpc → not invocable (§1.2).
- `~/.agents/agents.json` hexstrike entries — "hexstrike-ai" (claude) and "hexstrike-ai-hub" (hermes) — both `enabled: true` with url `http://127.0.0.1:31113/mcp`: **dead port** (nothing on 31113; description cites the deleted `start-cyberstrike-mcp-http.ps1` supervisor).
- `hexstrike_mcp_launcher.py` (the framed-stdio bridge the SSOT note points at) is registered nowhere I can find (not in agents.json, not in the gateway SSOT as an mcp-stdio row; `hexstrike-ai-mcp.json` is the repo's own sample config).
- Net: the only working interface to hexstrike today is the raw unauthenticated HTTP API on 0.0.0.0:8888.

---

## 6. Cross-cutting summary

| # | Component | Finding | Kind | Severity |
|---|---|---|---|---|
| 1 | cyberstrike-mcp | kind=rpc dispatch stub — 13/43 rows probe-only, never invocable via harness_invoke (gateway-server.py:382-385; live-proven) | unwired | high |
| 2 | cyberstrike-mcp | caldera + hexstrike both on 127.0.0.1:8888; caldera "available" is a false positive off hexstrike's socket | risk | high |
| 3 | cyberstrike-mcp | 14/18 module backends have no code in fronts/ (import fails live) while SSOT notes describe tool counts | missing | high |
| 4 | cyberstrike-mcp | catalogs totals wrong (34/12 claimed vs 20/9+14 actual; 43 rows) | stale | low |
| 5 | cyberstrike-mcp | 13 enabled agents.json entries on dead 311xx hub ports citing a deleted supervisor script | stale | medium |
| 6 | cyberstrike-mcp | SSOT notes stale: nuclei path, deepsource "server runs", tavily "both present", start-hexstrike.ps1 missing | stale | low |
| 7 | decepticon | "loopback-only" claim vs 0.0.0.0:3001-3003 unauth command-exec MCP servers (FastMCP default host 0.0.0.0) | risk | high |
| 8 | decepticon | dual-mode patch real; with docker down all execution is host-local via Git Bash (by design, but it is the live mode) | risk | medium |
| 9 | decepticon | live streamlit on 0.0.0.0:8501 predates staged script (started without --server.address) | risk | medium |
| 10 | decepticon-upstream | .env genuinely staged; compose parses (my config check) but OFFENSIVE-STACK's `docker compose up -d` won't start web/cli (profiles unset) | planned-not-included | medium |
| 11 | pentagi | raw host docker.sock mounted into root:root agent container regardless of DOCKER_INSIDE=false; DOCKER_HOST points at it; NET_ADMIN sandboxes — concrete host-escape path | risk | high |
| 12 | pentagi | .env claims vs reality: no OpenAI key anywhere, tavily/firecrawl `${...}` template junk, no exa var, PENTAGI_LISTEN_IP=0.0.0.0 vs "loopback-only" | stale | high |
| 13 | hexstrike-ai | server hardcodes 0.0.0.0 (HEXSTRIKE_HOST ignored); launcher claims localhost-only; unauth offensive API on all interfaces | risk | high |
| 14 | hexstrike-ai | MCP front unregistered everywhere; both agents.json entries point at dead 31113 | unwired | medium |

## 7. Not run / limitations

- Docker engine is non-functional on this VM (`docker ps` → 500), so no container bring-up was possible or attempted for pentagi / decepticon-upstream; compose was verified at config-parse level only (exact commands above).
- I did not drive the decepticon swarm UI/CLI agents, so whether `LANGGRAPH_API_URL=:2024` matters to the local variant is untested (port confirmed dead).
- The hacktricks two-call worker-reuse claim in OFFENSIVE-STACK.md was not re-measured.
- GCP firewall state was not queried (no gcloud call); all 0.0.0.0 findings are stated as interface bindings, which netstat proves regardless of edge filtering.
