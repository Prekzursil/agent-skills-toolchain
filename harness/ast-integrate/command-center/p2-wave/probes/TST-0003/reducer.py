"""Shared 12-condition unit-completion reducer.

Conditions 1-12 are independently addressable boolean checks. evaluate()
returns the first failing condition (lowest id) or PASS. A call site that
wants to skip a condition must pass skip=; production judges never skip.
Exit code 0 is not consulted. A digest or path string is not existence.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

TERMINAL_STATES = frozenset(
    {"SUCCESS", "FAILED", "BLOCKED", "TIMEOUT", "SEVERED", "PARTIAL"}
)
SENTINEL_PREFIXES = ("SUCCESS:", "FAILED:", "BLOCKED:", "TIMEOUT:", "SEVERED:")

Check = Callable[[dict], tuple[bool, str]]

CONDITIONS: list[tuple[int, str, Check]] = []


def _c1(receipt: dict) -> tuple[bool, str]:
    state = str(receipt.get("state") or "")
    if state not in TERMINAL_STATES:
        return False, f"state {state!r} is not a valid terminal state"
    return True, "terminal-state"


def _c2(receipt: dict) -> tuple[bool, str]:
    arts = receipt.get("artifacts") or []
    if not isinstance(arts, list) or not arts:
        return False, "no artifacts declared"
    art = arts[0] if isinstance(arts[0], dict) else {}
    if art.get("exists") is not True:
        return False, "artifact exists is not True (a path or digest is not existence)"
    return True, "artifact-exists"


def _c3(receipt: dict) -> tuple[bool, str]:
    arts = receipt.get("artifacts") or [{}]
    art = arts[0] if arts and isinstance(arts[0], dict) else {}
    nbytes = int(art.get("bytes") or 0)
    floor = int(receipt.get("min_bytes_threshold") or 128)
    if nbytes <= 0:
        return False, "artifact is empty"
    if nbytes < floor:
        return False, f"artifact {nbytes}B is below min_bytes_threshold {floor}"
    return True, "artifact-size"


def _c4(receipt: dict) -> tuple[bool, str]:
    if receipt.get("schema_valid") is not True:
        return False, "schema_valid is not True"
    return True, "schema-parse"


def _c5(receipt: dict) -> tuple[bool, str]:
    sentinel = str(receipt.get("sentinel") or "")
    if not sentinel:
        return False, "sentinel missing"
    if not sentinel.startswith(SENTINEL_PREFIXES):
        return False, "sentinel lacks a required completion prefix"
    return True, "sentinel-present"


def _c6(receipt: dict) -> tuple[bool, str]:
    evidence = receipt.get("evidence") or []
    if not isinstance(evidence, list) or not evidence:
        return False, "no evidence anchors"
    for row in evidence:
        if not isinstance(row, dict):
            return False, "evidence row is not an object"
        if not row.get("anchor") or not row.get("claim"):
            return False, "evidence row missing anchor or claim"
    return True, "evidence-anchors"


def _c7(receipt: dict) -> tuple[bool, str]:
    tests = receipt.get("tests") or []
    if not isinstance(tests, list) or not tests:
        return False, "no tests recorded"
    for row in tests:
        if not isinstance(row, dict):
            return False, "test row is not an object"
        if row.get("result") != "PASS":
            return False, f"test {row.get('id')} result {row.get('result')!r}"
    return True, "tests-passed"


def _c8(receipt: dict) -> tuple[bool, str]:
    controls = receipt.get("negative_controls") or []
    if not isinstance(controls, list) or not controls:
        return False, "no negative controls"
    for row in controls:
        if not isinstance(row, dict):
            return False, "negative-control row is not an object"
        if row.get("fired_on_bad_state") is not True:
            return False, f"negative control {row.get('id')} did not fire on the bad state"
        if row.get("silent_on_good_state") is not True:
            return False, f"negative control {row.get('id')} was not silent on the good state"
    return True, "negative-controls"


def _c9(receipt: dict) -> tuple[bool, str]:
    reviewer = receipt.get("reviewer") or {}
    if not isinstance(reviewer, dict):
        return False, "reviewer is not an object"
    if reviewer.get("verdict") != "PASS":
        return False, f"reviewer verdict {reviewer.get('verdict')!r}"
    if reviewer.get("independent") is not True:
        return False, "reviewer is not independent"
    return True, "reviewer-pass"


def _c10(receipt: dict) -> tuple[bool, str]:
    for defect in receipt.get("defects") or []:
        if not isinstance(defect, dict):
            continue
        sev = str(defect.get("severity") or "").upper()
        status = str(defect.get("status") or "").lower()
        if sev in {"P0", "P1", "BLOCKER"} and status in {"open", "unresolved", ""}:
            return False, f"unresolved {sev} defect {defect.get('id')}"
    return True, "no-open-p0-p1"


def _c11(receipt: dict) -> tuple[bool, str]:
    man = receipt.get("manifest_registration") or {}
    if not isinstance(man, dict) or man.get("registered") is not True:
        return False, "output is not registered in the artifact manifest"
    return True, "manifest-registered"


def _c12(receipt: dict) -> tuple[bool, str]:
    consumers = receipt.get("downstream_consumers") or []
    if not isinstance(consumers, list) or not consumers:
        return False, "no downstream consumers"
    for row in consumers:
        if not isinstance(row, dict):
            return False, "consumer row is not an object"
        if row.get("executed") is not True:
            return False, f"consumer {row.get('consumer')} was not executed"
        if row.get("read_ok") is not True:
            return False, f"consumer {row.get('consumer')} read_ok is not True"
    return True, "downstream-read"


CONDITIONS = [
    (1, "terminal-state", _c1),
    (2, "artifact-exists", _c2),
    (3, "artifact-size", _c3),
    (4, "schema-parse", _c4),
    (5, "sentinel-present", _c5),
    (6, "evidence-anchors", _c6),
    (7, "tests-passed", _c7),
    (8, "negative-controls", _c8),
    (9, "reviewer-pass", _c9),
    (10, "no-open-p0-p1", _c10),
    (11, "manifest-registered", _c11),
    (12, "downstream-read", _c12),
]


def evaluate(receipt: dict[str, Any], skip: Iterable[int] | None = None) -> dict[str, Any]:
    """Return a typed verdict. skip is a test-only seam for the C8 differential."""
    skipped = frozenset(int(x) for x in (skip or ()))
    if not isinstance(receipt, dict):
        return {
            "verdict": "FAILED",
            "failing-condition-id": 1,
            "reason": "receipt is not an object",
            "condition": "terminal-state",
        }
    for cid, name, fn in CONDITIONS:
        if cid in skipped:
            continue
        ok, reason = fn(receipt)
        if not ok:
            return {
                "verdict": "FAILED",
                "failing-condition-id": cid,
                "reason": reason,
                "condition": name,
            }
    return {
        "verdict": "PASS",
        "failing-condition-id": None,
        "reason": "all evaluated conditions satisfied",
        "condition": None,
    }
