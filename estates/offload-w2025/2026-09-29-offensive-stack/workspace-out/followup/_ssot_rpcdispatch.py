#!/usr/bin/env python3
"""rpc-dispatch lane 2026-09-30: transform mcp-ssot.json kind=rpc rows.

Every remaining kind=rpc row either gains its real native transport or is
reclassified kind=unavailable with an install_note. kind=rpc dies as a class.
"""
import json
import shutil

SSOT = r"D:\opt\cyberstrike-mcp\mcp-ssot.json"
shutil.copyfile(SSOT, SSOT + ".bak-rpcdispatch-20260930")

with open(SSOT, encoding="utf-8") as f:
    ssot = json.load(f)

rows = {b["name"]: b for b in ssot["backends"]}

# --- metasploit: real msgrpc msgpack-rpc client transport -------------------
rows["metasploit"].update({
    "kind": "msgrpc",
    "rpc": {
        "host": "127.0.0.1",
        "port": 55553,
        "uri": "/api/",
        "ssl": False,
        "username_env": "MSF_RPC_USER",
        "password_env": "MSF_RPC_PASS",
    },
    "note": ("rpc-dispatch 2026-09-30: native msgrpc transport (msgpack-rpc over TCP, "
             "msfrpcd-owned). Probe = connect + auth.login + core.version round-trip; "
             "dispatch routes the harness_invoke tool name 1:1 onto the msgrpc method "
             "map with caller params in arguments.params. Credentials come from "
             "MSF_RPC_USER / MSF_RPC_PASS (the msfrpcd -U/-P values). msfrpcd is NOT "
             "installed on this box, so the row honestly reports unavailable: "
             "'msgrpc not listening' until the operator starts one."),
})

# --- sliver: native sliver-client mcp stdio (v1.7.7) ------------------------
rows["sliver"].pop("rpc", None)
rows["sliver"].update({
    "kind": "mcp-stdio",
    "entry": "sliver-client mcp",
    "command": [
        "C:\\Users\\prekzursil\\.local\\bin\\sliver-client.exe",
        "mcp",
    ],
    "note": ("rpc-dispatch 2026-09-30: native MCP transport - sliver-client v1.7.7 'mcp' "
             "subcommand, stdio, into the existing mcp-stdio worker pool (no second pool). "
             "Binary installed at ~/.local/bin/sliver-client.exe (v1.7.7, commit "
             "0aa7e5bf, from out/research per the sliver native-MCP research note). Needs a "
             "multiplayer operator config in ~/.sliver-client/configs AND a running "
             "sliver-server; neither exists on this box, so spawn fails with the client's "
             "real error and the row stays unavailable until the operator stands them up. "
             "HTTP fallback rule (per research note): if a token-authed MCP endpoint is ever "
             "configured (sliver 'mcp start --transport http', token in <rootAppDir>/mcp.yaml), "
             "flip this row to kind=mcp-http with that URL - not wired now because no token "
             "is configured on this box."),
})

# --- burp: Burp MCP extension SSE endpoint ----------------------------------
rows["burp"].pop("rpc", None)
rows["burp"].update({
    "kind": "mcp-sse",
    "url": "http://127.0.0.1:9876",
    "note": ("rpc-dispatch 2026-09-30: native transport = Burp Suite MCP extension "
             "(PortSwigger BApp) SSE MCP served at the ROOT path of the configured port "
             "(GET / streams 'endpoint' events; JSON-RPC frames POST to ?sessionId=...). "
             "Port read from this row's url - not hardcoded in the gateway. Probe = real "
             "SSE initialize + tools/list handshake. Burp is NOT installed on this box "
             "post-reprovision (D:/opt/burp and AppData/Roaming/BurpSuite absent, :9876 "
             "closed - audit home-configs.md:32), so the row honestly reports unavailable "
             "with the real connection error until the operator restores Burp + the BApp."),
})

