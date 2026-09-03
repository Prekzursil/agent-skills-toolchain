#!/usr/bin/env python3
"""Switch CyberStrike remaining stdio MCPs to loopback HTTP. No secrets."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

SRC = Path(r"C:\Users\Prekzursil\.config\cyberstrike\cyberstrike.json")
BAK = Path(r"C:\Users\Prekzursil\.config\cyberstrike\cyberstrike.json.bak-2026-09-03-http-mcp")

REMOTE = {
    "github-security": 31410,
    "cve": 31411,
    "osint": 31412,
    "hexstrike-ai": 31413,
    "firecrawl": 31414,
    "hacktricks": 31415,
    "metasploit": 31416,
}
KEEP_REMOTE = {
    "sliver": "http://127.0.0.1:31380/mcp",
    "sliver-full": "http://127.0.0.1:31381/mcp",
    "basic-memory": "http://127.0.0.1:8765/mcp",
}


def main() -> int:
    if not BAK.exists():
        shutil.copy2(SRC, BAK)
    cfg = json.loads(SRC.read_text(encoding="utf-8"))
    mcp = cfg.setdefault("mcp", {})
    mcp.pop("search-hub", None)
    for name, port in REMOTE.items():
        mcp[name] = {
            "type": "remote",
            "url": f"http://127.0.0.1:{port}/mcp",
            "enabled": True,
            "timeout": 300000,
        }
    for name, url in KEEP_REMOTE.items():
        mcp[name] = {
            "type": "remote",
            "url": url,
            "enabled": True,
            "timeout": 300000,
        }
    cfg["bolt"] = {
        "bolt-lab": {
            "url": "http://127.0.0.1:3001",
            "enabled": True,
            "timeout": 900000,
        }
    }
    SRC.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    names = sorted(mcp)
    types = {k: mcp[k]["type"] for k in names}
    print("mcp", types)
    print("bolt", list(cfg["bolt"]))
    print("search-hub-in-cs", "search-hub" in mcp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
