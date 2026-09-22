"""Gateway skeleton probe battery — proves the routing layer per wiring_plan.
Read-only against the gateway + one read-only cve tool call. Emits a JSON result
block consumed by the lane receipt. One process, sequential probes."""
import json
import socket
import sys
import time

sys.path.insert(0, r"C:\Users\Prekzursil\.config\cyberstrike\gateway")
from gen_routes import _sock_exchange  # noqa: E402

GW = ("127.0.0.1", 31150)
OUT_PATH = r"D:\bolt\admin-crack-2026-09-19\raw\cs-sota\gw-probe-battery_2026-09-22.json"
results: dict = {"probes": []}


def probe(label: str, fn):
    t0 = time.monotonic()
    try:
        detail = fn()
        ms = round((time.monotonic() - t0) * 1000, 1)
        results["probes"].append({"probe": label, "ok": True, "ms": ms, "detail": detail})
        print(f"OK   {label} ({ms}ms)")
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        results["probes"].append({"probe": label, "ok": False, "ms": ms,
                                  "error": f"{type(e).__name__}: {e}"[:200]})
        print(f"FAIL {label} ({ms}ms): {type(e).__name__}: {e}"[:160])


def http(method, path, body=None, headers=None, host="cs-gateway"):
    s = socket.create_connection(GW, timeout=20)
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream",
         "Connection": "close"}
    h.update(headers or {})
    st, rh, b = _sock_exchange(s, method, path, host,
                               (json.dumps(body).encode() if body is not None else b""),
                               h, 20)
    s.close()
    return st, rh, b


def sse_json(b: bytes):
    t = b.decode("utf-8", "replace").strip()
    if t.startswith("{"):
        return json.loads(t)
    for ln in t.splitlines():
        if ln.startswith("data:"):
            try:
                return json.loads(ln[5:].strip())
            except json.JSONDecodeError:
                continue
    return {}


def p_health():
    st, _rh, b = http("GET", "/health")
    d = json.loads(b)
    assert st == 200 and d["status"] == "ok", (st, d)
    return d


def p_catalog():
    st, _rh, b = http("GET", "/catalog")
    d = json.loads(b)
    assert st == 200 and len(d) == 51, (st, len(d))
    kinds = {}
    for r in d:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    return {"routes": len(d), "kinds": kinds,
            "cve_row": next(r for r in d if r["name"] == "cve")}


def p_dead():
    st, _rh, b = http("GET", "/dead")
    d = json.loads(b)
    assert st == 200, st
    return {"dead_or_poisoned": [r["server"] for r in d]}


def p_meta_initialize():
    st, rh, b = http("POST", "/mcp/gateway",
                     {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "probe", "version": "1"}}})
    d = sse_json(b)
    assert st == 200 and d["result"]["serverInfo"]["name"] == "cs-gateway-skeleton", (st, d)
    return {"serverInfo": d["result"]["serverInfo"]}


