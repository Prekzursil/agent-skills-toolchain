"""Minimal stdio MCP wrapper around the local Nuclei CLI.

Replaces the lost tools/mcp/nuclei-mcp/server.py front (cyberstrike Heavy/Core profile).
Serves loopback-only via the shared mcp-proxy front on 127.0.0.1:31417.
Tools: scan (full/targeted), template search, update, tech-detect passthrough.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nuclei")

NUCLEI = shutil.which("nuclei") or str(Path.home() / r".local\bin\nuclei.exe")
MAX_OUTPUT = 120_000  # chars returned to the model
SCAN_TIMEOUT = 900  # seconds


def _run(args: list[str], timeout: int = SCAN_TIMEOUT) -> tuple[int, str]:
    try:
        p = subprocess.run(
            [NUCLEI, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out[:MAX_OUTPUT]
    except subprocess.TimeoutExpired:
        return 124, f"nuclei timed out after {timeout}s"
    except FileNotFoundError:
        return 127, f"nuclei binary not found at {NUCLEI}"


@mcp.tool()
def nuclei_scan(
    target: str,
    templates: str = "",
    severity: str = "",
    tags: str = "",
    extra_args: str = "",
    timeout: int = SCAN_TIMEOUT,
) -> str:
    """Run a nuclei scan against a target (authorized engagement targets only).

    Args:
        target: URL / host / CIDR to scan.
        templates: comma-separated template paths or IDs (empty = all if no other filter).
        severity: comma-separated severities (info,low,medium,high,critical).
        tags: comma-separated tags filter.
        extra_args: raw extra nuclei CLI args (appended verbatim; operator responsibility).
        timeout: scan timeout seconds.
    """
    args = ["-target", target, "-jsonl", "-silent"]
    if templates:
        args += ["-t", templates]
    if severity:
        args += ["-severity", severity]
    if tags:
        args += ["-tags", tags]
    if extra_args:
        args += extra_args.split()
    rc, out = _run(args, timeout=timeout)
    findings = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            j = json.loads(line)
            findings.append(
                {
                    "template": j.get("template-id"),
                    "name": j.get("info", {}).get("name"),
                    "severity": j.get("info", {}).get("severity"),
                    "host": j.get("host"),
                    "matched": j.get("matched-at"),
                    "type": j.get("type"),
                    "curl": j.get("curl-command"),
                    "extracted": j.get("extracted-results"),
                }
            )
        except json.JSONDecodeError:
            continue
    return json.dumps({"returncode": rc, "findings": findings}, indent=1)


@mcp.tool()
def nuclei_raw(args: str, timeout: int = 600) -> str:
    """Run nuclei with raw CLI arguments (operator-controlled). E.g. '-l urls.txt -severity critical'."""
    rc, out = _run(args.split(), timeout=timeout)
    return out


@mcp.tool()
def nuclei_templates_search(query: str) -> str:
    """List installed nuclei templates matching a regex query (id, name, severity, tags)."""
    base = Path.home() / r"AppData\Roaming\nuclei\templates"
    if not base.is_dir():
        return "templates directory not found — run nuclei_templates_update first"
    rx = re.compile(query, re.I)
    hits = []
    for yml in base.rglob("*.yaml"):
        try:
            text = yml.read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            continue
        m_id = re.search(r"^id:\s*(\S+)", text, re.M)
        m_sev = re.search(r"severity:\s*(\w+)", text)
        if m_id and (rx.search(m_id.group(1)) or rx.search(text[:1500])):
            hits.append(
                {
                    "id": m_id.group(1),
                    "severity": m_sev.group(1) if m_sev else "?",
                    "path": str(yml.relative_to(base)),
                }
            )
        if len(hits) >= 200:
            break
    return json.dumps({"count": len(hits), "templates": hits}, indent=1)


@mcp.tool()
def nuclei_templates_update() -> str:
    """Update the nuclei template library."""
    rc, out = _run(["-update-templates"], timeout=600)
    return out[-4000:]


if __name__ == "__main__":
    mcp.run()
