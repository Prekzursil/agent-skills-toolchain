#!/usr/bin/env python3
"""Fetch two-rail evidence for RES-0046. No tokens printed."""
from __future__ import annotations

import hashlib
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "captures" / "raw"
INDEX = HERE / "captures" / "index.json"
UA = "ast-integrate-RES-0046-research/1.0 (+local-worktree; no-auth)"

RAILS = [
    {
        "id": "gh-api-docker-mcp-gateway",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/docker/mcp-gateway",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "gh-api-ibm-mcp-context-forge",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/IBM/mcp-context-forge",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "gh-api-sparfenyuk-mcp-proxy",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/sparfenyuk/mcp-proxy",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "gh-api-supercorp-supergateway",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/supercorp-ai/supergateway",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "gh-api-mcp-spec-repo",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "gh-search-mcp-gateway-repos",
        "kind": "structured-api",
        "permalink": (
            "https://api.github.com/search/repositories"
            "?q=mcp+gateway+in:name&sort=stars&order=desc&per_page=10"
        ),
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prose-docker-mcp-gateway-readme",
        "kind": "prose-source",
        "permalink": "https://raw.githubusercontent.com/docker/mcp-gateway/main/README.md",
        "accept": "text/plain",
    },
    {
        "id": "prose-docker-mcp-gateway-docs",
        "kind": "prose-source",
        "permalink": "https://docs.docker.com/ai/mcp-catalog-and-toolkit/mcp-gateway/",
        "accept": "text/html",
    },
    {
        "id": "prose-ibm-contextforge-readme",
        "kind": "prose-source",
        "permalink": "https://raw.githubusercontent.com/IBM/mcp-context-forge/main/README.md",
        "accept": "text/plain",
    },
    {
        "id": "prose-ibm-contextforge-architecture",
        "kind": "prose-source",
        "permalink": "https://ibm.github.io/mcp-context-forge/latest/architecture/",
        "accept": "text/html",
    },
    {
        "id": "prose-ibm-contextforge-scale",
        "kind": "prose-source",
        "permalink": "https://ibm.github.io/mcp-context-forge/latest/manage/scale/",
        "accept": "text/html",
    },
    {
        "id": "prose-ibm-pr-4074",
        "kind": "prose-source",
        "permalink": "https://github.com/IBM/mcp-context-forge/pull/4074",
        "accept": "text/html",
    },
    {
        "id": "prose-sparfenyuk-mcp-proxy-readme",
        "kind": "prose-source",
        "permalink": "https://raw.githubusercontent.com/sparfenyuk/mcp-proxy/main/README.md",
        "accept": "text/plain",
    },
    {
        "id": "prose-supergateway-readme",
        "kind": "prose-source",
        "permalink": "https://raw.githubusercontent.com/supercorp-ai/supergateway/main/README.md",
        "accept": "text/plain",
    },
    {
        "id": "prose-anthropic-advanced-tool-use",
        "kind": "prose-source",
        "permalink": "https://www.anthropic.com/engineering/advanced-tool-use",
        "accept": "text/html",
    },
    {
        "id": "prose-anthropic-tool-search-docs",
        "kind": "prose-source",
        "permalink": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool",
        "accept": "text/html",
    },
    {
        "id": "prose-mcp-spec-tools-2025-11-25",
        "kind": "prose-source",
        "permalink": "https://modelcontextprotocol.io/specification/2025-11-25/server/tools",
        "accept": "text/html",
    },
    {
        "id": "prose-mcp-client-best-practices",
        "kind": "prose-source",
        "permalink": "https://modelcontextprotocol.io/docs/develop/clients/client-best-practices",
        "accept": "text/html",
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch(url: str, accept: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
            body = resp.read()
            final = str(resp.geturl())
            return int(resp.status), body, final
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, url


def ext_for(kind: str, permalink: str) -> str:
    if "api.github.com" in permalink:
        return ".json"
    if permalink.endswith(".md"):
        return ".md"
    if kind == "structured-api":
        return ".json"
    return ".html"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    failures = []
    for spec in RAILS:
        status, body, final = fetch(spec["permalink"], spec["accept"])
        rel = f"captures/raw/{spec['id']}{ext_for(spec['kind'], spec['permalink'])}"
        path = HERE / rel
        path.write_bytes(body)
        digest = sha256_bytes(body)
        row = {
            "id": spec["id"],
            "kind": spec["kind"],
            "permalink": spec["permalink"],
            "final_url": final,
            "http_status": status,
            "fetch_timestamp": ts,
            "sha256": digest,
            "bytes": len(body.replace(b"\r\n", b"\n")),
            "path": f"command-center/p2-wave/probes/RES-0046/{rel}",
        }
        rows.append(row)
        mark = "OK" if status == 200 and body else "FAIL"
        print(f"{mark} {status} {spec['id']} sha256={digest[:12]} bytes={len(body)}")
        if status != 200 or not body:
            failures.append(spec["id"])
    INDEX.write_text(
        json.dumps(
            {
                "unit_id": "RES-0046",
                "fetched_at": ts,
                "user_agent": UA,
                "auth": "none",
                "rails": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print(f"FAILED:capture {failures}")
        return 1
    print(f"SUCCESS:RES-0046-capture n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
