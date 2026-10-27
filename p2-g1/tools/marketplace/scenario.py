"""Benchmark-gaming scenario loader (IMP-0097)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Record:
    record_id: str
    claimed_delta: float
    reproduced: bool
    independent: bool
    publisher_only: bool = False


def load_scenario() -> tuple[dict[str, Any], list[Record], dict[str, Any], dict[str, Any]]:
    records = [
        Record("rec.unreproduced.claim", 4.0, reproduced=False, independent=False),
        Record("rec.publisher-only.rerun", 3.0, reproduced=True, independent=False, publisher_only=True),
        Record("rec.failed.independent", 2.5, reproduced=False, independent=True),
        Record("rec.independent.reproduced", 1.5, reproduced=True, independent=True),
        Record("rec.self-authored.reproduced", 2.0, reproduced=True, independent=True),
    ]
    measurements = {"base": 10.0}
    provenance = {
        "rec.independent.reproduced": {"independent": True, "reproduced": True},
        "rec.self-authored.reproduced": {
            "independent": True,
            "reproduced": True,
            "self_authored": True,
            "case_set": "bench.acme.easy-v1",
        },
        "rec.unreproduced.claim": {"independent": False, "reproduced": False},
        "rec.publisher-only.rerun": {"independent": False, "reproduced": True},
        "rec.failed.independent": {"independent": True, "reproduced": False},
    }
    raw = {"records": [r.record_id for r in records]}
    return measurements, records, provenance, raw
