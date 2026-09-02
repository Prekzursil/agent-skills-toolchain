#!/usr/bin/env python3
"""Probe 1: reviewer vendor differs from every author vendor per lens.

Live artifact must cover every SYN-0026 dependency. Same-vendor assignment
is rejected. Reviewers who authored a synthesis candidate are disqualified.
Roster intersection must be empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import protocol as P  # noqa: E402

ART = REPO / P.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0026-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail(f"artifact missing {P.OUT_REL}")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = P.domain(doc)
    if doc.get("unit_id") != P.UNIT_ID:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or payload.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"state={doc.get('state')}")
    kind = (doc.get("report") or {}).get("kind") if isinstance(doc.get("report"), dict) else None
    if kind not in (None, "meta-review-finding"):
        return fail(f"report.kind={kind}")

    units = P.index_units()
    expected = P.lens_ids_for_unit(units)
    rows = [r for r in (payload.get("lenses") or []) if isinstance(r, dict)]
    got = [r.get("lens_id") for r in rows]
    if got != expected:
        return fail(f"lens set {got} != deps {expected}")

    try:
        P.assert_vendor_differs(rows)
    except P.SameVendorReviewError as exc:
        return fail(str(exc))

    for row in rows:
        second = row.get("second_vendor_verdict") or {}
        if not second.get("label"):
            return fail(f"{row.get('lens_id')} missing second-vendor verdict")
        if not second.get("vendor"):
            return fail(f"{row.get('lens_id')} second-vendor vendor blank")

    author_ids = {
        a.get("id") for a in (payload.get("author_roster") or []) if a.get("id")
    }
    try:
        P.assign_reviewer("anthropic", "anthropic", "probe1-same-vendor", author_ids)
        return fail("same-vendor assign was accepted")
    except P.SameVendorReviewError:
        pass
    try:
        P.assign_reviewer("openai", "openai", "probe1-same-openai", author_ids)
        return fail("openai same-vendor assign was accepted")
    except P.SameVendorReviewError:
        pass

    ok_v = P.assign_reviewer(
        "anthropic", "openai", "SYN-0026-second-openai-SYN-0014", author_ids
    )
    if ok_v != "openai":
        return fail(f"cross-vendor assign returned {ok_v}")

    if "SYN-0008" in author_ids:
        try:
            P.assign_reviewer("openai", "anthropic", "SYN-0008", author_ids)
            return fail("SYN-0008 author was accepted as reviewer")
        except P.ReviewerAuthoredError:
            pass

    inter = payload.get("roster_intersection")
    if inter not in ([], None) and inter:
        return fail(f"roster_intersection={inter}")

    payload = {
        "probe": "probe1-vendor-differs",
        "unit_id": P.UNIT_ID,
        "lenses": [
            {
                "lens_id": r["lens_id"],
                "author_vendor": r["author_vendor"],
                "reviewer_vendor": r["reviewer_vendor"],
            }
            for r in rows
        ],
        "roster_intersection": inter or [],
        "same_vendor_rejected": True,
        "author_reviewer_rejected": "SYN-0008" in author_ids,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:SYN-0026-probe1 reviewer vendor differs from every author vendor per lens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
