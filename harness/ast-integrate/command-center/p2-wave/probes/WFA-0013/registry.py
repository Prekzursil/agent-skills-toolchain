#!/usr/bin/env python3
"""Load the 284-candidate registry from any on-disk location that actually exists."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CANDIDATE_PATHS = [
    Path.home() / ".claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/root/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "command-center/_wfa2_entries.json",
    REPO / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
]


def load_registry() -> tuple[dict[str, Any] | None, dict[str, Any]]:
    tried = []
    for path in CANDIDATE_PATHS:
        rec = {"path": str(path), "exists": False, "n": 0, "ok": False}
        try:
            rec["exists"] = path.is_file()
        except OSError:
            rec["exists"] = False
        tried.append(rec)
        if not rec["exists"]:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            rec["error"] = type(exc).__name__
            continue
        rows = doc.get("candidates") if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            rec["error"] = "no-candidates-array"
            continue
        rec["n"] = len(rows)
        rec["ok"] = True
        meta = {
            "path": str(path.as_posix() if path.is_absolute() else path),
            "n": len(rows),
            "coverage": "SCANNED",
            "tried": tried,
        }
        return doc, meta
    return None, {
        "path": None,
        "n": 0,
        "coverage": "NOT-CHECKED",
        "reason": "08-WORKFLOW-CANDIDATE-REGISTRY.json not present on this Linux host",
        "tried": tried,
    }
