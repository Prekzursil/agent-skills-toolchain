"""Independent hand-derivation oracle for IMP-0076 (no trust_levels import).

recompute(record) returns {"level", "score_millipoints"} straight from the
published formula spec: ratio*volume signed-release component saturating at 5,
integer pass-rate, linear advisory decay over a 720h window, provenance
completeness ratio; weighted 30/30/20/20; LOW<4000<=MEDIUM<7000<=HIGH.
"""
from __future__ import annotations

from typing import Any


def recompute(record: dict[str, Any]) -> dict[str, Any]:
    signed = int(record.get("releases_signed") or 0)
    unsigned = int(record.get("releases_unsigned") or 0)
    published = int(record.get("published_version_count") or 0)
    passes = int(record.get("conformance_passes") or 0)
    runs = int(record.get("conformance_runs") or 0)
    adv = int(record.get("advisory_count") or 0)
    median = record.get("advisory_median_response_hours")
    complete = int(record.get("provenance_complete_versions") or 0)
    if published <= 0:
        return {"level": "UNRATED", "score_millipoints": None}
    total = signed + unsigned
    ratio = (signed * 10000) // total if total else 0
    volume = min(10000, (signed * 10000) // 5) if total else 0
    signed_mp = (ratio * volume) // 10000 if total else 0
    conf_mp = (passes * 10000) // runs if runs > 0 else 0
    if adv <= 0:
        parts = [(30, signed_mp), (30, conf_mp), (20, (complete * 10000) // published)]
    else:
        adv_mp = 0 if median is None else max(0, 10000 - (int(median) * 10000) // 720)
        parts = [(30, signed_mp), (30, conf_mp), (20, adv_mp),
                 (20, (complete * 10000) // published)]
    score = sum(w * s for w, s in parts) // sum(w for w, _ in parts)
    level = "LOW" if score < 4000 else ("MEDIUM" if score < 7000 else "HIGH")
    return {"level": level, "score_millipoints": score}
