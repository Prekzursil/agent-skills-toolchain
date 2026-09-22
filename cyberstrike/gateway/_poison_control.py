"""Poison both-states control (design §9.2, rule 3b): mutate ONE baseline hash in a
TEMP baselines copy, mount a gateway instance on 31151 against it, and prove the
poison path FIRES (503 + audit line). Real artifacts untouched. Also measures RSS
while alive (acceptance gate gw RSS < 100 MB)."""
import asyncio
import json
import socket
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\Prekzursil\.config\cyberstrike\gateway")
import skeleton  # noqa: E402
from gen_routes import BASELINES_OUT, OUT as ROUTES_OUT  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="gw-poison-control-"))
bl = json.loads(BASELINES_OUT.read_text(encoding="utf-8"))
assert bl.get("cve", {}).get("alive") and bl["cve"].get("desc_sha8"), "cve baseline missing"
bl["cve"]["desc_sha8"] = "deadbeef"  # the mutation
tmp_bl = tmp / "baselines.json"
tmp_bl.write_text(json.dumps(bl), encoding="utf-8")
skeleton.BASELINES_OUT = tmp_bl  # monkeypatch: Gateway reads this module global

routes = json.loads(ROUTES_OUT.read_text(encoding="utf-8"))
routes["gateway"]["listen"] = "127.0.0.1:31151"
routes["gateway"]["fallback_ports"] = [31152]


async def main() -> int:
    gw = skeleton.Gateway(routes, idle_exit_s=600)
    await gw.do_mount()
    cve_mount = gw.mount.get("cve", {})
    print("mount cve:", cve_mount.get("status"), "drift=", cve_mount.get("drift"))
    rss_mb = None
    try:
        # WorkingSet via ctypes for the CURRENT process (the gateway runs in-proc)
        import ctypes
        import ctypes.wintypes as wt
        class PMC(ctypes.Structure):
            # full PROCESS_MEMORY_COUNTERS layout — a truncated struct fails the
            # call silently and reports 0.0 MB (measured)
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        rss_mb = round(pmc.WorkingSetSize / (1024 * 1024), 1)
        print(f"RSS (in-proc gateway incl. driver): {rss_mb} MB")
    except Exception as e:
        print("rss-probe-failed", e)
    server = await asyncio.start_server(gw.on_client, "127.0.0.1", 31151)

    def client_probe() -> str:
        # blocking client MUST run off-loop or the server task never gets scheduled
        s = socket.create_connection(("127.0.0.1", 31151), timeout=15)
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                      "clientInfo": {"name": "poison-control", "version": "1"}}}).encode()
        req = (b"POST /mcp/cve HTTP/1.1\r\nHost: gw\r\nContent-Type: application/json\r\n"
               b"Accept: application/json\r\nConnection: close\r\n"
               + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        s.sendall(req)
        resp = s.recv(65536).decode("utf-8", "replace")
        s.close()
        return resp

    resp = await asyncio.to_thread(client_probe)
    server.close()
    status = resp.split(" ", 2)[1] if " " in resp else "?"
    fired = status == "503" and "drift" in resp
    print(f"poison path: HTTP {status}, fired={fired}")
    print("resp head:", resp.split("\r\n\r\n", 1)[-1][:160])
    # audit tail must contain the poison FAILED line for cve
    tail = gw.audit.path.read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(tail)
    print("audit tail:", row.get("server"), row.get("status"),
          row.get("flags"), (row.get("reason") or "")[:60])
    audit_ok = row.get("server") == "cve" and "poison" in (row.get("flags") or [])
    ok = (cve_mount.get("status") == "poisoned") and fired and audit_ok
    print("CONTROL:", "FIRED-AS-EXPECTED" if ok else "DID-NOT-FIRE (detector broken)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