def p_meta_tools_list():
    st, _rh, b = http("POST", "/mcp/gateway",
                      {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    d = sse_json(b)
    names = [t["name"] for t in d["result"]["tools"]]
    assert st == 200 and names == ["gateway.catalog", "gateway.dead_list"], (st, names)
    return {"tools": names}


def p_meta_dead_list_call():
    st, _rh, b = http("POST", "/mcp/gateway",
                      {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                       "params": {"name": "gateway.dead_list", "arguments": {}}})
    d = sse_json(b)
    text = d["result"]["content"][0]["text"]
    servers = [r["server"] for r in json.loads(text)]
    assert st == 200, st
    return {"dead_servers": servers}


def p_cve_initialize_and_list():
    st, rh, b = http("POST", "/mcp/cve",
                     {"jsonrpc": "2.0", "id": 10, "method": "initialize",
                      "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "probe", "version": "1"}}})
    sid = rh.get("mcp-session-id")
    assert st == 200 and sid, ("no session from gateway-proxied initialize", st, rh)
    d = sse_json(b)
    assert d["result"]["serverInfo"]["name"] == "cve-mcp", d
    # tools/list THROUGH the gateway WITH the session (affinity proof)
    st2, rh2, b2 = http("POST", "/mcp/cve",
                        {"jsonrpc": "2.0", "id": 11, "method": "tools/list"},
                        headers={"Mcp-Session-Id": sid})
    d2 = sse_json(b2)
    tools = [t["name"] for t in d2["result"]["tools"]]
    assert st2 == 200 and tools, ("tools/list via gateway failed", st2, b2[:200])
    return {"session_passed_through": sid[:8] + "...", "front": "cve-mcp",
            "n_tools": len(tools), "tools_sample": tools[:6]}


def p_cve_tool_call():
    # read-only lookup through the full chain (client -> gw -> front -> tool)
    st, rh, b = http("POST", "/mcp/cve",
                     {"jsonrpc": "2.0", "id": 10, "method": "initialize",
                      "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "probe", "version": "1"}}})
    sid = rh.get("mcp-session-id")
    st2, _rh, b2 = http("POST", "/mcp/cve",
                        {"jsonrpc": "2.0", "id": 11, "method": "tools/list"},
                        headers={"Mcp-Session-Id": sid})
    tool = next((t["name"] for t in sse_json(b2)["result"]["tools"]
                 if "cve" in t["name"].lower() and "get" in t["name"].lower()), None)
    if tool is None:
        tool = next((t["name"] for t in sse_json(b2)["result"]["tools"]
                     if "search" in t["name"].lower() or "lookup" in t["name"].lower()), None)
    assert tool, "no read-only-looking cve tool found"
    st3, _rh3, b3 = http("POST", "/mcp/cve",
                         {"jsonrpc": "2.0", "id": 12, "method": "tools/call",
                          "params": {"name": tool,
                                     "arguments": {"cve_id": "CVE-2021-44228"}
                                     if "cve_id" in json.dumps(sse_json(b2)["result"]["tools"])[:4000]
                                     else {"query": "CVE-2021-44228", "limit": 1}}},
                         headers={"Mcp-Session-Id": sid})
    d3 = sse_json(b3)
    body = json.dumps(d3)[:300]
    assert st3 == 200 and ("result" in d3), ("tool call via gateway failed", st3, body)
    return {"tool": tool, "status": st3, "resp_head": body[:200]}


def p_unknown_route_404():
    st, _rh, b = http("POST", "/mcp/definitely-not-a-server",
                      {"jsonrpc": "2.0", "id": 20, "method": "tools/list"})
    assert st == 404, st
    return {"status": 404, "body": b.decode("utf-8", "replace")[:120]}


def p_remote_auth_501():
    st, _rh, b = http("POST", "/mcp/context7",
                      {"jsonrpc": "2.0", "id": 21, "method": "initialize",
                       "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                  "clientInfo": {"name": "probe", "version": "1"}}})
    assert st == 501, st
    return {"status": 501, "body": b.decode("utf-8", "replace")[:140]}


def p_latency_vs_direct():
    """Proof #2: gateway hop overhead vs direct front call (same tools/list)."""
    lat = {}
    for lane in ("direct", "gateway"):
        times = []
        sid = None
        if lane == "gateway":
            _st, rh, _b = http("POST", "/mcp/cve",
                               {"jsonrpc": "2.0", "id": 30, "method": "initialize",
                                "params": {"protocolVersion": "2025-03-26",
                                           "capabilities": {},
                                           "clientInfo": {"name": "probe", "version": "1"}}})
            sid = rh.get("mcp-session-id")
        for _ in range(5):
            t0 = time.monotonic()
            if lane == "direct":
                s = socket.create_connection(("127.0.0.1", 31111), timeout=20)
                _sock_exchange(s, "POST", "/mcp", "front",
                               json.dumps({"jsonrpc": "2.0", "id": 31,
                                           "method": "tools/list"}).encode(),
                               {"Content-Type": "application/json",
                                "Accept": "application/json, text/event-stream",
                                "Connection": "close"}, 20)
                s.close()
            else:
                http("POST", "/mcp/cve",
                     {"jsonrpc": "2.0", "id": 31, "method": "tools/list"},
                     headers={"Mcp-Session-Id": sid})
            times.append((time.monotonic() - t0) * 1000)
        lat[lane] = [round(t, 1) for t in sorted(times)]
    return {"direct_ms": lat["direct"], "gateway_ms": lat["gateway"],
            "delta_p50_ms": round(lat["gateway"][2] - lat["direct"][2], 1)}


probe("health", p_health)
probe("catalog", p_catalog)
probe("dead_list", p_dead)
probe("meta.initialize", p_meta_initialize)
probe("meta.tools/list", p_meta_tools_list)
probe("meta.gateway.dead_list call", p_meta_dead_list_call)
probe("cve initialize+tools/list via proxy (session affinity)", p_cve_initialize_and_list)
probe("cve read-only tool call via proxy", p_cve_tool_call)
probe("unknown route -> 404", p_unknown_route_404)
probe("remote-auth row -> 501 (structure-only)", p_remote_auth_501)
probe("latency: gateway hop vs direct", p_latency_vs_direct)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=1)
ok = sum(1 for p in results["probes"] if p["ok"])
print(f"\nBATTERY: {ok}/{len(results['probes'])} OK -> {OUT_PATH}")
sys.exit(0 if ok == len(results["probes"]) else 1)
