"""Capability negotiation and loud downgrade refusal.

A unit declaring min_tier=GUARANTEED that needs a capability the vendor
lacks MUST terminate as FAILED:<id> DOWNGRADE-REFUSED ... and never as
DEGRADED or SUCCESS.
"""
from __future__ import annotations

from typing import Any

from contract import CAPABILITY_TIERS, VENDORS

ALLOWED = "ALLOWED"
REFUSED = "REFUSED"
INVALID = "INVALID-ADAPTER"
DEGRADED = "DEGRADED"


def validate_adapter(vendor_id: str, adapter: dict[str, Any] | None = None) -> dict[str, Any]:
    ad = adapter if adapter is not None else VENDORS.get(vendor_id)
    if not ad:
        return {
            "status": INVALID,
            "reason": f"unknown-vendor:{vendor_id}",
            "marker": f"FAILED:adapter INVALID-ADAPTER unknown-vendor:{vendor_id}",
        }
    leaks = ad.get("leaks") or []
    if not leaks:
        return {
            "status": INVALID,
            "reason": "empty-leak-declaration",
            "marker": (
                f"FAILED:adapter INVALID-ADAPTER empty-leak-declaration "
                f"vendor={vendor_id} (no two vendors are identical)"
            ),
        }
    caps = ad.get("capabilities") or {}
    missing_keys = [k for k in CAPABILITY_TIERS if k not in caps]
    extra = [k for k in caps if k not in CAPABILITY_TIERS]
    if missing_keys or extra:
        return {
            "status": INVALID,
            "reason": f"capability-map-mismatch missing={missing_keys} extra={extra}",
            "marker": f"FAILED:adapter INVALID-ADAPTER capability-map-mismatch vendor={vendor_id}",
        }
    return {"status": "VALID", "reason": "ok", "marker": f"VALID:adapter vendor={vendor_id}"}


def negotiate(unit: dict[str, Any], vendor_id: str) -> dict[str, Any]:
    """Return a terminal negotiation record. Never silent."""
    vcheck = validate_adapter(vendor_id)
    if vcheck["status"] != "VALID":
        return {
            "status": INVALID,
            "vendor": vendor_id,
            "unit_id": unit.get("id"),
            "min_tier": unit.get("min_tier"),
            "missing": [],
            "leaks": [],
            "reason": vcheck["reason"],
            "marker": vcheck["marker"],
        }
    adapter = VENDORS[vendor_id]
    min_tier = str(unit.get("min_tier") or "").upper()
    uid = str(unit.get("id") or "UNKNOWN")
    if min_tier not in {"GUARANTEED", "BEST-EFFORT", "VENDOR-ONLY"}:
        return {
            "status": REFUSED,
            "vendor": vendor_id,
            "unit_id": uid,
            "min_tier": min_tier,
            "missing": [],
            "leaks": [],
            "reason": "min_tier-absent-or-invalid",
            "marker": f"FAILED:{uid} DOWNGRADE-REFUSED min_tier-absent-or-invalid vendor={vendor_id}",
        }
    needs = list(unit.get("capability_needs") or [])
    unknown = [c for c in needs if c not in CAPABILITY_TIERS]
    if unknown:
        return {
            "status": REFUSED,
            "vendor": vendor_id,
            "unit_id": uid,
            "min_tier": min_tier,
            "missing": unknown,
            "leaks": [],
            "reason": f"unknown-capability:{unknown}",
            "marker": f"FAILED:{uid} DOWNGRADE-REFUSED unknown-capability={unknown[0]} vendor={vendor_id}",
        }
    caps = adapter["capabilities"]
    missing = [c for c in needs if not caps.get(c)]
    leaks = list(adapter["leaks"])
    if not missing:
        return {
            "status": ALLOWED,
            "vendor": vendor_id,
            "unit_id": uid,
            "min_tier": min_tier,
            "missing": [],
            "leaks": leaks,
            "reason": "capabilities-satisfied",
            "marker": f"NEGOTIATED:{uid} vendor={vendor_id} missing=0 leaks={len(leaks)}",
        }
    # GUARANTEED: any missing capability is a loud refusal. Never DEGRADED.
    if min_tier == "GUARANTEED":
        cap = missing[0]
        return {
            "status": REFUSED,
            "vendor": vendor_id,
            "unit_id": uid,
            "min_tier": min_tier,
            "missing": missing,
            "leaks": leaks,
            "reason": f"DOWNGRADE-REFUSED capability={cap}",
            "marker": (
                f"FAILED:{uid} DOWNGRADE-REFUSED capability={cap} "
                f"vendor={vendor_id} min_tier=GUARANTEED"
            ),
        }
    # VENDOR-ONLY unit still cannot run without the named vendor capability.
    vendor_missing = [c for c in missing if CAPABILITY_TIERS[c] == "VENDOR-ONLY"]
    if vendor_missing:
        cap = vendor_missing[0]
        return {
            "status": REFUSED,
            "vendor": vendor_id,
            "unit_id": uid,
            "min_tier": min_tier,
            "missing": missing,
            "leaks": leaks,
            "reason": f"DOWNGRADE-REFUSED capability={cap}",
            "marker": (
                f"FAILED:{uid} DOWNGRADE-REFUSED capability={cap} "
                f"vendor={vendor_id} min_tier={min_tier}"
            ),
        }
    # BEST-EFFORT may continue only for missing BEST-EFFORT caps, with leaks.
    return {
        "status": DEGRADED,
        "vendor": vendor_id,
        "unit_id": uid,
        "min_tier": min_tier,
        "missing": missing,
        "leaks": leaks
        + [
            {
                "id": "A6-LEAK-DEGRADED",
                "surface": missing[0],
                "text": f"BEST-EFFORT unit ran without {missing}",
                "citation": "command-center/p2-wave/probes/ARC-0038/negotiate.py",
            }
        ],
        "reason": f"degraded-missing={missing}",
        "marker": f"DEGRADED:{uid} vendor={vendor_id} missing={missing[0]}",
    }


def silent_shim(unit: dict[str, Any], vendor_id: str) -> dict[str, Any]:
    """Negative control: pretends missing GUARANTEED caps still succeed.

    The probe must reject this behaviour. Not used on the live dispatch path.
    """
    honest = negotiate(unit, vendor_id)
    if honest["status"] == REFUSED and unit.get("min_tier") == "GUARANTEED":
        fake = dict(honest)
        fake["status"] = DEGRADED
        fake["reason"] = "silent-downgrade"
        fake["marker"] = f"SUCCESS:{unit.get('id')} (shim hid {honest.get('missing')})"
        return fake
    return honest
