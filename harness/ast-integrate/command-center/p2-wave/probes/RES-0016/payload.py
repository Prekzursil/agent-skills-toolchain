"""Read measurement fields from a receipt-shaped or legacy top-level artifact."""
from __future__ import annotations

from typing import Any


def measurements_of(doc: dict[str, Any]) -> dict[str, Any]:
    meas = doc.get("measurements")
    if isinstance(meas, dict) and meas:
        return meas
    report = doc.get("report")
    if isinstance(report, dict):
        nested = report.get("measurements")
        if isinstance(nested, dict) and nested:
            return nested
    return {}


def detector_fired(doc: dict[str, Any]) -> bool:
    rev = doc.get("reviewer")
    if isinstance(rev, dict) and rev.get("detector_control_fired") is True:
        return True
    report = doc.get("report")
    if isinstance(report, dict) and report.get("detector_control_fired") is True:
        return True
    det = measurements_of(doc).get("detector_control")
    return isinstance(det, dict) and det.get("fired") is True
