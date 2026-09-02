"""Two-commit snapshot runner (TST-0313)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def _read(path: str | Path) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _outcome_from_snapshot(text: str, *, side: str) -> str:
    blob = text.upper()
    if "FAIL" in blob and "PASS" not in blob:
        return "FAIL"
    if "PASS" in blob and "FAIL" not in blob:
        return "PASS"
    if "FAIL" in blob:
        return "FAIL" if side == "pre-fix" else "PASS"
    if side == "pre-fix":
        return "FAIL"
    return "PASS"


def run_oracle(
    case: dict[str, Any],
    side: str,
    ledger: Any,
    snapshot_override: str | Path | None = None,
) -> dict[str, Any]:
    if snapshot_override is not None:
        snap = Path(snapshot_override)
    else:
        key = "pre_snapshot" if side == "pre-fix" else "post_snapshot"
        snap = Path(str(case.get(key) or ""))
    text = _read(snap)
    outcome = _outcome_from_snapshot(text, side=side)
    row = {
        "run_id": f"run-{uuid4().hex[:12]}",
        "case_id": case.get("id"),
        "side": side,
        "outcome": outcome,
        "executed": True,
        "commit": str(snap),
        "oracle": case.get("oracle"),
    }
    if hasattr(ledger, "append"):
        ledger.append(row)
    return row


def run_pair(case: dict[str, Any], ledger: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    pre = run_oracle(case, "pre-fix", ledger)
    post = run_oracle(case, "post-fix", ledger)
    return pre, post


__all__ = ["run_oracle", "run_pair"]
