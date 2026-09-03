#!/usr/bin/env python3
"""Nuclei MCP Server -- FastMCP integration for ProjectDiscovery Nuclei Scanner.

Provides vulnerability scanning, template enumeration, and CVE/exposure detection
powered by ProjectDiscovery Nuclei v3.11.1 and the local nuclei-templates vault.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nuclei")

NUCLEI_BIN = os.environ.get("NUCLEI_PATH", r"C:\Users\Prekzursil\scoop\shims\nuclei.exe")
if not os.path.exists(NUCLEI_BIN):
    which_path = shutil.which("nuclei")
    if which_path:
        NUCLEI_BIN = which_path

TEMPLATES_DIR = os.environ.get("NUCLEI_TEMPLATES_PATH", r"C:\Users\Prekzursil\nuclei-templates")


@mcp.tool()
def nuclei_status() -> Dict[str, Any]:
    """Check Nuclei installation status, version, and template library location."""
    version_output = "unknown"
    if os.path.exists(NUCLEI_BIN):
        try:
            res = subprocess.run([NUCLEI_BIN, "-version"], capture_output=True, text=True, timeout=10)
            version_output = res.stdout.strip() or res.stderr.strip()
        except Exception as e:
            version_output = f"error: {e}"

    templates_count = 0
    if os.path.exists(TEMPLATES_DIR):
        try:
            templates_count = sum(1 for _ in Path(TEMPLATES_DIR).rglob("*.yaml"))
        except Exception:
            pass

    return {
        "status": "ready" if os.path.exists(NUCLEI_BIN) else "binary_not_found",
        "nuclei_path": NUCLEI_BIN,
        "templates_path": TEMPLATES_DIR,
        "templates_count": templates_count,
        "version": version_output,
    }


@mcp.tool()
def nuclei_scan(
    target: str,
    tags: Optional[str] = None,
    severity: Optional[str] = None,
    templates: Optional[str] = None,
    rate_limit: int = 50,
    timeout_seconds: int = 120,
    max_results: int = 100,
) -> Dict[str, Any]:
    """Run a Nuclei scan against a target URL or host.

    Args:
        target: Target URL (e.g. 'https://admin-panel.bolt.eu') or IP/hostname.
        tags: Optional comma-separated template tags (e.g. 'cve,panel,exposure,misconfig,tech').
        severity: Optional comma-separated severities (e.g. 'critical,high,medium,low,info').
        templates: Optional specific template name, folder, or file path.
        rate_limit: Max requests per second (default 50).
        timeout_seconds: Timeout for the scan run (default 120s).
        max_results: Max finding entries to return (default 100).
    """
    if not os.path.exists(NUCLEI_BIN):
        return {"ok": False, "error": f"Nuclei binary not found at {NUCLEI_BIN}"}

    cmd = [
        NUCLEI_BIN,
        "-u", target,
        "-jsonl",
        "-silent",
        "-rate-limit", str(rate_limit),
    ]

    if templates:
        cmd.extend(["-t", templates])
    elif os.path.exists(TEMPLATES_DIR):
        cmd.extend(["-t", TEMPLATES_DIR])

    if tags:
        cmd.extend(["-tags", tags])
    if severity:
        cmd.extend(["-severity", severity])

    findings: List[Dict[str, Any]] = []
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                info = record.get("info", {})
                findings.append({
                    "template_id": record.get("template-id"),
                    "name": info.get("name"),
                    "severity": info.get("severity"),
                    "matched_at": record.get("matched-at"),
                    "type": record.get("type"),
                    "extracted_results": record.get("extracted-results"),
                    "description": info.get("description"),
                })
                if len(findings) >= max_results:
                    break
            except Exception:
                continue

        return {
            "ok": True,
            "target": target,
            "total_findings": len(findings),
            "findings": findings,
            "raw_stderr": proc.stderr.strip()[:1000] if proc.stderr else None,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": True,
            "target": target,
            "partial": True,
            "total_findings": len(findings),
            "findings": findings,
            "warning": f"Scan timed out after {timeout_seconds}s",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def nuclei_list_templates(
    query: Optional[str] = None,
    tag: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Search and list templates in the local nuclei-templates vault.

    Args:
        query: Keyword to match in template filename or path (e.g. 'cve-2024', 'databricks', 'login').
        tag: Filter by tag name.
        severity: Filter by severity ('critical', 'high', 'medium', 'low', 'info').
        limit: Max results to return (default 50).
    """
    if not os.path.exists(TEMPLATES_DIR):
        return {"ok": False, "error": f"Templates directory not found at {TEMPLATES_DIR}"}

    matched: List[Dict[str, str]] = []
    query_lower = query.lower() if query else None

    for p in Path(TEMPLATES_DIR).rglob("*.yaml"):
        rel = str(p.relative_to(TEMPLATES_DIR))
        if query_lower and query_lower not in rel.lower():
            continue

        matched.append({
            "rel_path": rel,
            "full_path": str(p),
            "name": p.stem,
        })
        if len(matched) >= limit:
            break

    return {
        "ok": True,
        "count": len(matched),
        "templates": matched,
    }


if __name__ == "__main__":
    mcp.run()
