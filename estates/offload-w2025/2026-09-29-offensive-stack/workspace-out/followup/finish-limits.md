# Lane report: finish-limits — close rpc-dispatch §5

Date: 2026-09-30. Scope from the ask: close the four honestly-stated §5 limits of
out/followup/rpc-dispatch.md — the dead kind=env probe branch, the sliver
end-to-end, the metasploit/burp revival notes, and a fresh verify_stack count.

Sibling-lane note: a parallel repair lane (same finish-limits dispatch, after the
17:40 commit-exhaustion crash — see §2) edited mcp-ssot.json (sliver row env
GOGC/GOMEMLIMIT + note appendix) and gateway-server.py (WORKER_RSS_CAP_MB=6144
on-touch reap, gateway-server.py:118,271-318) and restarted the gateway at
19:08:33 (listener pid 15272). That file lineage includes this lane's edits;
both changes coexist in the running gateway. All final-state checks below were
run against that post-19:08 gateway.

## 1. DEAD kind=env PROBE BRANCH — REMOVED

- Grep first, as the ask requires: `C:/Python314/python.exe` census over
  D:\opt\cyberstrike-mcp\mcp-ssot.json → `rows with kind=env: []`
  (kind census: module 19, mcp-stdio 17, binary 8, mcp-http 3, msgrpc 1,
  mcp-sse 1, unavailable 5 — 54 rows). The five rows carrying an `env` key
  (hacktricks, firecrawl, darknet, sqlmap-mcp, ffuf-mcp) use it as per-backend
  env-var injection for module/mcp-stdio kinds (gateway-server.py:40,202-203),
  NOT as a probe kind.
- Removed the `elif kind == "env":` branch (was gateway-server.py:90-92 pre-edit)
  and corrected the stale `_backend_manifest` docstring.
- `grep "kind.*env" gateway-server.py` → no matches (exit 1);
  `C:/Python314/python.exe -m py_compile D:\opt\cyberstrike-mcp\gateway-server.py`
  → OK.
- Restart via the prescribed flow: `powershell -NoProfile -File
  D:/opt/cyberstrike-mcp/gateway-stop.ps1` (stopped pid 50376) then
  `Start-ScheduledTask -TaskName CyberStrikeGateway`; listener came back on
  127.0.0.1:31100 (then pid 50292).
- verify_stack.py right after → `FAILURES: none` (AVAILABLE 30 at that moment).

## 2. SLIVER REAL END-TO-END — DONE, REAL ROUND-TRIP

### Server install (official binary, loopback)
- Release verified via GitHub API
  (`api.github.com/repos/BishopFox/sliver/releases/tags/v1.7.7`, published
  2026-09-03): asset `sliver-server_windows-amd64.exe` (324.7 MB) EXISTS —
  the "binary unavailable for windows/amd64" failure mode did not occur.
- Downloaded from
  `https://github.com/BishopFox/sliver/releases/download/v1.7.7/sliver-server_windows-amd64.exe`
  (+ its .minisig, saved in out/tmp/). sha256
  `f95ae5de798943dd01e9145233c06b7b69c039ffe22fe9f9b4bfd1c349bcd3ff`.
  Installed at `D:\opt\sliver\sliver-server.exe`; `version` →
  `v1.7.7 - Compiled 2026-09-03 15:58:13 +0000 GMT - 0aa7e5bf962414823f12c3a8ea1f667f61b19ce2`
  — same version+commit as the existing client v1.7.7.
- First run: `sliver-server.exe daemon -l 127.0.0.1 -p 31337` — daemon mode
  (headless, `daemon --help`: "Force start server in daemon mode"; also
  bootstraps DB + certs on first boot under `~\.sliver\server`). Listener
  confirmed: `netstat -ano` → `127.0.0.1:31337 LISTENING` (pid 52632).
