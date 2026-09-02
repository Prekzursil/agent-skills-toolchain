#!/usr/bin/env python3
"""Declare the host-client set and probe this box (read-only)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

DECLARED_CLIENTS: list[dict[str, Any]] = [
    {
        "id": "claude-code",
        "label": "Claude Code",
        "binaries": ("claude", "claude-code"),
        "install_step": (
            "Install the Claude Code host client so `claude --version` or "
            "`claude-code --version` succeeds on PATH, then re-run the "
            "inside-client hook-fire and command-resolve probes against the "
            "shipped plugin (not the installer exit code)."
        ),
    },
    {
        "id": "codex-cli",
        "label": "Codex CLI",
        "binaries": ("codex",),
        "install_step": (
            "Install the OpenAI Codex CLI so `codex --version` succeeds on "
            "PATH, then re-run the inside-client hook-fire and command-resolve "
            "probes against the shipped plugin (not the installer exit code)."
        ),
    },
    {
        "id": "antigravity-agy",
        "label": "Antigravity/agy",
        "binaries": ("agy", "antigravity"),
        "install_step": (
            "Install the Antigravity/agy host client so `agy --version` or "
            "`antigravity --version` succeeds on PATH, then re-run the "
            "inside-client hook-fire and command-resolve probes against the "
            "shipped plugin (not the installer exit code)."
        ),
    },
]

CONFORMANCE_SUITE: list[dict[str, Any]] = [
    {
        "id": "plugin-install-smoke",
        "title": "Plugin installer exits 0",
        "inside_required": True,
        "note": (
            "An installer exit code is never sufficient for RUN. The named "
            "failure class is plugin-appears-installed-but-hooks-unloaded."
        ),
    },
    {
        "id": "hook-fires",
        "title": "A hook fires inside the client",
        "inside_required": True,
        "observation_kind": "hook_fired",
    },
    {
        "id": "command-resolves",
        "title": "A plugin command resolves inside the client",
        "inside_required": True,
        "observation_kind": "command_resolved",
    },
]

MATRIX_CANDIDATES = (
    "command-center/phase4/contracts/ARC-0095.json",
    "command-center/receipts/ARC-0095.json",
    "command-center/receipts/TST-0049.json",
    "command-center/phase4/compatibility-matrix.json",
)


def _version_from(binary: str) -> str:
    try:
        p = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    line = text.splitlines()[0].strip() if text else ""
    return line[:120]


def probe_client(spec: dict[str, Any]) -> dict[str, Any]:
    found = ""
    for name in spec["binaries"]:
        path = shutil.which(name)
        if path:
            found = path
            break
    if not found:
        row = {
            "id": spec["id"],
            "label": spec["label"],
            "client_present": False,
            "binary_path": None,
            "client_version": "",
            "install_step": spec["install_step"],
        }
        row["client_present"] = False
        row["binary_path"] = None
        row["install_step"] = spec["install_step"]
        return row
    version = _version_from(Path(found).name)
    if not version:
        version = _version_from(found)
    row = {
        "id": spec["id"],
        "label": spec["label"],
        "client_present": True,
        "binary_path": found,
        "client_version": version,
        "install_step": spec["install_step"],
    }
    row["client_present"] = True
    row["binary_path"] = found
    row["install_step"] = spec["install_step"]
    return row


def extra_mcp_hosts_from_matrix(
    repo: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    present: list[str] = []
    missing: list[str] = []
    named: list[dict[str, Any]] = []
    known = {c["id"] for c in DECLARED_CLIENTS}
    aliases = {
        "claude code": "claude-code",
        "claude-code": "claude-code",
        "codex cli": "codex-cli",
        "codex-cli": "codex-cli",
        "codex": "codex-cli",
        "antigravity": "antigravity-agy",
        "agy": "antigravity-agy",
        "antigravity/agy": "antigravity-agy",
    }
    for rel in MATRIX_CANDIDATES:
        path = repo / rel
        if not (path.is_file() and path.stat().st_size > 0):
            missing.append(rel)
            continue
        present.append(rel)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        hosts: list[Any] = []
        if isinstance(doc, dict):
            for key in ("clients", "host_clients", "mcp_hosts", "generic_mcp_hosts"):
                val = doc.get(key)
                if isinstance(val, list):
                    hosts.extend(val)
            axes = doc.get("axes") if isinstance(doc.get("axes"), dict) else {}
            for key in ("clients", "host_clients", "mcp_hosts"):
                val = axes.get(key)
                if isinstance(val, list):
                    hosts.extend(val)
        for item in hosts:
            if isinstance(item, str):
                ident, label = item.strip(), item.strip()
            elif isinstance(item, dict):
                ident = str(item.get("id") or item.get("name") or "").strip()
                label = str(item.get("label") or ident)
            else:
                continue
            if not ident:
                continue
            aliased = aliases.get(ident.lower(), ident)
            if aliased in known:
                continue
            named.append({"id": ident, "label": label, "source": rel})
            known.add(aliased)
    return named, {"present": present, "missing": missing}


def scan_inside_client_receipts(repo: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    roots = [
        repo / "command-center" / "receipts",
        repo / "command-center" / "phase4",
    ]
    needles = ("hook_fired", "command_resolved", "hook firing", "command resolving")
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            lower = text.lower()
            if not any(n.lower() in lower for n in needles):
                continue
            rel = path.relative_to(repo).as_posix()
            hits.append({"path": rel, "bytes": path.stat().st_size})
    return hits

extra_mcp_hosts_from_matrix = extra_mcp_hosts_from_matrix
DECLARED_CLIENTS = DECLARED_CLIENTS
scan_inside_client_receipts = scan_inside_client_receipts
