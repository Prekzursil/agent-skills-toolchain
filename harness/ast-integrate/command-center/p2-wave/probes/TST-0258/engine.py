"""Shared loader for TST-0258 fixtures and live simulator runs."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council import simulate as S  # noqa: E402
from tools.council.antifail import unanimity as U  # noqa: E402

CLONE = HERE / "fixtures" / "clone-instant.json"
LEGIT = HERE / "fixtures" / "legitimate-late.json"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0258.json"
SENTINEL = "SUCCESS:TST-0258"


def load_clone() -> dict[str, Any]:
    return S.load_spec(CLONE)


def load_legit() -> dict[str, Any]:
    return S.load_spec(LEGIT)


def roster(spec: dict[str, Any]) -> list[str]:
    return S.roster_ids(spec)


def run(spec: dict[str, Any], *, remediation: str = "full") -> dict[str, Any]:
    return S.run(spec, remediation=remediation)


def twice_identical(spec: dict[str, Any], *, remediation: str = "full") -> tuple[dict[str, Any], bool]:
    a = run(spec, remediation=remediation)
    b = run(spec, remediation=remediation)
    return a, S.canonical_bytes(a) == S.canonical_bytes(b)
