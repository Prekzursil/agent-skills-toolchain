"""Live candidate inventory: dispatcher registered set, ledgers, AUD-0013."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_MANIFEST = REPO / "hooks" / "_dispatch" / "manifest.json"
AUD0013 = REPO / "command-center" / "audit" / "AUD-0013-hooks-manifest-parity.json"


def _row(path: Path, role: str) -> dict[str, Any]:
    exists = path.exists()
    is_file = path.is_file()
    is_dir = path.is_dir()
    size = path.stat().st_size if is_file else 0
    nfiles = 0
    if is_dir:
        nfiles = sum(1 for p in path.rglob("*") if p.is_file())
    return {
        "path": str(path),
        "role": role,
        "exists": exists,
        "is_file": is_file,
        "is_dir": is_dir,
        "bytes": size,
        "file_count": nfiles,
    }


def candidate_paths() -> list[tuple[Path, str]]:
    home = Path.home()
    return [
        (LIVE_MANIFEST, "repo-dispatch-manifest"),
        (REPO / "hooks" / "hooks.json", "repo-hooks-json"),
        (REPO / "hooks" / "_dispatch" / "dispatch.py", "repo-dispatch-py"),
        (REPO / "agent-self" / "config" / "hooks" / "hooks.json", "agent-self-hooks-json"),
        (AUD0013, "aud-0013-parity"),
        (home / ".claude" / "hooks", "live-claude-hooks"),
        (home / ".claude" / "event-ledger", "live-claude-event-ledger"),
        (home / ".claude" / "logs", "live-claude-logs"),
        (home / ".agents" / "hooks", "live-agents-hooks"),
    ]


def log_search_paths() -> list[tuple[Path, str]]:
    """Paths that may contain per-hook fire records. Not the whole hooks/ tree."""
    home = Path.home()
    return [
        (home / ".claude" / "event-ledger", "live-claude-event-ledger"),
        (home / ".claude" / "logs", "live-claude-logs"),
        (home / ".claude" / "hooks", "live-claude-hooks"),
        (home / ".agents" / "hooks", "live-agents-hooks"),
    ]


def inventory() -> dict[str, Any]:
    rows = [_row(p, role) for p, role in candidate_paths()]
    present = [r for r in rows if r["exists"] and (r["is_file"] or r["file_count"] > 0)]
    return {
        "candidates": rows,
        "present_count": len(present),
        "estate_hook_tree_present": any(
            r["role"] in {"repo-dispatch-manifest", "repo-dispatch-py", "live-claude-hooks"}
            and r["exists"]
            and (r["is_file"] or r["file_count"] > 0)
            for r in rows
        ),
        "aud0013_present": any(r["role"] == "aud-0013-parity" and r["is_file"] for r in rows),
        "live_ledger_present": any(
            r["role"] == "live-claude-event-ledger"
            and r["exists"]
            and (r["is_file"] or r["file_count"] > 0)
            for r in rows
        ),
        "live_log_search_present": any(
            _row(p, role)["exists"] and (_row(p, role)["is_file"] or _row(p, role)["file_count"] > 0)
            for p, role in log_search_paths()
        ),
    }


def load_live_manifest() -> dict[str, Any] | None:
    if not LIVE_MANIFEST.is_file():
        return None
    return json.loads(LIVE_MANIFEST.read_text(encoding="utf-8"))


def live_registered_checks(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = manifest if manifest is not None else load_live_manifest()
    if not isinstance(doc, dict):
        return []
    out: list[dict[str, Any]] = []
    events = doc.get("events") or {}
    if not isinstance(events, dict):
        return []
    for event, body in events.items():
        if not isinstance(body, dict):
            continue
        for chk in body.get("checks") or []:
            if not isinstance(chk, dict):
                continue
            name = str(chk.get("name") or chk.get("script") or "")
            if not name:
                continue
            out.append(
                {
                    "id": name,
                    "event": str(event),
                    "script": str(chk.get("script") or ""),
                    "matcher": chk.get("matcher"),
                    "timeout": chk.get("timeout"),
                    "emits": chk.get("emits"),
                    "side_effect": chk.get("side_effect"),
                    "enabled": chk.get("enabled") is not False,
                }
            )
    return out


def live_registered_ids() -> list[str]:
    seen: list[str] = []
    for chk in live_registered_checks():
        hid = chk["id"]
        if hid not in seen:
            seen.append(hid)
    return seen


def load_registered_manifest() -> dict[str, Any]:
    path = HERE / "fixtures" / "registered" / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def registered_ids(manifest: dict[str, Any] | None = None) -> list[str]:
    """Fixture corpus ids used by the planted/silent searcher detector-control."""
    doc = manifest if manifest is not None else load_registered_manifest()
    return [str(h["id"]) for h in doc.get("hooks") or [] if isinstance(h, dict) and h.get("id")]