# --- ghidra: LaurieWired GhidraMCP stdio bridge ------------------------------
rows["ghidra"].pop("rpc", None)
rows["ghidra"].update({
    "kind": "mcp-stdio",
    "entry": "bridge_mcp_ghidra.py",
    "command": [
        "C:\\Python314\\python.exe",
        "C:\\Users\\prekzursil\\.local\\opt\\ghidra-mcp\\GhidraMCP-release-1-4\\bridge_mcp_ghidra.py",
    ],
    "note": ("rpc-dispatch 2026-09-30: native transport = LaurieWired GhidraMCP bridge "
             "(stdio FastMCP, proxies the Ghidra plugin's HTTP endpoint on 127.0.0.1:8080). "
             "Runs on the estate interpreter (the staged .venv is broken - its base "
             "pythoncore-3.14-64 path no longer exists; C:\\Python314 carries mcp+requests). "
             "Old rpc port 8192 was wrong for this bridge. Same availability semantics as "
             "binary-ninja/ida-pro/cheatengine: bridge spawns + initialize/tools-list => "
             "available; with the Ghidra app absent every tool call surfaces the bridge's "
             "real 'Request failed' connection error. Plugin jar staged at "
             "~/.local/opt/ghidra-mcp/_lauriewired_12.0.3_fallback."),
})

# --- RE bridges with nothing on this box: reclassify --------------------------
rows["ida"].pop("rpc", None)
rows["ida"].update({
    "kind": "unavailable",
    "install_note": ("rpc-dispatch 2026-09-30: duplicate row - the ida-pro-mcp plugin bridge "
                     "on :13337 is ALREADY dispatched for real through the 'ida-pro' row "
                     "(kind=mcp-stdio, npx ida-pro-mcp). Use harness_invoke('ida-pro', ...). "
                     "IDA itself is not installed on this box either way."),
})

rows["jadx"].pop("rpc", None)
rows["jadx"].update({
    "kind": "unavailable",
    "install_note": ("rpc-dispatch 2026-09-30: no jadx on this box (no install, nothing "
                     "listening on :8650). When the jadx MCP bridge is installed it speaks "
                     "stdio MCP and belongs in the mcp-stdio pool (command = its bridge "
                     "script); it must not return as kind=rpc."),
})

rows["caldera"].pop("rpc", None)
rows["caldera"].update({
    "kind": "unavailable",
    "install_note": ("rpc-dispatch 2026-09-30: no caldera on this box; the old rpc port 8890 "
                     "was an unverified placeholder (audit stack-wiring 1.3 - it once probed "
                     "'available' off hexstrike's socket on 8888, a false positive). When an "
                     "operator stands CALDERA up, wire its native REST API as its own kind; "
                     "do not revive a TCP-open rpc row."),
})

rows["havoc"].pop("rpc", None)
rows["havoc"].update({
    "kind": "unavailable",
    "install_note": ("rpc-dispatch 2026-09-30: no havoc on this box (nothing listening on "
                     ":40056). When stood up, wire its native REST API as its own kind; a "
                     "TCP-open rpc row must not return."),
})

rows["mythic"].pop("rpc", None)
rows["mythic"].update({
    "kind": "unavailable",
    "install_note": ("rpc-dispatch 2026-09-30: no mythic on this box (nothing listening on "
                     ":7443). When stood up, wire its native GraphQL HTTPS API as its own "
                     "kind; a TCP-open rpc row must not return."),
})

ssot["version"] = 7
ssot["generated"] = "2026-09-30"
ssot["design"] = ssot["design"].replace(
    "Backends are dispatch descriptors: kind=module (imported in-process) or kind=binary "
    "(spawned per invocation, reaped on return).",
    "Backends are dispatch descriptors: kind=module (imported in-process), kind=binary "
    "(spawned per invocation, reaped on return), kind=mcp-stdio (managed worker pool), "
    "kind=mcp-http / kind=mcp-sse (one-shot MCP clients to operator-owned servers), "
    "kind=msgrpc (metasploit msgpack-rpc client) or kind=unavailable (no real transport "
    "on this box; carries install_note). The kind=rpc stub class was removed 2026-09-30: "
    "available ALWAYS means a real protocol round-trip succeeded.")
ssot["catalogs"]["policy"] = ssot["catalogs"]["policy"].replace(
    "module importable / binary on PATH / rpc reachable / mcp-stdio worker spawn+initialize / mcp-http initialize handshake",
    "module importable / binary on PATH / mcp-stdio worker spawn+initialize / mcp-http initialize handshake / "
    "mcp-sse initialize handshake / msgrpc auth+core.version round-trip; kind=unavailable rows carry install_note")

with open(SSOT, "w", encoding="utf-8") as f:
    json.dump(ssot, f, indent=2, ensure_ascii=False)
    f.write("\n")

# report the new kind census
from collections import Counter
census = Counter(b["kind"] for b in ssot["backends"])
print("rows:", len(ssot["backends"]))
print("kind census:", dict(census))
print("kind=rpc remaining:", census.get("rpc", 0))
