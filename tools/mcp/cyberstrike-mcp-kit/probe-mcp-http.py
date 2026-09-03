#!/usr/bin/env python3
"""JSON-RPC initialize probe for loopback Streamable HTTP MCP fronts. No secrets."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

TARGETS = [
    ("sliver", "http://127.0.0.1:31380/mcp"),
    ("sliver-full", "http://127.0.0.1:31381/mcp"),
    ("github-security", "http://127.0.0.1:31410/mcp"),
    ("cve", "http://127.0.0.1:31411/mcp"),
    ("osint", "http://127.0.0.1:31412/mcp"),
    ("hexstrike-ai", "http://127.0.0.1:31413/mcp"),
    ("firecrawl", "http://127.0.0.1:31414/mcp"),
    ("hacktricks", "http://127.0.0.1:31415/mcp"),
    ("metasploit", "http://127.0.0.1:31416/mcp"),
    ("search-hub", "http://127.0.0.1:31420/mcp"),
    ("basic-memory", "http://127.0.0.1:8765/mcp"),
]

BODY = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "cs-http-probe", "version": "1.0"},
        },
    }
).encode("utf-8")


def probe(name: str, url: str) -> str:
    req = urllib.request.Request(
        url,
        data=BODY,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "replace")
            code = resp.status
            server = ""
            if "data:" in raw:
                for line in raw.splitlines():
                    if line.startswith("data:"):
                        raw = line[5:].strip()
                        break
            try:
                payload = json.loads(raw)
                result = payload.get("result") or {}
                info = result.get("serverInfo") or {}
                server = f"{info.get('name', '?')} {info.get('version', '')}".strip()
                err = payload.get("error")
                if err:
                    return f"{name} HTTP {code} RPC-ERR {err.get('code')} {err.get('message')}"
            except json.JSONDecodeError:
                return f"{name} HTTP {code} NON-JSON {raw[:80]!r}"
            return f"{name} HTTP {code} OK {server}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:120]
        return f"{name} HTTP {e.code} FAIL {body}"
    except Exception as e:
        return f"{name} ERR {type(e).__name__}: {e}"


def main() -> int:
    names = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    for name, url in TARGETS:
        if names and name not in names:
            continue
        print(probe(name, url), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
