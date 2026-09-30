#!/usr/bin/env python3
"""finish-limits lane: SSOT v7 -> v8 edits.
1. sliver note: new steady state (server + config stood up; start on demand).
2. metasploit install_note: precise revival procedure, with the corrected
   Windows claim (nightly MSI DOES ship msfrpcd.bat; foreground-only).
3. burp install_note: precise revival procedure (GUI first run + BApp :9876).
"""
import json

P = r"D:\opt\cyberstrike-mcp\mcp-ssot.json"
d = json.load(open(P, encoding="utf-8"))
rows = {b["name"]: b for b in d["backends"]}

rows["sliver"]["note"] = (
    "finish-limits 2026-09-30: REAL end-to-end proven. sliver-server v1.7.7 "
    "(official BishopFox windows-amd64 release, sha256 "
    "f95ae5de798943dd01e9145233c06b7b69c039ffe22fe9f9b4bfd1c349bcd3ff, commit "
    "0aa7e5bf - same as the client) installed at D:\\opt\\sliver\\sliver-server.exe; "
    "first daemon run generated DB+certs under ~\\.sliver\\server; operator config "
    "localop.cfg (operator 'localop', permissions all, mTLS) generated via "
    "'sliver-server.exe operator -n localop -l 127.0.0.1 -p 31337 -P all -s "
    "C:\\Users\\prekzursil\\.sliver-client\\configs\\localop.cfg' and lives there "
    "(loopback-only). Server lifecycle: START ON DEMAND - run "
    "D:\\opt\\sliver\\start-sliver-server.ps1 (sliver-server.exe daemon -l 127.0.0.1 "
    "-p 31337; stop-sliver-server.ps1 to stop; no watchdog, no scheduled task). "
    "Verified through the gateway with the server up: row available (11 tools), "
    "harness_invoke('sliver','__list__') returns the real tool list (fs_cat, fs_cd, "
    "fs_chmod, fs_chown, fs_cp, fs_ls, fs_mkdir, fs_mv, fs_pwd, fs_rm, "
    "list_sessions_and_beacons) and list_sessions_and_beacons round-trips to the "
    "live server ({\"sessions\":[],\"sessions_count\":0,...} - no implants yet, "
    "real zero). When the server is down the row flips back to unavailable after "
    "the 20s probe TTL (spawn fails with the client's real connection error). "
    "HTTP fallback rule unchanged: if a token-authed MCP endpoint is ever "
    "configured ('mcp start --transport http', token in <rootAppDir>/mcp.yaml), "
    "flip to kind=mcp-http with that URL."
)

rows["metasploit"]["install_note"] = (
    "REVIVAL (finish-limits 2026-09-30, claim re-verified): the old 'msfrpcd has "
    "no native Windows build' claim is OUTDATED - the current nightly Windows MSI "
    "(https://windows.metasploit.com/metasploitframework-latest.msi, ~400MB, built "
    "2026-08-26) DOES ship bin\\msfrpcd.bat and bin\\msfrpc.bat (verified this "
    "session by downloading the MSI and listing its payload; the .bat runs the "
    "bundled Ruby on embedded\\framework\\msfrpcd). Caveat from source "
    "(rapid7/metasploit-framework msfrpcd, start_rpc_service): background mode "
    "uses Process.fork and rescues NotImplementedError -> on Windows msfrpcd runs "
    "FOREGROUND-ONLY ('Background mode is not available on this platform'). "
    "ESTATE PLAN (primary): run msfrpcd on the future docker-era Linux host: "
    "msfrpcd -U $MSF_API_USER -P $MSF_API_PASSWORD -S -a <listen-addr> -p 55553 "
    "(creds already in this user's env pair MSF_API_USER / MSF_API_PASSWORD; -S "
    "matches this row's rpc.ssl=false, uri /api/), then point this row's rpc.host "
    "at that host and restart the gateway - probe + dispatch are already real. "
    "ALTERNATIVE on this box: install the Windows MSI, then run "
    "C:\\metasploit-framework\\bin\\msfrpcd.bat -U %MSF_API_USER% -P "
    "%MSF_API_PASSWORD% -S -a 127.0.0.1 -p 55553 in the foreground from a "
    "documented start script (sliver-server pattern) - not done this lane (heavy "
    "install, not asked). Until then this row honestly reports unavailable: "
    "msgrpc 127.0.0.1:55553 not listening (WinError 10061)."
)

rows["burp"]["install_note"] = (
    "REVIVAL (finish-limits 2026-09-30, claim verified): Burp Suite's first run "
    "requires the INTERACTIVE activation wizard - paste license key (or the "
    "manual offline flow, also wizard-driven); no CLI-only activation is "
    "documented (portswigger.net/burp/documentation/desktop/getting-started/"
    "activating-burp-license, read this session). Therefore Burp must be "
    "installed and activated by the operator in the GUI - never headlessly. "
    "Procedure: (1) operator installs Burp Suite and completes first-run license "
    "acceptance interactively; (2) install the Burp MCP extension (PortSwigger "
    "BApp store) via Extensions -> BApp Store; (3) configure the extension's MCP "
    "service to listen on 127.0.0.1:9876 (this row's url - GET / streams "
    "'endpoint' events, JSON-RPC frames POST to ?sessionId=...); (4) no gateway "
    "change needed - the mcp-sse probe does a real initialize + tools/list and "
    "the row lights up within the 20s TTL."
)

json.dump(d, open(P, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("SSOT updated: sliver note, metasploit + burp install_note; "
      "rows=%d" % len(d["backends"]))
