---
title: rpc-dispatch
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/followup/rpc-dispatch
---

# Lane report: rpc-dispatch — kill kind=rpc, dispatch every stubbed backend for real

Date: 2026-09-30. Lane scope from the ask: make every remaining stubbed backend either
(a) dispatch for real on its native transport or (b) explicitly report unavailable with
a reason — never available with a stub. Kill kind=rpc as a class.

**Invariant now enforced**: `available` means a real protocol round-trip succeeded
(msgrpc auth+core.version / SSE initialize+tools-list / stdio initialize+tools-list /
streamable-http initialize+tools-list), and `harness_invoke` returns either a real
result or a real error surfaced from the underlying tool.

---

## 0. What was found (baseline, all run this session)

- `D:\opt\cyberstrike-mcp\gateway-server.py:382-385` (pre-edit) was the kind=rpc stub:
  `"rpc dispatch not configured for this backend yet"` on harness_invoke, while the
  probe (pre-edit gateway-server.py:67-73) only did a bare `socket.create_connection` —
  "available" on TCP-open alone (audit out/audit/stack-wiring.md §1.2/§1.3).
- 9 kind=rpc rows remained in mcp-ssot.json: metasploit, sliver, burp, caldera, havoc,
  mythic, ghidra, ida, jadx (decepticon ×3 → mcp-http and hexstrike → mcp-stdio were
  already converted by the audit-fixes lane).
