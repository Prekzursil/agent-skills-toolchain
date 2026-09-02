#!/usr/bin/env python3
"""Probe 1: mechanical token rules + known-present MECH- prefix (no adjudication)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import resolver as R  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0190.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:CNF-0190-probe1 artifact missing or undersized")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:CNF-0190" not in blob:
        print("FAILED:CNF-0190-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "CNF-0190":
        print("FAILED:CNF-0190-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0190-probe1 self-declared", doc.get("state"))
        return 1

    estate = C.materialize()
    hits = R.scan_tree(estate)
    resolved = [h for h in hits if h["classification"] == R.CLASS_RESOLVED]
    mech = [h for h in resolved if h["id"].startswith("MECH-")]
    if not mech:
        print("FAILED:CNF-0190-probe1 no MECH- hits")
        return 1
    if any(h.get("adjudicated") for h in mech):
        print("FAILED:CNF-0190-probe1 MECH- required adjudication")
        return 1
    if any(h.get("namespace") != R.NS_MECH for h in mech):
        print("FAILED:CNF-0190-probe1 MECH- resolved to a non-mechanism namespace")
        return 1
    if any(h.get("confidence") != "token-rule" for h in resolved):
        print("FAILED:CNF-0190-probe1 resolved hit not from a token rule")
        return 1

    bare_m_in_arch = [
        h
        for h in hits
        if h["id"].startswith("M-") and "13-architecture" in h["artifact"].lower()
    ]
    if bare_m_in_arch:
        print("FAILED:CNF-0190-probe1 bare M-NN inside architecture file", bare_m_in_arch[:3])
        return 1

    planted = [
        h
        for h in hits
        if h["id"] == "M-16"
        and "ambiguous" in h["artifact"].lower()
        and h["classification"] == R.CLASS_UNRESOLVED
    ]
    if not planted:
        print("FAILED:CNF-0190-probe1 planted ambiguous M-16 was not UNRESOLVED")
        return 1

    sample = [h for h in doc.get("reviewer", {}).get("sample", {}).get("rows", [])]
    if len(sample) < 20:
        print(f"FAILED:CNF-0190-probe1 reviewer sample {len(sample)} < 20")
        return 1
    if not all(r.get("agree") for r in sample):
        print("FAILED:CNF-0190-probe1 reviewer disagreement")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-token-rules",
                "unit_id": "CNF-0190",
                "mech_resolved": len(mech),
                "mech_adjudicated": 0,
                "resolved": len(resolved),
                "planted_unresolved": len(planted),
                "reviewer_sample": len(sample),
                "pass": True,
            }
        )
    )
    print("SUCCESS:CNF-0190-probe1 mechanical token rules and known-present MECH-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
