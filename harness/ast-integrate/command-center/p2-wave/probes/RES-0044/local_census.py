#!/usr/bin/env python3
"""Local census: does THIS program ship an HTTP OAuth MCP consumer?"""
from __future__ import annotations

import json
import re
from pathlib import Path

NEEDLES = (
    "oauth-protected-resource",
    "Protected Resource Metadata",
    "code_challenge",
    "code_verifier",
    "authorization_servers",
    "StreamableHTTP",
    "streamable_http",
    "WWW-Authenticate",
)

SKIP_PARTS = {
    "node_modules",
    ".git",
    "captures",
    "__pycache__",
    "p2-wave/probes/RES-0044",
}

# Verdict only counts tools/ and IMP-0048; do not rglob the whole worktree.
SCAN_REL = (
    "tools",
    "command-center/p2-wave/probes/IMP-0048",
)
MCP_JSON_REL = (
    ".mcp.json",
    "mcp.json",
    "tools/.mcp.json",
    "command-center/.mcp.json",
)


def iter_files(root: Path):
    for rel_root in SCAN_REL:
        base = root / rel_root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if any(part in rel for part in SKIP_PARTS):
                continue
            if path.suffix.lower() not in {".py", ".ts", ".js", ".json", ".md"}:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            yield path, rel
    for rel in MCP_JSON_REL:
        path = root / rel
        if path.is_file():
            yield path, rel


def census(repo: Path) -> dict:
    hits = []
    mcp_json = []
    for path, rel in iter_files(repo):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.name in {".mcp.json", "mcp.json"} or rel.endswith("/.mcp.json"):
            try:
                doc = json.loads(text)
            except json.JSONDecodeError:
                doc = None
            servers = (doc or {}).get("mcpServers") if isinstance(doc, dict) else None
            mcp_json.append(
                {
                    "path": rel,
                    "parseable": isinstance(doc, dict),
                    "server_count": len(servers) if isinstance(servers, dict) else 0,
                    "stdio_commands": sorted(
                        {
                            (servers or {}).get(k, {}).get("command")
                            for k in (servers or {})
                            if isinstance((servers or {}).get(k), dict)
                            and (servers or {}).get(k, {}).get("command")
                        }
                    )
                    if isinstance(servers, dict)
                    else [],
                    "has_url_server": bool(
                        isinstance(servers, dict)
                        and any(
                            isinstance(v, dict) and ("url" in v or "serverUrl" in v)
                            for v in servers.values()
                        )
                    ),
                }
            )
        found = sorted({n for n in NEEDLES if n in text})
        # Ignore this unit's own research files and catalog text.
        if found and "RES-0044" not in rel and "WORK-UNIT-CATALOG" not in rel:
            if rel.startswith("tools/") or rel.startswith("command-center/p2-wave/probes/IMP-0048"):
                hits.append({"path": rel, "needles": found})
    tools_hits = [h for h in hits if h["path"].startswith("tools/")]
    return {
        "http_oauth_consumer_in_tools": len(tools_hits) > 0,
        "tool_hits": tools_hits[:40],
        "imp0048_hits": [h for h in hits if "IMP-0048" in h["path"]][:20],
        "mcp_json_files": mcp_json,
        "stdio_only_observed": all(not row.get("has_url_server") for row in mcp_json)
        if mcp_json
        else True,
        "verdict": (
            "THIS-WORKTREE-HAS-NO-HTTP-OAUTH-MCP-CLIENT"
            if not tools_hits
            else "HTTP-OAUTH-STRINGS-PRESENT-IN-TOOLS"
        ),
    }
