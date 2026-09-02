#!/usr/bin/env python3
"""Probe 1: adapter extraction + lineage rehash (independent of the checker)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402

NEEDLE = {
    "ietf": "absolute requirement of the specification",
    "w3c": None,  # any extracted MUST
    "slsa": "MUST generate provenance",
    "mcp": "initialization phase MUST be the first interaction",
}


def main() -> int:
    lineage = A.verify_lineage()
    mismatches = [r for r in lineage if not r["match"] or not r["present"]]
    extracted = A.extract_all()
    pinned = A.canonical_requirements(extracted)
    classes = sorted(extracted)
    counts = {c: len(extracted[c]) for c in classes}
    missing_class = [c for c in ("ietf", "w3c", "slsa", "mcp") if counts.get(c, 0) < 1]
    pin_ids = {p["id"] for p in pinned}
    required_pins = {
        "ietf.rfc2119.must-absolute",
        "ietf.rfc8174.uppercase-only",
        "mcp.lifecycle.initialization-first",
        "mcp.basic.id-must-not-null",
        "slsa.v1.0.provenance-authentic",
    }
    missing_pins = sorted(required_pins - pin_ids)
    discussion_ok = True
    for row in pinned:
        hist = row.get("discussion_history") or {}
        if not hist:
            discussion_ok = False
            break
    report = {
        "probe": "probe1-adapter-lineage",
        "unit_id": "RES-0139",
        "snapshots_checked": len(lineage),
        "lineage_mismatches": mismatches,
        "extracted_counts": counts,
        "pinned_ids": sorted(pin_ids),
        "missing_class": missing_class,
        "missing_pins": missing_pins,
        "discussion_history_present": discussion_ok,
        "independent_signals": [
            "sha256-rehash-of-frozen-snapshots-versus-fetch-manifest",
            "rfc2119-keyword-extraction-from-snapshot-bytes",
        ],
    }
    print(json.dumps(report, indent=2))
    ok = (
        not mismatches
        and not missing_class
        and not missing_pins
        and discussion_ok
        and len(lineage) >= 8
    )
    if not ok:
        print("FAILED:RES-0139-probe1 adapter lineage or extraction")
        return 1
    print("SUCCESS:RES-0139-probe1 adapter extraction and lineage rehash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
