#!/usr/bin/env python3
"""Capture live official-MCP-registry evidence (HTTP + DNS). Re-runnable."""
from __future__ import annotations

import hashlib
import json
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
UA = "RES-0038-ast-integrate-research/1.0 (honest-capture)"
CTX = ssl.create_default_context()

URLS = [
    {
        "id": "registry-ping",
        "url": "https://registry.modelcontextprotocol.io/v0.1/ping",
        "rail": "structured-api",
        "filename": "registry-ping.json",
    },
    {
        "id": "registry-version",
        "url": "https://registry.modelcontextprotocol.io/v0.1/version",
        "rail": "structured-api",
        "filename": "registry-version.json",
    },
    {
        "id": "openapi",
        "url": "https://registry.modelcontextprotocol.io/openapi.yaml",
        "rail": "structured-api",
        "filename": "openapi.yaml",
    },
    {
        "id": "server-schema",
        "url": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "rail": "structured-api",
        "filename": "server.schema.json",
    },
    {
        "id": "brave-server-detail",
        "url": (
            "https://registry.modelcontextprotocol.io/v0.1/servers/"
            + urllib.parse.quote("io.github.brave/brave-search-mcp-server", safe="")
            + "/versions/latest"
        ),
        "rail": "structured-api",
        "filename": "brave-server-detail.json",
    },
    {
        "id": "brave-npm",
        "url": "https://registry.npmjs.org/@brave/brave-search-mcp-server/2.1.3",
        "rail": "structured-api",
        "filename": "brave-npm-2.1.3.json",
    },
    {
        "id": "pulsemcp-server-detail",
        "url": (
            "https://registry.modelcontextprotocol.io/v0.1/servers/"
            + urllib.parse.quote("com.pulsemcp/remote-filesystem", safe="")
            + "/versions/latest"
        ),
        "rail": "structured-api",
        "filename": "pulsemcp-server-detail.json",
    },
    {
        "id": "official-registry-requirements",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/registry/"
            "main/docs/reference/server-json/official-registry-requirements.md"
        ),
        "rail": "prose-source",
        "filename": "official-registry-requirements.md",
        "permalink": (
            "https://github.com/modelcontextprotocol/registry/blob/main/"
            "docs/reference/server-json/official-registry-requirements.md"
        ),
    },
    {
        "id": "official-registry-api",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/registry/"
            "main/docs/reference/api/official-registry-api.md"
        ),
        "rail": "prose-source",
        "filename": "official-registry-api.md",
        "permalink": (
            "https://github.com/modelcontextprotocol/registry/blob/main/"
            "docs/reference/api/official-registry-api.md"
        ),
    },
    {
        "id": "generic-server-json",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/registry/"
            "main/docs/reference/server-json/generic-server-json.md"
        ),
        "rail": "prose-source",
        "filename": "generic-server-json.md",
        "permalink": (
            "https://github.com/modelcontextprotocol/registry/blob/main/"
            "docs/reference/server-json/generic-server-json.md"
        ),
    },
    {
        "id": "package-types",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/registry/"
            "main/docs/modelcontextprotocol-io/package-types.mdx"
        ),
        "rail": "prose-source",
        "filename": "package-types.mdx",
        "permalink": (
            "https://github.com/modelcontextprotocol/registry/blob/main/"
            "docs/modelcontextprotocol-io/package-types.mdx"
        ),
    },
    {
        "id": "quickstart",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/registry/"
            "main/docs/modelcontextprotocol-io/quickstart.mdx"
        ),
        "rail": "prose-source",
        "filename": "quickstart.mdx",
        "permalink": (
            "https://github.com/modelcontextprotocol/registry/blob/main/"
            "docs/modelcontextprotocol-io/quickstart.mdx"
        ),
    },
    {
        "id": "authentication",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/registry/"
            "main/docs/modelcontextprotocol-io/authentication.mdx"
        ),
        "rail": "prose-source",
        "filename": "authentication.mdx",
        "permalink": (
            "https://github.com/modelcontextprotocol/registry/blob/main/"
            "docs/modelcontextprotocol-io/authentication.mdx"
        ),
    },
    {
        "id": "cli-commands",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/registry/"
            "main/docs/reference/cli/commands.md"
        ),
        "rail": "prose-source",
        "filename": "cli-commands.md",
        "permalink": (
            "https://github.com/modelcontextprotocol/registry/blob/main/"
            "docs/reference/cli/commands.md"
        ),
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch(url: str, timeout: int = 45) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    ts = utc_now()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            body = resp.read()
            return {
                "ok": True,
                "url": url,
                "final_url": resp.geturl(),
                "http_status": int(resp.status),
                "content_type": resp.headers.get("Content-Type"),
                "fetched_at": ts,
                "bytes": len(body),
                "sha256": sha256_bytes(body),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http_status": int(exc.code),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "fetched_at": ts,
            "bytes": len(body),
            "sha256": sha256_bytes(body) if body else None,
            "error": str(exc),
            "body": body,
        }
    except Exception as exc:  # noqa: BLE001 — capture rail must record the miss
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http_status": None,
            "fetched_at": ts,
            "error": f"{type(exc).__name__}: {exc}",
            "body": b"",
        }


