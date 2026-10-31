"""CNF-0136 fault taxonomy. Infrastructure faults are BLOCKED, never REFUTED.

CNF-0136-TAXONOMY-TABLE
"""
from __future__ import annotations

from typing import Any

# CNF-0136-ROW severed-stream
# CNF-0136-ROW quota-429-storm
# CNF-0136-ROW timeout-<n>s
# CNF-0136-ROW duplicate-dispatch
# CNF-0136-ROW runner-crash-as-severed-stream

TAXONOMY: tuple[str, ...] = (
    "severed-stream",
    "quota-429-storm",
    "timeout-<n>s",
    "duplicate-dispatch",
    "runner-crash-as-severed-stream",
)

FORBIDDEN_INFRA_VERDICTS = frozenset({"CONFIRMED", "REFUTED"})

_PREREQ = {
    "severed-stream": "restore-confirmer-stream",
    "quota-429-storm": "vendor-quota-headroom",
    "timeout-<n>s": "extend-or-split-confirmation-timeout",
    "duplicate-dispatch": "dedupe-confirmation-job-id",
    "runner-crash-as-severed-stream": "restore-confirmer-stream",
}

_KIND_TO_FAULT = {
    "kill": "severed-stream",
    "crash": "severed-stream",
    "http-429": "quota-429-storm",
    "timeout": "timeout-<n>s",
    "duplicate": "duplicate-dispatch",
}

_INFRA_NEEDLES = (
    "sigkill",
    "killed",
    "crash",
    "429",
    "529",
    "timeout",
    "deadline",
    "severed",
    "stream-eof",
    "duplicate-dispatch",
    "runner-crash",
)


def map_fault(cls: str) -> dict[str, Any]:
    fault = _KIND_TO_FAULT.get(cls, cls)
    if fault == "runner-crash-as-severed-stream":
        fault = "severed-stream"
    return {
        "verdict": "BLOCKED",
        "fault_class": fault,
        "named_prerequisite": _PREREQ.get(fault, "restore-confirmer-stream"),
    }


def naive_launder_to_refuted(cls: str) -> str:
    del cls
    return "REFUTED"


def evidence_looks_like_infra(blob: str) -> bool:
    text = str(blob or "").lower()
    return any(n in text for n in _INFRA_NEEDLES)
