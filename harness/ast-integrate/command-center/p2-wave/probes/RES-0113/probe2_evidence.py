#!/usr/bin/env python3
"""Probe 2: independent evidence refuter (default REFUTED / fail).

Promoted mechanisms need DOI, section, effect size AND baseline.
E3 cannot promote. Rejected ACH must carry effect size AND baseline.
Both-states: planting an E3-promoted headline-without-baseline must fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402

ART = C.ART


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0113-probe2 artifact missing")
        return 1
    doc = C.load_art()
    if str(doc.get("state") or "").upper() in C.NOT_DELIVERING:
        print(f"FAILED:RES-0113-probe2 self-declared {doc.get('state')}")
        return 1
    err = C.both_states_evidence(doc)
    promoted = [
        m.get("id")
        for m in (doc.get("mechanisms") or [])
        if isinstance(m, dict) and m.get("promoted") is True
    ]
    print(
        json.dumps(
            {
                "probe": "probe2-evidence",
                "unit_id": "RES-0113",
                "both_states": err is None,
                "error": err,
                "promoted_ids": promoted,
                "promoted_count": len(promoted),
                "defaults_to_refuted": True,
            },
            sort_keys=True,
        )
    )
    if err:
        print(f"FAILED:RES-0113-probe2 {err}")
        return 1
    print("SUCCESS:RES-0113-probe2 evidence-quality refuter and E3-promote control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
