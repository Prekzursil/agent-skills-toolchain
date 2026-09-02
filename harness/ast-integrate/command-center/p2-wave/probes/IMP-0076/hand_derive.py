"""Independent millipoint oracle for IMP-0076 probe1.

This is a second copy of the integer formula, not an import of
tools/marketplace/trust_levels.py. Probe1 fails if the two copies disagree
or if either disagrees with the frozen hand_derived table in the fixture.
"""
from __future__ import annotations

from typing import Any, Mapping

WEIGHTS = {
    "signed_releases": 30,
    "conformance_pass_rate": 30,
    "advisory_response_time": 20,
    "provenance_completeness": 20,
}
SAT = 5
ADV_WINDOW = 720


def _signed(signed: int, unsigned: int) -> int:
    total = signed + unsigned
    if total <= 0:
        return 0
    ratio = (signed * 10000) // total
    volume = min(10000, (signed * 10000) // SAT)
    return (ratio * volume) // 10000


def recompute(record: Mapping[str, Any]) -> dict[str, Any]:
    signed = int(record.get("releases_signed") or 0)
    unsigned = int(record.get("releases_unsigned") or 0)
    published = int(record.get("published_version_count") or (signed + unsigned))
    passes = int(record.get("conformance_passes") or 0)
    runs = int(record.get("conformance_runs") or 0)
    adv_count = int(record.get("advisory_count") or 0)
    median = record.get("advisory_median_response_hours")
    complete = int(record.get("provenance_complete_versions") or 0)

    if published <= 0:
        return {
            "level": "UNRATED",
            "score_millipoints": None,
            "signed_mp": None,
            "conformance_mp": None,
            "advisory_mp": None,
            "provenance_mp": None,
        }

    signed_mp = _signed(signed, unsigned)
    conf_mp = 0 if runs <= 0 else (passes * 10000) // runs
    if adv_count <= 0:
        adv_mp = None
    elif median is None:
        adv_mp = 0
    else:
        adv_mp = max(0, 10000 - (int(median) * 10000) // ADV_WINDOW)
    prov_mp = (complete * 10000) // published if published else 0

    parts: list[tuple[int, int]] = [
        (WEIGHTS["signed_releases"], signed_mp),
        (WEIGHTS["conformance_pass_rate"], conf_mp),
    ]
    if adv_mp is not None:
        parts.append((WEIGHTS["advisory_response_time"], adv_mp))
    parts.append((WEIGHTS["provenance_completeness"], prov_mp))
    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) // wsum
    if score < 4000:
        level = "LOW"
    elif score < 7000:
        level = "MEDIUM"
    else:
        level = "HIGH"
    return {
        "level": level,
        "score_millipoints": score,
        "signed_mp": signed_mp,
        "conformance_mp": conf_mp,
        "advisory_mp": adv_mp,
        "provenance_mp": prov_mp,
    }
