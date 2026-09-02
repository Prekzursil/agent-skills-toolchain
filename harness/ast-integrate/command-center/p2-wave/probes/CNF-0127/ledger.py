#!/usr/bin/env python3
"""Live census + planted retained-improvement list for CNF-0127."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LEDGER_PATH = HERE / "fixtures" / "ledger.json"

LIVE_PATHS = [
    "tools/selfimprove/retain.py",
    "tools/selfimprove/ledger.json",
    "command-center/confirmation/CNF-0052-benchmark-regression.json",
    "command-center/confirmation/CNF-0119-disagreement-adjudication.json",
    "command-center/confirmation/CNF-0027-baseline-variance.json",
]


def census(repo: Path | None = None) -> dict:
    root = repo or REPO
    rows = []
    for rel in LIVE_PATHS:
        p = root / rel
        rows.append(
            {
                "path": rel,
                "present": p.is_file() and p.stat().st_size > 0,
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    live_loop = any(
        r["present"] and r["path"].startswith("tools/selfimprove/") for r in rows
    )
    return {
        "live_selfimprove_loop_present": live_loop,
        "paths": rows,
        "live_retained_improvements": [],
        "note": (
            "No production retention ledger on disk. Confirmation audits the "
            "planted retained-improvement list plus this census; it does not "
            "invent production keeps."
        ),
    }


def load_planted() -> list[dict]:
    doc = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    rows = doc.get("retained_improvements") or []
    if len(rows) < 4:
        raise ValueError(f"planted ledger too small: {len(rows)}")
    return rows


def retained_list() -> dict:
    planted = load_planted()
    live = census()
    return {
        "census": live,
        "planted": planted,
        "under_audit": planted,
        "source": "fixture+census",
    }
