#!/usr/bin/env python3
"""Shared completion predicate used at nested-council fan-in.

This is the confirmer-authored reducer for CNF-0174. Production CC-0003
(`agentspec.oracle.judge` / tools/council) is absent on this worktree; the
parent record cites this module path so a second local majority rule cannot
hide. Anti-patterns from the CC-0003 contract:

* exit code zero alone is never success
* a plausible digest is not a receipt
* a file path in text is not proof the file exists
"""
from __future__ import annotations

from typing import Any

MODULE_PATH = "command-center/p2-wave/probes/CNF-0174/reducer.py"
SYMBOL = "judge"

COMPLETE = "COMPLETE"
INCOMPLETE = "INCOMPLETE"
BLOCKED = "BLOCKED"
FAILED = "FAILED"
NOT_CHECKED = "NOT-CHECKED"

TERMINAL_NONCOMPLETE = {INCOMPLETE, BLOCKED, FAILED}


def _cond(cid: str, passed: bool, note: str) -> dict[str, Any]:
    return {"id": cid, "pass": passed, "note": note}


def judge(record: dict[str, Any]) -> dict[str, Any]:
    """Return a typed verdict plus per-condition pointers. Never a bare bool."""
    if not isinstance(record, dict):
        return {
            "verdict": FAILED,
            "claimed": None,
            "conditions": [_cond("record-shape", False, "record is not an object")],
            "reducer_module": MODULE_PATH,
            "reducer_symbol": SYMBOL,
        }

    claimed = str(record.get("completion") or "").upper() or None
    exit_code = record.get("exit_code")
    present = bool(record.get("artifact_present"))
    digest = str(record.get("artifact_digest") or "")
    path_text = str(record.get("artifact_path") or record.get("artifact_path_in_text") or "")
    evidence = str(record.get("reasoning") or record.get("evidence") or "").strip()

    conditions = [
        _cond(
            "exit-zero-is-not-success",
            not (exit_code == 0 and not present),
            "exit_code==0 with missing artifact is INCOMPLETE",
        ),
        _cond(
            "digest-is-not-receipt",
            not (bool(digest) and not present),
            "a digest without artifact_present is not a receipt",
        ),
        _cond(
            "path-is-not-proof",
            not (bool(path_text) and not present),
            "a path string is not proof the file exists",
        ),
        _cond(
            "evidence-nonempty-when-complete",
            not (claimed == COMPLETE and not evidence),
            "COMPLETE requires non-empty reasoning/evidence",
        ),
        _cond(
            "artifact-present-when-complete",
            not (claimed == COMPLETE and not present),
            "COMPLETE requires artifact_present=true",
        ),
    ]

    any_fail = any(not c["pass"] for c in conditions)
    if claimed == COMPLETE and not any_fail:
        verdict = COMPLETE
    elif claimed in TERMINAL_NONCOMPLETE:
        verdict = claimed
    elif claimed == COMPLETE and any_fail:
        verdict = INCOMPLETE
    elif not claimed:
        verdict = NOT_CHECKED
    else:
        verdict = INCOMPLETE

    return {
        "verdict": verdict,
        "claimed": claimed,
        "conditions": conditions,
        "reducer_module": MODULE_PATH,
        "reducer_symbol": SYMBOL,
        "child_id": record.get("id"),
    }
