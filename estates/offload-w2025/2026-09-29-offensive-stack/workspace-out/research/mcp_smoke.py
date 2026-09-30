"""Smoke-test the ArtBlood MCP stdio server: initialize -> tools/list -> graph_stats -> shortest_paths."""
import json, subprocess, sys, threading, time, os

exe = sys.argv[1]
cache = sys.argv[2]
proc = subprocess.Popen([exe, "mcp", "--cache", cache],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, encoding="utf-8")

responses = {}
def reader():
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = msg.get("id")
        if rid is not None:
            responses[rid] = msg

t = threading.Thread(target=reader, daemon=True)
t.start()

def send(obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()

def wait(rid, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if rid in responses:
            return responses[rid]
        time.sleep(0.1)
    raise TimeoutError(f"no response for id {rid}")

send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "smoke", "version": "0"}}})
init = wait(1)
print("INIT serverInfo:", json.dumps(init.get("result", {}).get("serverInfo", {})))
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
tools = wait(2)
names = [t["name"] for t in tools.get("result", {}).get("tools", [])]
print("TOOLS:", names)
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
    "name": "graph_stats", "arguments": {}}})
stats = wait(3)
print("GRAPH_STATS:", json.dumps(stats.get("result", {}))[:400])
send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
    "name": "shortest_paths", "arguments": {"from": "ALICE@CORP.LOCAL", "to": "CORP.LOCAL", "limit": 5}}})
paths = wait(4)
print("SHORTEST_PATHS:", json.dumps(paths.get("result", {}))[:600])
proc.stdin.close()
try:
    proc.wait(timeout=10)
except subprocess.TimeoutExpired:
    proc.kill()
err = proc.stderr.read()[:500]
if err:
    print("STDERR:", err)
print("MCP_SMOKE_OK tools=%d" % len(names))
