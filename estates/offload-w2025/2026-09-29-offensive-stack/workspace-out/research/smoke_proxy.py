"""Smoke test: start proxy via ProxyManager, push traffic, verify addon records to SQLite."""
import subprocess, sys, time

from nodriver_proxy_mcp.proxy.controller import proxy_manager

r = proxy_manager.start(port=8082)
print("start():", r)
if r.get("status") not in ("started", "already_running"):
    sys.exit(1)

# Drive HTTP and HTTPS traffic through mitmproxy
for url in ["http://example.com/", "https://example.com/"]:
    p = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-x", "http://127.0.0.1:8082", "-k", url],
        capture_output=True, text=True, timeout=30)
    print(f"curl {url} -> {p.stdout.strip()} (stderr: {p.stderr.strip()[:80]})")

time.sleep(1.5)  # let addon flush to SQLite

from nodriver_proxy_mcp.proxy.recorder import traffic_db
res = traffic_db.get_summary(limit=10)
flows = res.get("flows", res) if isinstance(res, dict) else res
print("recorded flows:", len(flows))
for f in flows[:5]:
    print("  ", f.get("method"), f.get("status_code"), f.get("url"))

print("stop():", proxy_manager.stop())
