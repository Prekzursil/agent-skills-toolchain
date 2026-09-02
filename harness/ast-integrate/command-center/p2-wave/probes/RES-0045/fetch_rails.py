#!/usr/bin/env python3
"""Fetch dual-rail snapshots for RES-0045 (structured spec + prose).

Does not use api.github.com (rate-limited). Raw GitHub + official docs only.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots"
UA = "RES-0045-evidence-capture/1.0 (research dual-rail; local measure)"
CTX = ssl.create_default_context()

MCP_SHA = "57ac4a2ec742e0cb7622d899b0f5d3bcf769fd69"
A2A_SHA = "16ba52690519bf55b9388e34d4db356efa88aa51"

SOURCES = [
    {
        "id": "r1-mcp-schema",
        "kind": "structured-api",
        "protocol": "mcp",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/"
            f"modelcontextprotocol/{MCP_SHA}/schema/2026-07-28/schema.json"
        ),
        "file": "r1-mcp-schema-2026-07-28.json",
        "pinned_commit": MCP_SHA,
    },
    {
        "id": "r1-a2a-proto",
        "kind": "structured-api",
        "protocol": "a2a",
        "url": (
            "https://raw.githubusercontent.com/a2aproject/A2A/"
            f"{A2A_SHA}/specification/a2a.proto"
        ),
        "file": "r1-a2a.proto",
        "pinned_commit": A2A_SHA,
    },
    {
        "id": "r1-agntcy-openapi",
        "kind": "structured-api",
        "protocol": "agent-connect",
        "url": "https://raw.githubusercontent.com/agntcy/acp-spec/main/openapi.json",
        "file": "r1-agntcy-acp-openapi.json",
        "pinned_commit": None,
    },
    {
        "id": "r1-ibm-acp-openapi",
        "kind": "structured-api",
        "protocol": "agent-connect",
        "url": "https://raw.githubusercontent.com/i-am-bee/acp/main/docs/spec/openapi.yaml",
        "file": "r1-ibm-acp-openapi.yaml",
        "pinned_commit": None,
    },
    {
        "id": "r2-mcp-architecture",
        "kind": "prose-source",
        "protocol": "mcp",
        "url": "https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture.md",
        "file": "r2-mcp-architecture.md",
        "pinned_commit": None,
    },
    {
        "id": "r2-mcp-server-concepts",
        "kind": "prose-source",
        "protocol": "mcp",
        "url": "https://modelcontextprotocol.io/docs/2026-07-28/learn/server-concepts.md",
        "file": "r2-mcp-server-concepts.md",
        "pinned_commit": None,
    },
    {
        "id": "r2-mcp-client-concepts",
        "kind": "prose-source",
        "protocol": "mcp",
        "url": "https://modelcontextprotocol.io/docs/2026-07-28/learn/client-concepts.md",
        "file": "r2-mcp-client-concepts.md",
        "pinned_commit": None,
    },
    {
        "id": "r2-a2a-and-mcp",
        "kind": "prose-source",
        "protocol": "a2a",
        "url": (
            "https://raw.githubusercontent.com/a2aproject/A2A/"
            f"{A2A_SHA}/docs/topics/a2a-and-mcp.md"
        ),
        "file": "r2-a2a-and-mcp.md",
        "pinned_commit": A2A_SHA,
    },
    {
        "id": "r2-a2a-discovery",
        "kind": "prose-source",
        "protocol": "a2a",
        "url": (
            "https://raw.githubusercontent.com/a2aproject/A2A/"
            f"{A2A_SHA}/docs/topics/agent-discovery.md"
        ),
        "file": "r2-a2a-agent-discovery.md",
        "pinned_commit": A2A_SHA,
    },
    {
        "id": "r2-acp-mcp-a2a",
        "kind": "prose-source",
        "protocol": "agent-connect",
        "url": "https://agentcommunicationprotocol.dev/about/mcp-and-a2a.md",
        "file": "r2-acp-mcp-and-a2a.md",
        "pinned_commit": None,
    },
    {
        "id": "r2-acp-run-lifecycle",
        "kind": "prose-source",
        "protocol": "agent-connect",
        "url": "https://agentcommunicationprotocol.dev/core-concepts/agent-run-lifecycle.md",
        "file": "r2-acp-run-lifecycle.md",
        "pinned_commit": None,
    },
    {
        "id": "r2-agntcy-readme",
        "kind": "prose-source",
        "protocol": "agent-connect",
        "url": "https://raw.githubusercontent.com/agntcy/acp-spec/main/README.md",
        "file": "r2-agntcy-readme.md",
        "pinned_commit": None,
    },
]


def fetch(url: str) -> tuple[int, str, str, bytes]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*"},
    )
    with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
        body = resp.read()
        return (
            int(resp.status),
            str(resp.geturl()),
            str(resp.headers.get("Content-Type") or ""),
            body,
        )


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for src in SOURCES:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status, final, ctype, body = fetch(src["url"])
        if status != 200:
            raise SystemExit(f"FAILED:fetch {src['id']} http {status}")
        if len(body) < 200:
            raise SystemExit(f"FAILED:fetch {src['id']} too-small {len(body)}")
        path = SNAP / src["file"]
        path.write_bytes(body)
        sha = hashlib.sha256(body).hexdigest()
        row = {
            "id": src["id"],
            "kind": src["kind"],
            "protocol": src["protocol"],
            "permalink": src["url"],
            "requested_url": src["url"],
            "final_url": final,
            "fetch_timestamp": ts,
            "http_status": status,
            "content_type": ctype,
            "sha256": sha,
            "captured_bytes": len(body),
            "snapshot": f"command-center/p2-wave/probes/RES-0045/snapshots/{src['file']}",
            "pinned_commit": src["pinned_commit"],
        }
        rows.append(row)
        print(f"OK {src['id']} {status} bytes={len(body)} sha256={sha[:12]}")
        time.sleep(0.15)
    index = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user_agent": UA,
        "rails": rows,
    }
    (SNAP / "CAPTURE.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SUCCESS:RES-0045-fetch {len(rows)} rails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