- Operator + multiplayer config: `D:\opt\sliver\sliver-server.exe operator -n
  localop -l 127.0.0.1 -p 31337 -P all -s
  C:\Users\prekzursil\.sliver-client\configs\localop.cfg` (plain `operator`
  without `-P` fails: "Must specify --permissions"). Config lands exactly where
  the client expects; contents: operator "localop", lhost 127.0.0.1, lport
  31337, mTLS CA/cert/key material (plaintext local-only per estate rule;
  token sha8 cbbe1219).
- Direct sanity: `~\.local\bin\sliver-client.exe sessions` one-shot →
  connected `grpc/mtls` to 127.0.0.1:31337, rendered the banner, exit 0.

### The 17:40 crash and the sibling fix (context, not this lane's work)
The first direct client run at 17:40 exhausted Windows commit charge (Go heap
retention) and the session was interrupted ("Tool execution was interrupted
before resume"). A sibling repair lane bounded the worker: sliver row env
`GOGC=20`, `GOMEMLIMIT=4GiB`, gateway `WORKER_RSS_CAP_MB=6144`. Observed
worker RSS after: ~36 MB (tasklist). No watchdog involved.

### Real gateway round-trip (out/followup/_sliver_e2e.py, run twice — final run
against the post-19:08 gateway, exit 0):
- Row: `status=available, detail: mcp-stdio worker (11 tools)` — a REAL
  initialize + tools-list round-trip with the spawned `sliver-client.exe mcp`
  worker over mTLS to the live server.
- `harness_invoke("sliver","__list__")` raw:
  `{"backend": "sliver", "tool": "__list__", "mode": "mcp-stdio-managed-worker",
   "ok": true, "tools": ["fs_cat","fs_cd","fs_chmod","fs_chown","fs_cp","fs_ls",
   "fs_mkdir","fs_mv","fs_pwd","fs_rm","list_sessions_and_beacons"]}` — the
  REAL native tool surface (matches research note §5: 11 tools).
- One trivial real tool call, `harness_invoke("sliver","list_sessions_and_beacons")`
  raw: `{"backend": "sliver", "tool": "list_sessions_and_beacons", "mode":
  "mcp-stdio-managed-worker", "ok": true, "result": "{\"sessions\":[],
  \"sessions_count\":0,\"beacons\":[],\"beacons_count\":0}"}` — a real
  RPC round-trip to the live server (zero sessions because no implants exist;
  a real zero, not a stub).
- Script output kept at out/followup/_sliver_e2e.out. Final line:
  `SLIVER-E2E RESULT: PASS`.

### Server lifecycle — START ON DEMAND (no watchdog, no scheduled task)
- `D:\opt\sliver\start-sliver-server.ps1` — documented start script (idempotent:
  checks :31337 first). Underlying command: `sliver-server.exe daemon -l
  127.0.0.1 -p 31337`. `D:\opt\sliver\stop-sliver-server.ps1` stops it.
