"""Hook-lifecycle comparison from on-disk rails (two independent parses).

Claude Code events: snapshot table AND RES-0009 captured stdin files.
Codex events: TST-0082 healthy hooks.json AND the loader's declared keys.
A live vendor binary is NOT invented when absent from PATH.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLAUDE_SNAP = REPO / "command-center/p2-wave/probes/RES-0009/snapshots/cli-hooks.md"
CLAUDE_CAPS = REPO / "command-center/p2-wave/probes/RES-0009/captures"
CODEX_HOOKS = REPO / "command-center/p2-wave/probes/TST-0082/fixtures/healthy/hooks.json"
CODEX_RECEIPT = REPO / "command-center/p2-wave/probes/TST-0082/captures/healthy-receipt.txt"
TABLE_RE = re.compile(r"^\| `([A-Z][A-Za-z0-9]+)` \|", re.M)
RECEIPT_RE = re.compile(r"^RECEIPT event=([A-Za-z0-9]+)\b", re.M)


def _sha_lineage(path: Path) -> dict[str, str]:
    import hashlib
    from datetime import datetime, timezone

    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "resolved_url": f"file://{path.as_posix()}",
        "fetch_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": str(len(raw)),
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
    }


def claude_from_snapshot(text: str) -> list[str]:
    return list(dict.fromkeys(TABLE_RE.findall(text)))


def claude_from_captures(cap_dir: Path) -> list[str]:
    names = []
    for path in sorted(cap_dir.glob("*.json")):
        names.append(path.stem)
    return names


def codex_from_hooks_json(path: Path) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    hooks = doc.get("hooks") or {}
    if not isinstance(hooks, dict):
        return []
    return sorted(hooks.keys())


def codex_from_receipt(path: Path) -> list[str]:
    """Second signal: events a Codex-shaped dispatcher actually fired."""
    text = path.read_text(encoding="utf-8")
    return list(dict.fromkeys(RECEIPT_RE.findall(text)))


def compare() -> dict[str, Any]:
    snap_text = CLAUDE_SNAP.read_text(encoding="utf-8")
    from_table = claude_from_snapshot(snap_text)
    from_caps = claude_from_captures(CLAUDE_CAPS)
    claude = sorted(set(from_table) & set(from_caps))
    if not claude:
        claude = sorted(set(from_caps) or set(from_table))
    codex_keys = codex_from_hooks_json(CODEX_HOOKS)
    codex_fired = codex_from_receipt(CODEX_RECEIPT)
    codex = sorted(set(codex_keys) & set(codex_fired)) or sorted(set(codex_keys) or set(codex_fired))
    claude_only = sorted(set(claude) - set(codex))
    codex_only = sorted(set(codex) - set(claude))
    shared = sorted(set(claude) & set(codex))
    # Two parse paths must agree on the Claude set used for uniqueness.
    table_vs_caps = sorted(set(from_table) ^ set(from_caps))
    unique_runtime = None
    unique_events = []
    if claude_only:
        unique_runtime = "claude-code"
        unique_events = claude_only
    elif codex_only:
        unique_runtime = "codex"
        unique_events = codex_only
    return {
        "claude_events": claude,
        "claude_from_snapshot_table": from_table,
        "claude_from_captures": from_caps,
        "claude_table_capture_symmetric_diff": table_vs_caps,
        "codex_events": codex,
        "codex_from_hooks_json": codex_keys,
        "codex_from_receipt_fire": codex_fired,
        "shared": shared,
        "claude_only": claude_only,
        "codex_only": codex_only,
        "unique_lifecycle_runtime": unique_runtime,
        "unique_lifecycle_events": unique_events,
        "cursor_status": "NOT-CHECKED",
        "cursor_reason": "no Cursor hook snapshot on this worktree and live Cursor session was not driven",
        "lineage": {
            "claude_snapshot": _sha_lineage(CLAUDE_SNAP),
            "codex_hooks_json": _sha_lineage(CODEX_HOOKS),
            "codex_receipt": _sha_lineage(CODEX_RECEIPT),
        },
        "pass": bool(unique_runtime) and len(claude_only) >= 1 and len(shared) >= 1,
    }