def capture_dns(domain: str) -> dict:
    ts = utc_now()
    proc = subprocess.run(
        ["dig", "+short", "TXT", domain],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    raw = (proc.stdout or "").encode("utf-8")
    recs = []
    for line in (proc.stdout or "").splitlines():
        recs.append(line.strip().strip('"'))
    return {
        "ok": proc.returncode == 0,
        "tool": "dig +short TXT",
        "domain": domain,
        "command": f"dig +short TXT {domain}",
        "fetched_at": ts,
        "exit_code": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "records": recs,
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "mcp_txt": [r for r in recs if "v=MCPv1" in r],
    }


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    rows = []
    failed = []
    for spec in URLS:
        got = fetch(spec["url"])
        dest = CAP / spec["filename"]
        dest.write_bytes(got.get("body") or b"")
        row = {
            "id": spec["id"],
            "rail": spec["rail"],
            "url": spec["url"],
            "permalink": spec.get("permalink") or spec["url"],
            "final_url": got.get("final_url"),
            "http_status": got.get("http_status"),
            "content_type": got.get("content_type"),
            "fetched_at": got.get("fetched_at"),
            "bytes": dest.stat().st_size,
            "sha256": sha256_bytes(dest.read_bytes()),
            "path": f"command-center/p2-wave/probes/RES-0038/captures/{spec['filename']}",
            "ok": bool(got.get("ok")),
        }
        if got.get("error"):
            row["error"] = got["error"]
            failed.append(spec["id"])
        rows.append(row)
        print(f"http {row['http_status']} {spec['id']} sha256={row['sha256'][:12]}...")

    dns = capture_dns("pulsemcp.com")
    dns_path = CAP / "pulsemcp-dns-txt.txt"
    dns_path.write_text(dns["stdout"], encoding="utf-8")
    dns_row = {
        "id": "pulsemcp-dns-txt",
        "rail": "structured-api",
        "url": "dns:pulsemcp.com TXT",
        "permalink": "dns:pulsemcp.com TXT (dig +short)",
        "final_url": "dns:pulsemcp.com",
        "http_status": None,
        "dns_exit_code": dns["exit_code"],
        "fetched_at": dns["fetched_at"],
        "bytes": dns_path.stat().st_size,
        "sha256": sha256_bytes(dns_path.read_bytes()),
        "path": "command-center/p2-wave/probes/RES-0038/captures/pulsemcp-dns-txt.txt",
        "ok": dns["ok"] and bool(dns["mcp_txt"]),
        "mcp_txt": dns["mcp_txt"],
        "command": dns["command"],
    }
    rows.append(dns_row)
    print(f"dns  mcp_txt={dns['mcp_txt']} sha256={dns_row['sha256'][:12]}...")

    index = {
        "unit_id": "RES-0038",
        "captured_at": utc_now(),
        "captures": rows,
        "failed_ids": failed,
    }
    (CAP / "capture_index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    if failed:
        print(f"FAILED:RES-0038-capture missing={failed}")
        return 1
    if not dns_row["ok"]:
        print("FAILED:RES-0038-capture pulsemcp DNS TXT v=MCPv1 absent")
        return 1
    print("SUCCESS:RES-0038-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
