#!/usr/bin/env python3
"""Client-side recomputation of MCP-registry trust signals."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"

MCP_TXT_RE = re.compile(r"v=MCPv1;\s*k=(ed25519|ecdsap384);\s*p=([A-Za-z0-9+/=]+)")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def npm_mcpname(server_doc: dict, npm_doc: dict) -> dict:
    server = server_doc.get("server") if isinstance(server_doc.get("server"), dict) else server_doc
    name = str(server.get("name") or "")
    pkgs = [
        p
        for p in (server.get("packages") or [])
        if isinstance(p, dict) and p.get("registryType") == "npm"
    ]
    if not pkgs:
        return {
            "signal_id": "npm_mcpName_ownership",
            "computed": True,
            "match": False,
            "reason": "no-npm-package",
            "server_name": name,
        }
    pkg = pkgs[0]
    mcp = npm_doc.get("mcpName")
    ident = pkg.get("identifier")
    ver = pkg.get("version")
    match = mcp == name and npm_doc.get("name") == ident and str(npm_doc.get("version")) == str(ver)
    return {
        "signal_id": "npm_mcpName_ownership",
        "computed": True,
        "server_name": name,
        "npm_name": npm_doc.get("name"),
        "npm_version": npm_doc.get("version"),
        "npm_mcpName": mcp,
        "package_identifier": ident,
        "package_version": ver,
        "registry_base_url": pkg.get("registryBaseUrl"),
        "match": bool(match),
        "mcpName_equals_server_name": mcp == name,
        "identifier_equals_npm_name": npm_doc.get("name") == ident,
        "version_equals": str(npm_doc.get("version")) == str(ver),
        "method": (
            "Read server.json name from the official registry API response; "
            "GET the npm packument version document; compare mcpName == name "
            "and identifier/version against npm name/version."
        ),
    }


def parse_txt_records(text: str) -> list[str]:
    out: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        if s:
            out.append(s)
    return out


def dns_mcp_txt(records: list[str], domain: str, server_name: str) -> dict:
    mcp = [r for r in records if "v=MCPv1" in r]
    parsed = []
    for r in mcp:
        m = MCP_TXT_RE.search(r)
        if m:
            parsed.append({"k": m.group(1), "p": m.group(2), "raw": r})
    ns = str(server_name or "").split("/")[0]
    # reverse-DNS namespace com.pulsemcp -> pulsemcp.com
    expected_domain = ".".join(reversed(ns.split("."))) if ns else ""
    return {
        "signal_id": "dns_apex_mcp_txt",
        "computed": True,
        "domain": domain,
        "server_name": server_name,
        "namespace": ns,
        "expected_domain": expected_domain,
        "domain_matches_namespace": expected_domain == domain,
        "mcp_txt_present": bool(parsed),
        "parsed": parsed,
        "match": bool(parsed) and expected_domain == domain,
        "does_not_replay_login_signature": True,
        "method": (
            "Query apex TXT on the reverse-DNS domain of a domain-namespace "
            "server name. Accept only records matching v=MCPv1; k=ed25519|ecdsap384; p=... "
            "This recomputes key publication, not the original signed auth challenge."
        ),
    }


def github_namespace_repo_owner(server_doc: dict) -> dict:
    server = server_doc.get("server") if isinstance(server_doc.get("server"), dict) else server_doc
    name = str(server.get("name") or "")
    repo = server.get("repository") if isinstance(server.get("repository"), dict) else {}
    url = str(repo.get("url") or "")
    prefix = "io.github."
    if not name.startswith(prefix) or "/" not in name[len(prefix) :]:
        return {
            "signal_id": "github_namespace_repo_owner_consistency",
            "computed": True,
            "match": False,
            "reason": "not-io.github-namespace",
            "server_name": name,
        }
    owner = name[len(prefix) :].split("/", 1)[0].lower()
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    parts = [p for p in (parsed.path or "").split("/") if p]
    gh_owner = parts[0].lower() if parts else ""
    host_ok = host in {"github.com", "www.github.com"}
    match = host_ok and gh_owner == owner
    return {
        "signal_id": "github_namespace_repo_owner_consistency",
        "computed": True,
        "server_name": name,
        "namespace_owner": owner,
        "repository_url": url,
        "repository_host": host,
        "repository_owner": gh_owner,
        "match": match,
        "not_oauth_replay": True,
        "method": (
            "Parse io.github.<owner>/... from server name and compare <owner> "
            "to the GitHub repository.url owner. String consistency only; "
            "does not replay GitHub OAuth/OIDC."
        ),
    }


def allowlisted_npm_base(server_doc: dict) -> dict:
    server = server_doc.get("server") if isinstance(server_doc.get("server"), dict) else server_doc
    allowed = "https://registry.npmjs.org"
    pkgs = [
        p
        for p in (server.get("packages") or [])
        if isinstance(p, dict) and p.get("registryType") == "npm"
    ]
    if not pkgs:
        return {
            "signal_id": "npm_registry_base_url_allowlist",
            "computed": True,
            "match": False,
            "reason": "no-npm-package",
        }
    base = str(pkgs[0].get("registryBaseUrl") or "").rstrip("/")
    return {
        "signal_id": "npm_registry_base_url_allowlist",
        "computed": True,
        "registry_base_url": base,
        "allowed": allowed,
        "match": base == allowed,
        "method": (
            "Compare packages[].registryBaseUrl to the official allowlist "
            "value https://registry.npmjs.org (official-registry-requirements.md)."
        ),
    }


def live_dig_txt(domain: str, timeout: int = 20) -> dict:
    proc = subprocess.run(
        ["dig", "+short", "TXT", domain],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    records = parse_txt_records(proc.stdout or "")
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "records": records,
        "command": f"dig +short TXT {domain}",
    }


def from_captures() -> dict:
    server = load_json(CAP / "brave-server-detail.json")
    npm = load_json(CAP / "brave-npm-2.1.3.json")
    pulse = load_json(CAP / "pulsemcp-server-detail.json")
    dns_text = (CAP / "pulsemcp-dns-txt.txt").read_text(encoding="utf-8")
    return {
        "npm_mcpName_ownership": npm_mcpname(server, npm),
        "npm_registry_base_url_allowlist": allowlisted_npm_base(server),
        "github_namespace_repo_owner_consistency": github_namespace_repo_owner(server),
        "dns_apex_mcp_txt": dns_mcp_txt(
            parse_txt_records(dns_text),
            "pulsemcp.com",
            str((pulse.get("server") or {}).get("name") or ""),
        ),
    }
