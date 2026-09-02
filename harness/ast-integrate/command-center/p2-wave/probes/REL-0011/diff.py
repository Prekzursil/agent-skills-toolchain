#!/usr/bin/env python3
"""Bidirectional set-diff between a CycloneDX bill and an independent closure.

The bill is a claim. This module is the gate. It does not generate either set.
"""
from __future__ import annotations

from typing import Iterable


def as_purl_set(items: Iterable) -> set[str]:
    out: set[str] = set()
    for item in items:
        if isinstance(item, str) and item:
            out.add(item)
        elif isinstance(item, dict):
            purl = item.get("purl")
            if purl:
                out.add(str(purl))
    return out


def bidirectional(bill, closure) -> dict:
    bill_set = as_purl_set(bill)
    closure_set = as_purl_set(closure)
    cmb = sorted(closure_set - bill_set)
    bms = sorted(bill_set - closure_set)
    return {
        "closure_minus_bill": cmb,
        "bill_minus_shipped": bms,
        "counts": {
            "closure_minus_bill": len(cmb),
            "bill_minus_shipped": len(bms),
            "bill": len(bill_set),
            "closure": len(closure_set),
        },
        "bill": sorted(bill_set),
        "closure": sorted(closure_set),
    }
