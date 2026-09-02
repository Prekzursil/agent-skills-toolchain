"""Detect security-adjacent capabilities from THIS worktree (computed, not recalled)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lib import REPO, load_json, rel, sha256_path

AUD_GRAPH = REPO / "command-center/p2-wave/probes/AUD-0030/probe1-ast-graph.json"
TAXONOMY = REPO / "command-center/p2-wave/probes/IMP-0184/coverage.py"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
MCP = REPO / "tools/mcp"
COMMIT_RE = re.compile(r"commit `([0-9a-f]{40})`")

LIVE_PIN_FILES: dict[str, tuple[str, ...]] = {
    "reverse-engineering-mcp-bundle": (
        "README.md",
        "manifests/ida-pro-mcp.json",
        "manifests/ghidra-mcp.json",
        "manifests/binary-ninja-mcp.json",
        "manifests/frida-mcp.json",
        "manifests/hexstrike-ai.json",
        "wrappers/hexstrike_mcp_launcher.py",
    ),
    "hexstrike-ai": (
        "README.md",
        "references/upstream-sources.md",
        "scripts/hexstrike_mcp_launcher.py",
    ),
    "hacktricks-mcp-server": (
        "README.md",
        "package.json",
        "package-lock.json",
        "references/provenance.json",
    ),
    "cheatengine-mcp-bridge": ("README.md",),
}


def _mcp_packages(graph: dict) -> set[str]:
    pkgs: set[str] = set()
    for key in graph.get("edges") or {}:
        parts = str(key).split(".")
        if len(parts) >= 3 and parts[0] == "tools" and parts[1] == "mcp":
            pkgs.add(parts[2])
    return pkgs


def _graph_modules(graph: dict, token: str) -> list[str]:
    hits = [str(k) for k in (graph.get("edges") or {}) if token in str(k)]
    return sorted(hits)


def _live_tool_dirs() -> list[str]:
    root = REPO / "tools"
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def _live_mcp_dirs() -> list[str]:
    if not MCP.is_dir():
        return []
    return sorted(p.name for p in MCP.iterdir() if p.is_dir())


def _file_meta(path: Path) -> dict[str, Any]:
    digest, nbytes = sha256_path(path)
    return {"bytes": nbytes, "path": rel(path), "sha256": digest}


def _lock_meta(path: Path) -> dict[str, Any]:
    doc = load_json(path)
    ver = str((doc.get("packages") or {}).get("", {}).get("version") or doc.get("version") or "")
    digest, nbytes = sha256_path(path)
    return {
        "bytes": nbytes,
        "name": doc.get("name"),
        "path": rel(path),
        "sha256": digest,
        "version": ver,
    }


def _package_record(name: str) -> dict[str, Any]:
    root = MCP / name
    files = []
    commit_pins: list[str] = []
    for rel_name in LIVE_PIN_FILES.get(name, ("README.md",)):
        path = root / rel_name
        if not path.is_file():
            continue
        files.append(_file_meta(path))
        if path.suffix.lower() in {".md", ".json"}:
            text = path.read_text(encoding="utf-8")
            commit_pins.extend(COMMIT_RE.findall(text))
            if path.name == "provenance.json":
                try:
                    doc = load_json(path)
                    up = str(doc.get("upstream_commit") or "")
                    if re.fullmatch(r"[0-9a-f]{40}", up):
                        commit_pins.append(up)
                except (OSError, ValueError, TypeError):
                    pass
    extra: dict[str, Any] = {}
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        doc = load_json(pkg_json)
        extra["package_name"] = doc.get("name")
        extra["package_version"] = doc.get("version")
    return {
        "commit_pins": sorted(set(commit_pins)),
        "files": files,
        "present": root.is_dir(),
        **extra,
    }


def _hacktricks_locks() -> list[Path]:
    seen: set[Path] = set()
    rows: list[Path] = []
    live = MCP / "hacktricks-mcp-server" / "package-lock.json"
    if live.is_file():
        rows.append(live)
        seen.add(live.resolve())
    for p in sorted(REPO.glob("command-center/p2-wave/probes/**/hacktricks-mcp-server/package-lock.json")):
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        rows.append(p)
    return rows


def detect() -> dict[str, Any]:
    graph = load_json(AUD_GRAPH) if AUD_GRAPH.is_file() else {"edges": {}}
    pkgs = _mcp_packages(graph)
    live = _live_tool_dirs()
    mcp_dirs = _live_mcp_dirs()
    lock_meta = [_lock_meta(p) for p in _hacktricks_locks()]
    versions = sorted({str(x.get("version") or "") for x in lock_meta if x.get("version")})
    catalog_sha, catalog_bytes = sha256_path(CATALOG)
    graph_sha, graph_bytes = sha256_path(AUD_GRAPH)
    tax_sha, tax_bytes = sha256_path(TAXONOMY)
    catalog_text = CATALOG.read_text(encoding="utf-8")
    live_packages = {name: _package_record(name) for name in LIVE_PIN_FILES}
    live_re = live_packages["reverse-engineering-mcp-bundle"]["present"]
    live_hx = live_packages["hexstrike-ai"]["present"]
    live_ht = live_packages["hacktricks-mcp-server"]["present"]
    live_ce = live_packages["cheatengine-mcp-bridge"]["present"]
    schema = REPO / "command-center/schema/research-claim-record.schema.json"
    schema_sha, schema_bytes = sha256_path(schema) if schema.is_file() else ("", 0)
    return {
        "aud_graph": {
            "bytes": graph_bytes,
            "has_hexstrike_ai": "hexstrike-ai" in pkgs,
            "has_reverse_engineering_bundle": "reverse-engineering-mcp-bundle" in pkgs,
            "hexstrike_modules": _graph_modules(graph, "hexstrike"),
            "mcp_packages": sorted(pkgs),
            "path": rel(AUD_GRAPH),
            "re_modules": _graph_modules(graph, "reverse-engineering-mcp-bundle"),
            "sha256": graph_sha,
        },
        "catalog": {
            "bytes": catalog_bytes,
            "mentions_bandit": "bandit" in catalog_text,
            "mentions_j15_dual_use": "J-15 dual-use disclosure review" in catalog_text,
            "mentions_osv_scanner": "osv-scanner" in catalog_text,
            "mentions_semgrep": "semgrep" in catalog_text,
            "path": rel(CATALOG),
            "sha256": catalog_sha,
        },
        "hacktricks": {
            "lockfiles": lock_meta,
            "present": bool(lock_meta) or live_ht,
            "versions": versions,
        },
        "live": {
            "tool_dirs": live,
            "tools_mcp_dirs": mcp_dirs,
            "tools_mcp_present": MCP.is_dir(),
        },
        "live_mcp": {
            "cheatengine_present": live_ce,
            "hacktricks_present": live_ht,
            "hexstrike_present": live_hx,
            "packages": live_packages,
            "re_bundle_present": live_re,
        },
        "schema": {
            "bytes": schema_bytes,
            "path": "command-center/schema/research-claim-record.schema.json",
            "present": schema.is_file(),
            "sha256": schema_sha,
        },
        "taxonomy": {
            "bytes": tax_bytes,
            "defines_security_scan": '        "security.scan",' in TAXONOMY.read_text(encoding="utf-8"),
            "path": rel(TAXONOMY),
            "sha256": tax_sha,
        },
    }