- Box survey (commands run): `where msfrpcd/msfconsole/sliver/burp` → nothing on PATH;
  `netstat -ano` on ports 55553/31337/9876/8890/40056/7443/8192/13337/8650 → nothing
  listening; `D:\opt\burp` and `AppData\Roaming\BurpSuite` ABSENT (Burp wiped in the
  reprovision — audit home-configs.md:32); no Ghidra/IDA/jadx installs anywhere
  (targeted `find` over C:/D: roots); `out/research/sliver-client.exe` v1.7.7
  (`sliver-client.exe version` → `v1.7.7 - 0aa7e5bf…`) with a working `mcp` stdio
  subcommand (`sliver-client.exe mcp --help` → "Start the MCP stdio server") per the
  research note out/research/dive-Sliver--native-MCP-server-.md; GhidraMCP bridge
  script present at `C:\Users\prekzursil\.local\opt\ghidra-mcp\GhidraMCP-release-1-4\bridge_mcp_ghidra.py`
  (stdio FastMCP proxying the Ghidra plugin's HTTP :8080), but its staged `.venv` is
  broken (base interpreter `pythoncore-3.14-64` gone) — the estate interpreter
  `C:\Python314\python.exe` carries `mcp` + `requests 2.34.2` + `msgpack 1.1.2`, so the
  bridge runs on it directly.
- Pre-existing estate env pair `MSF_API_USER` / `MSF_API_PASSWORD` found in HKCU
  Environment (values read locally only; not reproduced here) — used as the metasploit
  credential source.

## 1. Gateway changes (D:\opt\cyberstrike-mcp\gateway-server.py)

1. **kind=rpc removed as a class** — both the TCP-open probe branch and the stub
   dispatch branch are gone; `grep "kind.*rpc"` over the file returns nothing.
2. **kind=msgrpc added** (metasploit): real msgpack-rpc client (`msgpack` 1.1.2 already
   on the estate interpreter — no new deps). `_msf_roundtrip` frames
   `[0, msgid, method, params]` → `[1, msgid, result, error]` over a fresh TCP
   connection (SSL if `rpc.ssl`), one connection per call so nothing is held open.
   `_msf_token` does `auth.login` from `rpc.username_env`/`rpc.password_env` env vars,
   caches per gateway process, and stale-token auth failures re-login once and retry.
   Probe `_msgrpc_probe` = connect + auth + `core.version` round-trip. Dispatch routes
   the harness_invoke tool name 1:1 onto the msgrpc method map; caller params ride in
   `arguments.params`. msf error hashes (`error_class`/`error_message`) are surfaced
   verbatim.
3. **kind=mcp-sse added** (burp): one-shot SSE MCP client (`mcp.client.sse.sse_client`)
   on the shared `_http_loop` (same one-shot-client loop as mcp-http; no new loop, no
   children). Handles Burp's root-path flavor — the installed SDK resolves the
   `endpoint` event's relative `?sessionId=` ref via `urljoin`
   (C:\Python314\Lib\site-packages\mcp\client\sse.py:84). Probe = initialize +
   tools/list. URL/port read from the SSOT row — nothing hardcoded.
4. **kind=unavailable added**: probe always reports unavailable with the row's
   `install_note` as the reason; harness_invoke would return the install_note.
5. **Probe cache made TTL-based** (`_AVAIL_TTL`, default 20s, env `GATEWAY_AVAIL_TTL`):
   the old sticky per-session cache could never show a server dying mid-session. Now a
   stale entry is re-probed on touch (same on-touch philosophy as worker reaping — no
   timers, no watchdog). This is what makes the required negative test pass without a
   gateway restart.
6. **Error flattening** `_flatten_error`: the one-shot MCP clients raise nested
   anyio ExceptionGroups whose leaf is the real connect error; probes and invoke
   errors now carry the leaf (e.g. `ConnectError: All connection attempts failed`)
   instead of `unhandled errors in a TaskGroup (1 sub-exception)`. Applied to both
   `_mcpsse_call` and `_mcphttp_call` (identical SDK wrapping, one shared formatter —
   the only factoring done; msgrpc and mcp-sse stay separate native transports).
7. `mcp-stdio` worker-pool internals untouched — sliver and ghidra were registered
   into the existing pool as ordinary rows.

## 2. SSOT changes (D:\opt\cyberstrike-mcp\mcp-ssot.json, version 6 → 7)

Per-backend outcomes (the ask's report format):

### metasploit — CONVERTED (kind=msgrpc)
- **Transport chosen**: native msgrpc msgpack-rpc over TCP 127.0.0.1:55553
  (`rpc{host,port,uri:/api/,ssl:false,username_env:MSF_API_USER,password_env:MSF_API_PASSWORD}`).
- **Probe result (steady state, no msfrpcd on this box)**: `unavailable — msgrpc
  127.0.0.1:55553 msgrpc auth failed: not listening: ConnectionRefusedError:
  [WinError 10061] No connection could be made because the target machine actively
  refused it` — the ask's required "msgrpc not listening" reason, with the real
  socket error.
- **Real invoke** (through 127.0.0.1:31100/mcp against a protocol-accurate local
  msgrpc test double, out/followup/msgrpc_testdouble.py — real msfrpcd is NOT
  installed on this box):
  - `harness_invoke("metasploit","core.version")` raw:
    `{"backend": "metasploit", "tool": "core.version", "mode": "msgrpc-client", "ok": true, "result": {"version": "6.3.42-testdouble", "ruby": "3.3.5 x64-mswin64", "api": "1.0"}}`
  - `core.stats` raw: `{"ok": true, "result": {"active": 0, "sessions": 0, "jobs": 0, "note": "msgrpc test double"}}`
  - error propagation: bad method raw: `{"ok": false, "error": "msgrpc call failed: NoMethodError: undefined method 'module.nonexistent'"}` — the wire's own error class/message surfaced.
- **Negative test**: double killed → after the 20s TTL the row flipped to unavailable
  with the WinError 10061 detail above (phase-2 run).
- **Converted-or-reclassified**: converted; lights up for real the day an operator
  starts msfrpcd (creds already in user env as MSF_API_USER/MSF_API_PASSWORD).

### sliver — CONVERTED (kind=mcp-stdio, existing worker pool)
- **Transport chosen**: native `sliver-client mcp` stdio (v1.7.7 mainline native MCP
  server, per out/research/dive-Sliver--native-MCP-server-.md). Binary installed to
  `C:\Users\prekzursil\.local\bin\sliver-client.exe` (from out/research; version
  re-verified after copy). No second pool — ordinary row in the existing mcp-stdio
  pool. HTTP-token fallback: NOT wired because no token/endpoint is configured on
  this box; the fallback rule is documented in the row note (flip to kind=mcp-http
  with the `mcp start --transport http` URL if ever configured).
- **Probe result**: `unavailable — mcp-stdio failed: spawn failed: McpError:
  Connection closed`. Underlying cause captured directly:
  `sliver-client.exe mcp` exits with `no config files found at
  C:\Users\prekzursil\.sliver-client\configs (use --config)` — no multiplayer
  operator config and no sliver-server exist on this box.
- **Real invoke raw response** (honest steady state):
  `{"error": "backend 'sliver' unavailable", "status": "unavailable", "detail": "mcp-stdio failed: spawn failed: McpError: Connection closed", "note": "…needs a multiplayer operator config AND a running sliver-server; neither exists on this box…"}`
  — requirement 4 satisfied: the real transport error, not a stub message. A real
  end-to-end tool call was not possible without installing a sliver-server; that is
  reported, not faked (no stand-in was put on the sliver row).
- **Negative test**: n/a (row never available); the flip direction (config+server →
  lights up) is exercised by construction of the pool, same as every mcp-stdio row.
- **Converted-or-reclassified**: converted.

### burp — CONVERTED (kind=mcp-sse)
- **Transport chosen**: Burp's MCP extension (PortSwigger BApp) SSE MCP at the ROOT
  path; url `http://127.0.0.1:9876` read from the SSOT row — port not hardcoded
  (transport shape per the estate burp-mcp skill: GET / streams `endpoint` events,
  JSON-RPC frames POST to `?sessionId=…`).
- **Probe result (steady state)**: `unavailable — mcp-sse http://127.0.0.1:9876
  failed: unhandled errors in a TaskGroup: ConnectError: All connection attempts
  failed` — Burp is not installed on this box post-reprovision (D:/opt/burp and
  AppData/Roaming/BurpSuite absent; :9876 closed).
- **Real invoke** (through 31100/mcp against a Burp-flavored SSE test double,
  out/followup/sse_testdouble.py — SSE stream served at "/", messages at /message,
  exactly the extension's shape):
  `harness_invoke("burp","ping")` raw:
  `{"backend": "burp", "tool": "ping", "mode": "mcp-sse-one-shot", "ok": true, "result": "pong-from-burp-sse-test-double"}`
  and the probe detail during that window: `mcp-sse http://127.0.0.1:9876 (2 tools)`.
- **Negative test (this lane's demonstrated flip)**: double killed → after the TTL the
  row flipped to unavailable with the ConnectError detail above, and
  `harness_invoke("burp","ping")` returned
  `{"error": "backend 'burp' unavailable", "status": "unavailable", "detail": "mcp-sse … ConnectError: All connection attempts failed", "note": "…Burp is NOT installed on this box post-reprovision…"}`.
- **Converted-or-reclassified**: converted; lights up when the operator restores Burp
  + the BApp (no gateway change needed).

### ghidra — CONVERTED (kind=mcp-stdio, existing worker pool)
- **Transport chosen**: the bridge's actual transport — stdio FastMCP
  (`bridge_mcp_ghidra.py`), run on the estate interpreter
  `C:\Python314\python.exe …\GhidraMCP-release-1-4\bridge_mcp_ghidra.py` (the staged
  .venv is broken; estate interpreter carries mcp+requests). The old rpc port 8192 was
  wrong for this bridge — it proxies the Ghidra plugin's HTTP endpoint on 127.0.0.1:8080
  (bridge_mcp_ghidra.py:17 `DEFAULT_GHIDRA_SERVER = "http://127.0.0.1:8080/"`).
- **Probe result**: `available — mcp-stdio worker (27 tools)` — a REAL
  initialize/tools-list round-trip with the spawned bridge (same availability
  semantics as binary-ninja/ida-pro/cheatengine: the Ghidra app itself is not
  installed, so tool CALLS surface the bridge's real connection error).
- **Real invoke raw response** (Ghidra absent — the bridge's own real error, not a
  gateway stub):
  `harness_invoke("ghidra","list_segments",{offset:0,limit:5})` raw:
  `{"backend": "ghidra", "tool": "list_segments", "mode": "mcp-stdio-managed-worker", "ok": true, "result": "Request failed: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /list_segments?offset=0&limit=5 (Caused by NewConnectionError(\"…[WinError 10061] …actively refused it\"))"}`
- **Negative test**: the app-level negative is inherent (calls fail with the real
  bridge error until Ghidra runs); row-level flip n/a (the bridge, which IS the
  row's server, stays spawnable).
- **Converted-or-reclassified**: converted. Net effect: +1 real available row.

### ida — RECLASSIFIED (kind=unavailable)
- The :13337 endpoint this row pointed at is the ida-pro-mcp plugin bridge, which is
  ALREADY dispatched for real through the existing `ida-pro` row (kind=mcp-stdio,
  npx ida-pro-mcp). Keeping a second row for the same plugin would double-book it
  (the audit's §1.3 sin). install_note says exactly this and points callers at
  `harness_invoke('ida-pro', …)`; IDA itself is not installed either way.

### jadx — RECLASSIFIED (kind=unavailable)
- No jadx anywhere on the box (targeted find: nothing; nothing listens on :8650).
  install_note: when the jadx MCP bridge is installed it speaks stdio MCP and belongs
  in the mcp-stdio pool — it must not return as kind=rpc.

### caldera / havoc / mythic — RECLASSIFIED (kind=unavailable each)
- None installed; nothing listening on 8890/40056/7443. caldera's old port was an
  unverified placeholder whose TCP-open probe once read "available" off hexstrike's
  socket (audit §1.3 false positive) — that can't recur. Each install_note names the
  native transport to wire when an operator stands the server up (caldera REST /
  havoc REST / mythic GraphQL), as its own kind — never a revived TCP-open rpc row.

## 3. Verification (exact commands and outcomes)

1. **Direct transport tests** (doubles up, before gateway restart):
   `MSF_RPC_USER=msf MSF_RPC_PASS=msf-test-pass C:\Python314\python.exe out/followup/_transport_direct_test.py`
   → `RESULT: PASS` — msgrpc probe/auth/core.version/core.stats + real NoMethodError
   surfacing; mcp-sse probe (2 tools) + ping; TTL cache semantics; SSOT census with 0
   rpc rows.
2. **Phase-1 e2e through the live gateway** (`_e2e_phase1.py` via
   http://127.0.0.1:31100/mcp, doubles up): all converted/reclassified rows honest;
   real invokes with raw responses reproduced above; `kind=rpc rows remaining: NONE`;
   `PHASE-1 RESULT: PASS`.
3. **Phase-2 negative flip test** (`_e2e_phase2.py`, doubles killed, waited 24s > 20s
   TTL, NO gateway restart): metasploit → `unavailable … not listening:
   ConnectionRefusedError: [WinError 10061]…`; burp → `unavailable … ConnectError:
   All connection attempts failed`; invoke against dead burp returns that real
   transport error. `PHASE-2 RESULT: PASS`.
4. **Final steady state** (`_e2e_final.py`, fresh gateway, no doubles):
   `FINAL-STATE RESULT: PASS` — ghidra available (27 tools); all 8 other
   converted/reclassified rows unavailable with real reasons; 0 rpc rows.
5. **verify_stack.py** (the ask's named check, run twice — once mid-lane and once
   against the final gateway instance):
   `C:\Python314\python.exe D:\opt\cyberstrike-mcp\verify_stack.py` →
   `gateway tools: ['harness_bridge_status', 'harness_capabilities', 'harness_invoke']`,
   `AVAILABLE backends (30)`, `unavailable (24)`, all five probes `OK`,
   **`FAILURES: none`**.
6. **netstat 0.0.0.0 check**: captured `netstat -ano | grep 0.0.0.0: | grep LISTEN`
   before and after the whole lane (netstat_before.txt / netstat_after.txt). True
   0.0.0.0-local bindings: 16 before, 16 after, **identical lines** — no converted
   backend added a 0.0.0.0 binding (the only diffs were my two 127.0.0.1-bound test
   doubles disappearing and the gateway's pid change on 127.0.0.1:31100).
7. **Gateway restarts** used exactly the prescribed flow:
   `powershell -NoProfile -File D:/opt/cyberstrike-mcp/gateway-stop.ps1` then
   `Start-ScheduledTask -TaskName CyberStrikeGateway` (three times across the lane;
   final listener pid 50376 on 127.0.0.1:31100). No new processes, timers, or
   watchdogs were introduced; test doubles were killed after use.

## 4. New SSOT row count and census

- **54 rows total** (`catalogs.total_backends` corrected 53 → 54 to match the measured
  array; `specialized_total` corrected 20 → 19 measured). Kind census:
  `module 19, mcp-stdio 17 (+sliver, +ghidra), binary 8, mcp-http 3, msgrpc 1
  (+metasploit), mcp-sse 1 (+burp), unavailable 5 (ida, jadx, caldera, havoc, mythic)`
  — **kind=rpc: 0**. Availability: 30 available / 24 unavailable, every "available"
  backed by a real round-trip.
- SSOT backup: `mcp-ssot.json.bak-rpcdispatch-20260930` (pre-lane state).

## 5. Not done / limits (stated, not faked)

- metasploit and burp invokes were proven against clearly-labeled, protocol-accurate
  local test doubles (out/followup/msgrpc_testdouble.py, sse_testdouble.py) because
  neither msfrpcd nor Burp exists on this box; both doubles are killed and both rows
  settle to unavailable with real connection errors. A real msfrpcd/Burp round-trip
  was NOT possible on this box.
- sliver: no real tool call possible (no sliver-server/config); the row's honest
  state and the underlying `no config files found … (use --config)` error are
  recorded instead. No stand-in was wired into the sliver row.
- The ask's sliver HTTP-token fallback is documented in the row note, not wired:
  no token/endpoint is configured on this box, and wiring a dead path would be
  speculative abstraction.
- The dead `kind=env` probe branch noted by the audit (no row uses it) was left
  untouched — outside this lane's scope.
- verify_stack.py itself was not modified (not required by the ask); counts it
  prints come from the gateway's honest manifest.

## 6. Artifacts

- Gateway: `D:\opt\cyberstrike-mcp\gateway-server.py` (msgrpc + mcp-sse + unavailable
  kinds, TTL probe cache, error flattening, rpc stub removed).
- SSOT: `D:\opt\cyberstrike-mcp\mcp-ssot.json` v7 (54 rows, 0 rpc).
- Test doubles + scripts: `out/followup/{msgrpc_testdouble.py, sse_testdouble.py,
  _transport_direct_test.py, _e2e_phase1.py, _e2e_phase2.py, _e2e_final.py,
  _ssot_rpcdispatch.py, netstat_before.txt, netstat_after.txt, msgrpc_double.log,
  sse_double.log}`.