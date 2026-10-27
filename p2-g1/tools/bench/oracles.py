"""Oracle cases for live vs hermetic benchmarks."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

CASES = [
    {"id": "advisory-nvd", "observed_class": "advisory-db", "kind": "advisory-db"},
    {"id": "hermetic-unit", "observed_class": "hermetic", "kind": "hermetic"},
]


@dataclass
class LiveResult:
    result_id: str
    observed_class: str
    captured_at: datetime
    verdict: str = "PASS"
    case_id: str = ""


def case_by_id(cid: str) -> dict[str, Any]:
    for row in CASES:
        if row["id"] == cid:
            return row
    raise KeyError(cid)


def execute_case(case: dict[str, Any], *, captured_at: datetime, result_id: str) -> LiveResult:
    return LiveResult(
        result_id=result_id,
        observed_class=str(case["observed_class"]),
        captured_at=captured_at,
        case_id=str(case["id"]),
    )


def oracle_advisory(case: dict[str, Any] | None = None) -> str:
    return "advisory-db"


def oracle_hermetic(case: dict[str, Any] | None = None) -> str:
    return "hermetic"
