"""Planted counterexample report (TST-0116)."""
from __future__ import annotations

from typing import Any

from proptest.runner import run_planted_shrink

REPORT_SCHEMA = {
    "type": "object",
    "required": ["verdict", "shrunk"],
}


def planted_report() -> dict[str, Any]:
    run = run_planted_shrink()
    report = {
        "verdict": "FAIL",
        "shrunk": run["shrunk"],
        "property": run["property"],
        "seed": run["seed"],
    }
    return {"run": run, "report": report}
