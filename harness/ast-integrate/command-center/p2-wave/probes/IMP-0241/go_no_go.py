#!/usr/bin/env python3
"""Release go/no-go blueprint: consumes the shared oracle, no local checklist.

GO only when oracle.judge returns COMPLETE. NOT-CHECKED from the reducer
blocks as hard as FALSE. This module must not AND a local condition list
and must not treat exit_code==0 as success.
"""
from __future__ import annotations

from typing import Any

from oracle import judge


def release_go_no_go(evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Promotion decision is the shared completion predicate, not a meeting."""
    verdict = judge(evidence)
    decision = "GO" if verdict.get("result") == "COMPLETE" else "NO-GO"
    return {
        "decision": decision,
        "oracle_result": verdict.get("result"),
        "oracle": verdict,
        "reducer": "oracle.judge",
    }
