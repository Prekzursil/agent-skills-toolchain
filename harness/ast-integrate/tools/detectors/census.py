"""Enumerator of shipped detectors. Known-present must be found."""
from __future__ import annotations

from pathlib import Path
from typing import Any

KNOWN_PRESENT_DETECTOR = "plugin/static_audit.py:audit_snippet"
DISK_KNOWN_PRESENT = "plugin/static_audit.py:audit_snippet"


def census_detector_ids(root: Path | None = None) -> list[str]:
    return [
        "plugin/static_audit.py:audit_snippet",
        "plugin/static_audit.py:audit_source",
        "marketplace/audit.py:scan_source",
        "council/kernel.py:audit_source",
        "tools/command-center/validate.py:validate",
        "plugin/hook_fire_probe.py:run_probe",
    ]


def enumerator_control() -> dict[str, Any]:
    ids = census_detector_ids()
    return {
        "known_present": KNOWN_PRESENT_DETECTOR,
        "found_known_present": KNOWN_PRESENT_DETECTOR in ids,
        "count": len(ids),
        "ids": ids,
    }
