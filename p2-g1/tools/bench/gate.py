"""Three-outcome evaluation gate: KEEP / REVERT / INSUFFICIENT-EVIDENCE."""
from __future__ import annotations

from typing import Any, Mapping


def decide(paired: Mapping[str, Any], margins: Mapping[str, Any]) -> dict[str, Any]:
    n = int(paired.get("n") or 0)
    primary = margins.get("primary") if isinstance(margins.get("primary"), dict) else {}
    secondary = margins.get("secondary") if isinstance(margins.get("secondary"), dict) else {}
    need_n = int(primary.get("pre_registered_n") or 24)
    min_effect = float(primary.get("min_effect") or 0.05)
    sec_floor = float(secondary.get("min_effect") or -0.05)
    interval = paired.get("interval") if isinstance(paired.get("interval"), dict) else None
    if n < need_n:
        return {
            "outcome": "INSUFFICIENT-EVIDENCE",
            "reason_id": "underpowered",
            "n": n,
            "cited_interval": None,
            "interval": interval,
            "change_id": paired.get("change_id"),
        }
    if interval is None:
        return {
            "outcome": "INSUFFICIENT-EVIDENCE",
            "reason_id": "bare-point-estimate",
            "n": n,
            "cited_interval": None,
            "interval": None,
            "change_id": paired.get("change_id"),
        }
    lo = float(interval.get("lo") or 0.0)
    hi = float(interval.get("hi") or 0.0)
    mean = float(interval.get("mean") or paired.get("point_estimate") or 0.0)
    cited = f"lo={lo:.4f} hi={hi:.4f} n={n}"
    sec = paired.get("secondary") if isinstance(paired.get("secondary"), dict) else {}
    sec_mean = float(sec.get("mean") or 0.0)
    if sec_mean < sec_floor:
        return {
            "outcome": "REVERT",
            "reason_id": "material-regression",
            "n": n,
            "cited_interval": cited,
            "interval": dict(interval),
            "change_id": paired.get("change_id"),
        }
    if lo >= min_effect:
        return {
            "outcome": "KEEP",
            "reason_id": "pre-registered-margin",
            "n": n,
            "cited_interval": cited,
            "interval": dict(interval),
            "change_id": paired.get("change_id"),
        }
    if hi <= 0.0 or abs(mean) < min_effect:
        return {
            "outcome": "REVERT",
            "reason_id": "neutral-or-unproven",
            "n": n,
            "cited_interval": cited,
            "interval": dict(interval),
            "change_id": paired.get("change_id"),
        }
    return {
        "outcome": "REVERT",
        "reason_id": "neutral-or-unproven",
        "n": n,
        "cited_interval": cited,
        "interval": dict(interval),
        "change_id": paired.get("change_id"),
    }
