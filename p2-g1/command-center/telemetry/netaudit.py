"""AST audit: the telemetry package must import no network modules (IMP-0479)."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

NETWORK_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "urllib2",
        "urllib3",
        "requests",
        "httpx",
        "aiohttp",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "xmlrpc",
        "websocket",
        "websockets",
        "socketserver",
        "asyncio",
    }
)


def _module_hits(tree: ast.AST) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in NETWORK_MODULES:
                    hits.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top in NETWORK_MODULES:
                hits.append(node.module or "")
    return hits


def audit_no_network(package_dir: Path | str) -> dict[str, Any]:
    root = Path(package_dir)
    hits: list[dict[str, Any]] = []
    scanned: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned.append(path.name)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for mod in _module_hits(tree):
            hits.append({"file": path.name, "module": mod})
    return {
        "pass": not hits,
        "hits": hits,
        "scanned": scanned,
        "n_scanned": len(scanned),
    }


__all__ = ["NETWORK_MODULES", "audit_no_network"]
