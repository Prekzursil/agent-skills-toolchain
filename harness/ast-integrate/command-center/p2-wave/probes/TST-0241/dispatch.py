"""O(1) per-unit dispatch: route a work unit and record it on a ledger."""
from __future__ import annotations

import hashlib
from typing import Any

from fixtures import LANES
from ledger import EmptyInputError


def route(unit_id: str) -> str:
    digest = hashlib.sha256(unit_id.encode("utf-8")).digest()
    return LANES[digest[0] % len(LANES)]


def dispatch_record(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": unit["id"],
        "lane": route(str(unit["id"])),
        "payload": unit["payload"],
        "seq": unit["seq"],
    }


def dispatch_cohort(units: list[dict[str, Any]], ledger: Any) -> list[int]:
    if not units:
        raise EmptyInputError(
            "dispatch_cohort: n_inputs=0; FAIL rather than report a time"
        )
    written: list[int] = []
    for unit in units:
        written.append(ledger.write(dispatch_record(unit)))
    return written
