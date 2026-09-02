"""Live-tree writer and credential-source inventory for BLD-0051.

Reports names, presence and byte length only. Never reads credential file
bodies or prints environment values.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402

_WRITER_SPECS = [
    {
        "id": "W-receipt-bld0051",
        "class": "receipt-emitter",
        "path": "command-center/p2-wave/probes/BLD-0051/emit_map.py",
        "anchor": "secret_redact.safe_write",
        "redaction": "ARMED",
        "notes": "This unit's shipped receipt writer; redactor is ON.",
    },
    {
        "id": "W-receipt-arc-emit",
        "class": "receipt-emitter",
        "path": "command-center/p2-wave/probes/ARC-0016/emit_refutation.py",
        "anchor": "out.write_text(json.dumps(...))",
        "redaction": "LACKING",
        "notes": "JSON dump with no redact call.",
    },
    {
        "id": "W-event-ledger-close",
        "class": "event-ledger",
        "path": "tools/command-center/close.py",
        "anchor": "close.py:85 append_event",
        "redaction": "LACKING",
        "notes": "json.dumps(payload) appended to EVENTS.jsonl with no redact.",
    },
    {
        "id": "W-event-ledger-catalog",
        "class": "event-ledger",
        "path": "tools/command-center/catalog.py",
        "anchor": "catalog.py:126 save write_text",
        "redaction": "LACKING",
        "notes": "Catalog save serializes full objects; no redact.",
    },
    {
        "id": "W-derived-renderer",
        "class": "derived-renderer",
        "path": "tools/command-center/render.py",
        "anchor": "render.py:295 write_all write_text",
        "redaction": "LACKING",
        "notes": "Renders STATUS.md and derived JSON from catalog bytes.",
    },
    {
        "id": "W-supervisor-log",
        "class": "supervisor-log",
        "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        "anchor": "dispatch_cursor.py:45 log(); :428 CURSOR_API_KEY presence",
        "redaction": "LACKING",
        "notes": "Appends supervisor.log; checks CURSOR_API_KEY; no redact.",
    },
    {
        "id": "W-cloud-submitter",
        "class": "cloud-job-submitter",
        "path": "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py",
        "anchor": "bringup_cursor_fleet.py:68-72 token prefix print",
        "redaction": "LACKING",
        "notes": "Reads CURSOR_API_TOKEN/KEY; prints length and 4-char prefix.",
    },
    {
        "id": "W-rollback-arc0014",
        "class": "rollback-backup",
        "path": "command-center/p2-wave/probes/ARC-0014/rollback.py",
        "anchor": "rollback.py:128 ledger_path.write_text",
        "redaction": "LACKING",
        "notes": "Rewrites ledger JSON after rehearsal; no redact.",
    },
    {
        "id": "W-monitor",
        "class": "monitor",
        "path": "tools/monitor/",
        "anchor": "ABSENT on this tree",
        "redaction": "NOT-CHECKED",
        "notes": "No monitor writer package on this sparse checkout.",
    },
    {
        "id": "W-package-builder",
        "class": "package-builder",
        "path": "package.json",
        "anchor": "ABSENT on this tree",
        "redaction": "NOT-CHECKED",
        "notes": "No npm/wheel publish writer on this tree (lockfile fixtures only).",
    },
    {
        "id": "W-transcript-exporter",
        "class": "transcript-exporter",
        "path": "tools/council/artifacts/",
        "anchor": "ABSENT on this tree",
        "redaction": "NOT-CHECKED",
        "notes": "No council transcript exporter on this sparse checkout.",
    },
]


def _on_tree(rel: str) -> bool:
    path = REPO / rel
    return path.is_file() or path.is_dir()


def writers() -> list[dict]:
    rows = []
    for spec in _WRITER_SPECS:
        row = dict(spec)
        row["on_this_tree"] = _on_tree(spec["path"])
        if not row["on_this_tree"] and spec["redaction"] != "NOT-CHECKED":
            row["redaction"] = "NOT-CHECKED"
        rows.append(row)
    return rows


def _env_source(name: str, scope: str) -> dict:
    present = name in os.environ
    raw = os.environ.get(name, "") if present else ""
    return {
        "id": f"S-env-{name}",
        "kind": "environment",
        "name": name,
        "scope": scope,
        "present": present,
        "byte_length": len(raw.encode("utf-8")) if present else 0,
        "value_reported": False,
    }


def _file_source(rel: str, kind: str, scope: str) -> dict:
    path = REPO / rel
    candidates = [path]
    if rel.startswith(".") or rel.startswith("~"):
        candidates.append(Path.home() / rel.lstrip("~/"))
    existing = next((p for p in candidates if p.is_file()), None)
    return {
        "id": f"S-file-{rel.replace('/', '_').replace('.', '_')}",
        "kind": kind,
        "name": rel,
        "scope": scope,
        "present": existing is not None,
        "byte_length": existing.stat().st_size if existing is not None else 0,
        "value_reported": False,
        "path": str(existing) if existing is not None else rel,
    }


def credential_sources() -> list[dict]:
    rows = [
        _env_source("CURSOR_API_KEY", "process-env; dispatch_cursor supervisor"),
        _env_source("CURSOR_API_TOKEN", "process-env; bringup_cursor_fleet"),
        _env_source("CURSOR_API_KEY", "process-env; dispatch_cursor alias"),
        _env_source("CURSOR_API_TOKEN", "process-env; bringup alias"),
        _env_source("ANTHROPIC_API_KEY", "process-env; named in harvest extracts"),
        _env_source("GITHUB_TOKEN", "process-env; CI harvest"),
        _file_source(
            "tools/mcp/cloud-hub/accounts.json",
            "account-pool",
            "live rotation pool; names/scopes/bytes only; never staged",
        ),
        _file_source(
            "tools/mcp/search-hub/accounts.json",
            "account-pool",
            "live rotation pool; names/scopes/bytes only; never staged",
        ),
        _file_source("auth.json", "auth-file", "IMP-0061 named credential file"),
        _file_source(".credentials.json", "auth-file", "IMP-0061 named credential file"),
        _file_source(".cursor/mcp.json", "mcp-config", "MCP server env blocks"),
        _file_source("mcp.json", "mcp-config", "MCP server env blocks"),
    ]
    ssh = Path.home() / ".ssh" / "id_ed25519"
    rows.append(
        {
            "id": "S-ssh-id_ed25519",
            "kind": "ssh-key",
            "name": "~/.ssh/id_ed25519",
            "scope": "bringup_cursor_fleet KEY path; SSH to cloud boxes",
            "present": ssh.is_file(),
            "byte_length": ssh.stat().st_size if ssh.is_file() else 0,
            "value_reported": False,
        }
    )
    rows.append(
        {
            "id": "S-keychain-dpapi",
            "kind": "keychain-dpapi",
            "name": "keychain/DPAPI APIs",
            "scope": "Windows DPAPI / macOS keychain; no API imports on this Linux tree",
            "present": False,
            "byte_length": 0,
            "value_reported": False,
        }
    )
    return rows


_CLOUD_KEYS = {
    "CURSOR_API_KEY",
    "CURSOR_API_TOKEN",
    "CURSOR_API_KEY",
    "CURSOR_API_TOKEN",
}
_SERIALIZING = {
    "event-ledger",
    "derived-renderer",
    "receipt-emitter",
    "rollback-backup",
}


def _could_carry(writer: dict, source: dict) -> tuple[bool, str, str]:
    wclass = writer["class"]
    skind = source["kind"]
    wid = writer["id"]
    redaction = writer["redaction"]
    if writer["redaction"] == "NOT-CHECKED" or not writer["on_this_tree"]:
        return False, "NOT-CHECKED", "writer absent or not exercised on this tree"
    if wid == "W-receipt-bld0051":
        if skind == "environment":
            return (
                True,
                "ARMED",
                "emitter may mention env NAMES; values scrubbed by secret_redact.safe_write",
            )
        return True, "ARMED", "receipt write path runs secret_redact.safe_write before bytes hit disk"
    if wclass == "cloud-job-submitter" and source["name"] in _CLOUD_KEYS:
        return True, "LACKING", "bringup reads the env token and prints length plus a 4-char prefix"
    if wclass == "supervisor-log" and source["name"] in {
        "CURSOR_API_KEY",
        "CURSOR_API_KEY",
    }:
        return True, "LACKING", "dispatch checks CURSOR_API_KEY and writes supervisor.log without redact"
    if wclass in _SERIALIZING:
        if skind in {"environment", "auth-file", "account-pool", "mcp-config"}:
            return True, redaction, "writer serializes caller-supplied JSON/text with no redact call"
        if skind == "ssh-key":
            return False, "N/A", "writer does not read SSH key material"
        if skind == "keychain-dpapi":
            return False, "N/A", "no keychain API on this Linux tree"
    if skind == "ssh-key" and wclass == "cloud-job-submitter":
        return True, "LACKING", "bringup uses ~/.ssh/id_ed25519 as KEY for cloud SSH; not redacted"
    return False, "N/A", "no plausible data-flow from this source into this writer on this tree"


def egress_map(
    writer_rows: list[dict] | None = None,
    source_rows: list[dict] | None = None,
) -> list[dict]:
    writer_rows = writer_rows or writers()
    source_rows = source_rows or credential_sources()
    cells = []
    for writer in writer_rows:
        for source in source_rows:
            could, status, evidence = _could_carry(writer, source)
            if not could and status == "N/A":
                continue
            cells.append(
                {
                    "writer_id": writer["id"],
                    "source_id": source["id"],
                    "could_carry": could,
                    "redaction": status,
                    "evidence": evidence,
                }
            )
    return cells


def redact_call_sites() -> list[dict]:
    hits = []
    roots = [REPO / "tools" / "command-center", HERE]
    pattern = re.compile(r"secret_redact|redact_text|safe_write")
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if not pattern.search(text):
                continue
            hits.append({"path": path.relative_to(REPO).as_posix(), "mentions_redactor": True})
    return hits
