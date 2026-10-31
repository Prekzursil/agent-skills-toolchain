"""Payload size budget derived from a previous-archive measurement."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from archive_census import DetectorFailure, census


@dataclass
class Budget:
    max_bytes: int
    max_file_count: int
    derivation: dict[str, Any] = field(default_factory=dict)


def formula_max_bytes(measured_archive_bytes: int) -> int:
    return int(measured_archive_bytes) + max(4096, int(measured_archive_bytes) // 2)


def formula_max_file_count(measured_file_count: int) -> int:
    return int(measured_file_count) + 8


def derive_budget(previous: Path) -> Budget:
    previous = Path(previous)
    measured = census(previous)
    return Budget(
        max_bytes=formula_max_bytes(previous.stat().st_size),
        max_file_count=formula_max_file_count(measured["file_count"]),
        derivation={
            "measured_archive_bytes": previous.stat().st_size,
            "measured_file_count": measured["file_count"],
            "measured_payload_bytes": measured["payload_bytes"],
            "formula": "max_bytes = measured + max(4096, measured//2); max_file_count = n+8",
        },
    )


def check_archive(archive: Path, budget: Budget) -> dict[str, Any]:
    archive = Path(archive)
    try:
        measured = census(archive)
    except DetectorFailure as exc:
        return {
            "ok": False,
            "violations": [f"detector:{exc}"],
            "file_count": 0,
            "independent_file_count": 0,
        }
    violations: list[str] = []
    if measured["os_archive_bytes"] > budget.max_bytes:
        violations.append(
            f"max_bytes:{measured['os_archive_bytes']}>{budget.max_bytes}"
        )
    if measured["file_count"] > budget.max_file_count:
        violations.append(
            f"max_file_count:{measured['file_count']}>{budget.max_file_count}"
        )
    indep_n = len(measured["independent"]["entries"])
    if indep_n != measured["file_count"]:
        violations.append("detector:file_count_mismatch")
    return {
        "ok": not violations,
        "violations": violations,
        "file_count": measured["file_count"],
        "independent_file_count": indep_n,
        "os_archive_bytes": measured["os_archive_bytes"],
    }


def budget_copied_from_current(budget: Budget, current: Path) -> bool:
    current = Path(current)
    size = current.stat().st_size
    return budget.max_bytes in {size, size + 1, size - 1}


def dump_budget(budget: Budget, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(budget), indent=2) + "\n", encoding="utf-8", newline="\n")