- Loopback-only: daemon binds 127.0.0.1:31337 (mTLS); nothing on 0.0.0.0.
- When the server is down the row honestly flips back to unavailable after the
  20s probe TTL (spawn fails with the client's real error).
- SSOT sliver row note rewritten to this steady state (see §4).

## 3. METASPLOIT/BURP REVIVAL NOTES — WRITTEN, WITH A CORRECTED CLAIM

### msfrpcd — the §5 claim "no native Windows build" is OUTDATED (verified)
- Official docs (docs.metasploit.com .../nightly-installers.html, read this
  session): "Installers are built nightly for macOS, Windows (64-bit) and
  Linux." HEAD `https://windows.metasploit.com/metasploitframework-latest.msi`
  → 200 OK, 399,974,400 bytes, Last-Modified 2026-08-26.
- Definitive check (ran, not guessed): downloaded that MSI, listed it with
  7-Zip (MSI → Project.cab → inner zip) — it DOES ship `bin\msfrpcd.bat` and
  `bin\msfrpc.bat` (plus msfconsole/msfvenom/etc.). The .bat runs the bundled
  Ruby on `embedded\framework\msfrpcd` (bat extracted to out/tmp/msibats/).
- Caveat from source (fetched raw msfrpcd from rapid7/metasploit-framework
  master, out/tmp/msfrpcd_source.rb:84-97): background mode uses `Process.fork`
  and rescues `NotImplementedError` → "Background mode is not available on this
  platform" — msfrpcd on Windows is FOREGROUND-ONLY.
- install_note written to the metasploit row: primary plan = run msfrpcd on the
  future docker-era Linux host (`msfrpcd -U $MSF_API_USER -P $MSF_API_PASSWORD
  -S -a <listen-addr> -p 55553`; creds already in user env; `-S` matches
  rpc.ssl=false, uri /api/), point this row's rpc.host at it, restart gateway —
  probe + dispatch already real. Alternative recorded: Windows MSI +
  `msfrpcd.bat ... ` foreground from a documented start script (sliver pattern).
  No GUI software installed headlessly; nothing was installed.

### burp — claim VERIFIED
- PortSwigger docs page "Activating your Burp Suite license" (fetched this
  session): first launch = interactive wizard (paste license key; manual/offline
  flow is also wizard-driven); "No — nothing in the page documents CLI
  activation." Matches §5's claim.
- install_note written to the burp row: (1) operator installs Burp + completes
  first-run license acceptance interactively (never headless), (2) install the
  MCP BApp from the BApp store, (3) point it at 127.0.0.1:9876 (row's url),
  (4) no gateway change needed — the mcp-sse probe lights the row within the
  20s TTL.

## 4. SSOT + verification

- SSOT edits (out/followup/_ssot_finishlimits.py, applied; re-read to confirm):
  sliver note rewritten; metasploit + burp install_note keys added. 54 rows,
  kind census unchanged (0 rpc, 0 env). Backup:
  `D:\opt\cyberstrike-mcp\mcp-ssot.json.bak-finishlimits-20260930`.
- **verify_stack.py final run** (the ask's named check, against the current
  gateway): `C:\Python314\python.exe D:\opt\cyberstrike-mcp\verify_stack.py` →
  gateway tools ok; **AVAILABLE backends (31)** (previous lane: 30 — the +1 is
  sliver), **unavailable (23)**; all five probes OK; **`FAILURES: none`**.
- Gateway restarts this lane: 1 by this lane (17:26, prescribed flow); 1 by the
  sibling repair lane (19:08) — both via gateway-stop.ps1 +
  Start-ScheduledTask CyberStrikeGateway. No new timers/watchdogs/process
  classes introduced; sliver-server is an operator-owned, start-on-demand,
  loopback-only single process with a documented start script.

## 5. Not done / remaining limits (stated, not faked)

- No real msfrpcd/Burp round-trip: neither server was stood up (per the ask —
  revival notes only, no headless GUI installs). Both rows stay unavailable
  with real connection errors and now carry precise install_notes.
- The metasploit Windows-MSI alternative was verified as POSSIBLE (msfrpcd.bat
  ships, foreground-only) but not installed — heavy install, outside the ask.
- msfmcpd (a native MCP daemon now present in the metasploit repo root and in
  the MSI payload's framework tree) was noticed while verifying; not wired —
  out of scope for this ask (row is kind=msgrpc and works against msfrpcd).
- verify_stack.py itself unmodified; its counts come from the gateway manifest.

## 6. Artifacts

- D:\opt\cyberstrike-mcp\gateway-server.py (dead env branch removed; sibling's
  RSS cap coexists), mcp-ssot.json (sliver note, msf/burp install_notes) +
  .bak-finishlimits-20260930.
- D:\opt\sliver\{sliver-server.exe, start-sliver-server.ps1,
  stop-sliver-server.ps1}; C:\Users\prekzursil\.sliver-client\configs\localop.cfg.
- out/followup/{_sliver_e2e.py, _sliver_e2e.out, _ssot_finishlimits.py}.
- Evidence kept small: out/tmp/{sliver_rel.json, msfrpcd_source.rb, msibats/,
  sliver-server_windows-amd64.exe.minisig}. The 400MB MSI, its 422MB inner
  payload and the duplicate 325MB server exe were deleted after inspection.
