#!/usr/bin/env python3
"""Vendor/model diversity computed from a roster (not narrated)."""
from __future__ import annotations

from census import norm


def vendor_set(roster: list[dict]) -> list[str]:
    seen, out = set(), []
    for judge in roster:
        v = norm(judge.get("vendor"))
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    out.sort()
    return out


def model_set(roster: list[dict]) -> list[str]:
    seen, out = set(), []
    for judge in roster:
        m = norm(judge.get("model"))
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    out.sort()
    return out


def diversity_report(
    roster: list[dict],
    vendor_minimum: int,
    model_minimum: int = 0,
) -> dict:
    vendors = vendor_set(roster)
    models = model_set(roster)
    vendor_ok = len(vendors) >= int(vendor_minimum)
    model_ok = len(models) >= int(model_minimum) if model_minimum else True
    return {
        "roster_size": len(roster),
        "vendors": vendors,
        "vendor_count": len(vendors),
        "vendor_minimum": int(vendor_minimum),
        "vendor_ok": vendor_ok,
        "models": models,
        "model_count": len(models),
        "model_minimum": int(model_minimum),
        "model_ok": model_ok,
        "ok": vendor_ok and model_ok,
        "computed_not_asserted": True,
    }
