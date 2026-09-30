#!/usr/bin/env python3
"""deep_front_probe.py <port> - deep probe: TCP connect + MCP initialize handshake."""
import json
import sys
import urllib.request



class _PostRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return urllib.request.Request(newurl, data=req.data, headers=req.headers,
                                      method=req.get_method())


def probe(port: int) -> int:
    url = f"http://127.0.0.1:{port}/mcp"
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "deep_front_probe", "version": "1.0"},
        },
    }).encode()
    opener = urllib.request.build_opener(_PostRedirectHandler())
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
    )
    try:
        with opener.open(req, timeout=10) as resp:
            payload = resp.read().decode(errors="replace")
            ok = resp.status == 200
            print(f"port {port}: HTTP {resp.status} {'OK' if ok else 'FAIL'}")
            print(payload[:600])
            return 0 if ok else 2
    except Exception as exc:  # noqa: BLE001
        print(f"port {port}: FAIL {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(probe(int(sys.argv[1])))
