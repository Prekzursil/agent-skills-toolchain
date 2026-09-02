"""Oracle cases for live vs hermetic benchmarks (TST-0303).

Each case declares a class, but the class the platform records is the one
observed while the case's oracle actually runs under ``NetworkObserver``.
A case that declares ``hermetic`` and then fetches NVD is recorded as
``advisory-db`` and inherits that class's TTL.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from bench.classify import classify_calls, live_hosts
from bench.observe import NetworkObserver

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=agent-skills-toolchain"
HERMETIC_BLOB = b"agent-skills-toolchain phase0 hermetic digest fixture\n"


def _case_label(case: dict[str, Any] | str | None) -> str:
    if isinstance(case, dict):
        return str(case.get("id") or "")
    return str(case or "")


def oracle_advisory(case: dict[str, Any] | str | None = None) -> str:
    """Live oracle: queries the NVD advisory database for the case keyword."""
    label = _case_label(case)
    url = NVD_URL + ("&label=" + label if label else "")
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read()
    try:
        json.loads(body.decode("utf-8") or "{}")
    except ValueError:
        return "advisory-db:unparsed"
    return "advisory-db"


def oracle_hermetic(case: dict[str, Any] | str | None = None) -> str:
    """Hermetic oracle: pure computation, no network."""
    label = _case_label(case)
    digest = hashlib.sha256(HERMETIC_BLOB + label.encode("utf-8")).hexdigest()
    return f"hermetic:{digest[:12]}"


def oracle_lie_hermetic(case: dict[str, Any] | str | None = None) -> str:
    """Declares hermetic, but its check consults NVD before answering."""
    oracle_advisory(case)
    return oracle_hermetic(case)


ORACLES: dict[str, Callable[[Any], str]] = {
    "advisory": oracle_advisory,
    "hermetic": oracle_hermetic,
    "lie-hermetic": oracle_lie_hermetic,
}

CASES: list[dict[str, Any]] = [
    {"id": "advisory-nvd", "declared_class": "advisory-db", "oracle": "advisory"},
    {"id": "hermetic-unit", "declared_class": "hermetic", "oracle": "hermetic"},
    {"id": "hermetic-digest", "declared_class": "hermetic", "oracle": "hermetic"},
    {"id": "lie-hermetic-hits-nvd", "declared_class": "hermetic", "oracle": "lie-hermetic"},
]


@dataclass
class LiveResult:
    result_id: str
    observed_class: str
    captured_at: datetime
    verdict: str = "PASS"
    case_id: str = ""
    declared_class: str = ""
    observed_hosts: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    oracle_output: str = ""

    @property
    def mismatch(self) -> bool:
        return self.declared_class != self.observed_class

    def as_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "case_id": self.case_id,
            "declared_class": self.declared_class,
            "observed_class": self.observed_class,
            "observed_hosts": list(self.observed_hosts),
            "mismatch": self.mismatch,
            "captured_at": self.captured_at.isoformat(),
            "verdict": self.verdict,
        }


def case_by_id(cid: str) -> dict[str, Any]:
    for row in CASES:
        if row["id"] == cid:
            return row
    raise KeyError(cid)


def observe_case(case: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    """Run the case's oracle under the observer; return (class, calls, output)."""
    oracle = ORACLES[str(case.get("oracle") or "hermetic")]
    with NetworkObserver() as obs:
        output = oracle(case)
        calls = obs.snapshot()
    return classify_calls(calls), calls, str(output)


def execute_case(case: dict[str, Any], *, captured_at: datetime, result_id: str) -> LiveResult:
    observed, calls, output = observe_case(case)
    return LiveResult(
        result_id=result_id,
        observed_class=observed,
        captured_at=captured_at,
        case_id=str(case["id"]),
        declared_class=str(case.get("declared_class") or case.get("kind") or ""),
        observed_hosts=live_hosts(calls),
        calls=calls,
        oracle_output=output,
    )
