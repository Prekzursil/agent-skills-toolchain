#!/usr/bin/env python3
"""Direct transport tests for the rpc-dispatch lane (2026-09-30).

Loads the REAL gateway-server.py module (post-edit) and exercises the new
kind=msgrpc and kind=mcp-sse client transports against the local test doubles.
Run with the doubles already listening (55553, 9876).
"""
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location("gateway_server", r"D:\opt\cyberstrike-mcp\gateway-server.py")
gw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gw)

rows = {b["name"]: b for b in gw.SSOT["backends"]}
ok = True

print("== msgrpc (metasploit row) ==")
msf = rows["metasploit"]
assert msf["kind"] == "msgrpc", msf["kind"]
status, detail = gw._msgrpc_probe(msf)
print("probe:", status, "|", detail)
ok &= status == "available"
r1 = gw._msf_invoke(msf, "core.version", [], 10.0)
print("core.version:", json.dumps(r1, default=gw._msf_jsonable))
ok &= r1.get("ok") and "testdouble" in json.dumps(r1)
r2 = gw._msf_invoke(msf, "core.stats", [], 10.0)
print("core.stats:", json.dumps(r2, default=gw._msf_jsonable))
ok &= r2.get("ok")
r3 = gw._msf_invoke(msf, "module.nonexistent", [], 10.0)
print("bad method (expect real NoMethodError surfaced):", json.dumps(r3, default=gw._msf_jsonable))
ok &= not r3.get("ok") and "NoMethodError" in r3.get("error", "")

print("\n== mcp-sse (burp row) ==")
burp = rows["burp"]
assert burp["kind"] == "mcp-sse", burp["kind"]
status, detail = gw._mcpsse_probe(burp)
print("probe:", status, "|", detail)
ok &= status == "available"
r4 = gw._mcpsse_call(burp["url"], "ping", {}, 15.0)
print("ping:", json.dumps(r4))
ok &= r4.get("ok") and "pong" in r4.get("result", "")

print("\n== TTL cache semantics ==")
gw._AVAIL_TTL = 1.0
s1, d1 = gw._probe_availability(burp)
t_then = gw._AVAIL_CACHE["burp"][2]
s2, d2 = gw._probe_availability(burp)  # within TTL -> cached
ok &= (s1 == s2 == "available")
print("within TTL re-probe returns cached:", s2, "| cache entry age reused:", gw._AVAIL_CACHE["burp"][2] == t_then)

print("\n== kind census (SSOT must have zero kind=rpc) ==")
from collections import Counter
census = Counter(b["kind"] for b in gw.SSOT["backends"])
print(dict(census), "| rpc rows:", census.get("rpc", 0))
ok &= census.get("rpc", 0) == 0

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
