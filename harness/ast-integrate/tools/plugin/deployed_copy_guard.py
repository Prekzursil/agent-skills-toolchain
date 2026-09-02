"""Detect edits targeting a deployed copy and inject the canonical repo path."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ADVISORY_MARK = "IMP-0037-DEPLOYED-COPY"
CANON_TOKEN = "canonical-repo:"
FORCE_ERROR_ENV = "IMP0037_FORCE_ERROR"


def blocks(payload: dict[str, Any]) -> bool:
    spec = payload.get("hookSpecificOutput") or {}
    if spec.get("permissionDecision") == "deny":
        return True
    if payload.get("continue") is False:
        return True
    return False


def load_ledger(path: Path | str | None = None) -> list[dict[str, Any]]:
    env = os.environ.get("DEPLOY_PROVENANCE_LEDGER")
    p = Path(path or env or "")
    if not p.is_file():
        return []
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if isinstance(doc, dict):
        rows = doc.get("records") or doc.get("entries") or []
        return [x for x in rows if isinstance(x, dict)]
    return []


def lookup(file_path: str, ledger: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    rows = ledger if ledger is not None else load_ledger()
    target = str(Path(file_path))
    for row in rows:
        live = str(row.get("live_path") or row.get("deployed") or "")
        if live and Path(live) == Path(target):
            return row
    return None


def advisory_payload(canonical: str) -> dict[str, Any]:
    ctx = f"{ADVISORY_MARK} edit the repo source instead: {CANON_TOKEN}{canonical}"
    return {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": ctx,
        },
        "systemMessage": ctx,
    }


def silent_payload() -> dict[str, Any]:
    return {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        },
    }


def handle_event(event: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get(FORCE_ERROR_ENV) == "1":
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": "fail-open",
            },
        }
    tool_input = event.get("tool_input") or {}
    path = str(tool_input.get("file_path") or "")
    hit = lookup(path)
    if hit:
        canon = str(hit.get("repo_path") or hit.get("canonical") or "")
        return advisory_payload(canon)
    return silent_payload()
