#!/usr/bin/env python3
"""Probe 1: 30-chunk completeness plus planted extent recovery.

Mechanically different field from probe 2 (verdict-stability / kappa).
Validates the catalog output against the physical schema via on-disk $ref
resolution (schema_check.py), not a network fetch of ast-integrate.invalid.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import unshadow as U  # noqa: E402

U.unshadow()

from extent import measure_marked_file, naive_whole_file_bytes  # noqa: E402
from plant_payload import PAYLOAD_BYTES  # noqa: E402
from sample import draw_sample, mutant_sample  # noqa: E402
import schema_check as SC  # noqa: E402
from threshold import EXTENT_TOLERANCE_BYTES, SAMPLE_N, SAMPLE_SEED  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0143-content-redistribution.json"
SENTINEL = (
    "SUCCESS:ADV-0143 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every content class "
    "carries a verdict with a measured extent and a stated residual risk, "
    "the 30-chunk completeness sample found no unclassifiable chunk, and "
    "inter-reviewer agreement met the pre-registered threshold. Any other "
    "terminal state is FAILED:ADV-0143 <classification> with the diagnostic "
    "tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0143-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ADV-0143-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0143" or doc.get("state") != "SUCCESS":
        print("FAILED:ADV-0143-probe1 state", doc.get("state"))
        return 1
    if not SC.garbage_rejected(REPO):
        print("FAILED:ADV-0143-probe1 schema accepted garbage")
        return 1
    errs = SC.error_messages(doc, REPO)
    if errs:
        print("FAILED:ADV-0143-probe1 schema-invalid")
        for line in errs[:20]:
            print(" ", line)
        return 1

    payload = SC.domain(doc)
    rows = payload["content_classes"]
    if len(rows) < 10:
        print("FAILED:ADV-0143-probe1 class rows", len(rows))
        return 1
    for row in rows:
        if row.get("verdict") not in {
            "REDISTRIBUTABLE",
            "SUMMARISE-ONLY",
            "EXCLUDE",
            "NEEDS-OWNER-DECISION",
        }:
            print("FAILED:ADV-0143-probe1 missing verdict", row.get("class_id"))
            return 1
        ext = row.get("extent") or {}
        if not isinstance(ext.get("bytes"), int) or ext["bytes"] < 0:
            print("FAILED:ADV-0143-probe1 extent not measured", row.get("class_id"))
            return 1
        if not row.get("residual_risk"):
            print("FAILED:ADV-0143-probe1 residual missing", row.get("class_id"))
            return 1
        if row.get("not_legal_advice") is not True:
            print("FAILED:ADV-0143-probe1 legal-advice line missing")
            return 1

    completeness = draw_sample(REPO)
    mutant = mutant_sample(REPO)
    if completeness["n"] != SAMPLE_N or completeness["seed"] != SAMPLE_SEED:
        print("FAILED:ADV-0143-probe1 sample control drift")
        return 1
    if completeness["unclassifiable_count"] != 0:
        print(
            "FAILED:ADV-0143-probe1 unclassifiable",
            completeness["unclassifiable"],
        )
        return 1
    if mutant["unclassifiable_count"] <= 0:
        print("FAILED:ADV-0143-probe1 mutant taxonomy classified every chunk")
        return 1
    rec = payload["completeness_sample"]
    if rec.get("unclassifiable_count") != 0:
        print("FAILED:ADV-0143-probe1 artifact completeness not zero")
        return 1

    measured = measure_marked_file(REPO)
    naive = naive_whole_file_bytes(REPO)
    delta = abs(measured["measured_bytes"] - PAYLOAD_BYTES)
    if delta > EXTENT_TOLERANCE_BYTES:
        print(
            "FAILED:ADV-0143-probe1 plant length",
            measured["measured_bytes"],
            "!=",
            PAYLOAD_BYTES,
        )
        return 1
    if abs(naive - PAYLOAD_BYTES) <= EXTENT_TOLERANCE_BYTES:
        print("FAILED:ADV-0143-probe1 naive file-size recovered the plant")
        return 1
    rec_ext = payload["extent_control"]
    if rec_ext.get("measured_bytes") != measured["measured_bytes"]:
        print("FAILED:ADV-0143-probe1 artifact extent mismatch")
        return 1
    if rec_ext.get("known_bytes") != PAYLOAD_BYTES:
        print("FAILED:ADV-0143-probe1 artifact known_bytes mismatch")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-completeness-and-extent",
                "unclassifiable_count": completeness["unclassifiable_count"],
                "population": completeness["population"],
                "mutant_unclassifiable_count": mutant["unclassifiable_count"],
                "measured_bytes": measured["measured_bytes"],
                "known_bytes": PAYLOAD_BYTES,
                "naive_whole_file_bytes": naive,
                "class_rows": len(rows),
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:ADV-0143-probe1 completeness unclassifiable=0 "
        f"plant_bytes={measured['measured_bytes']} "
        f"mutant_unclassifiable={mutant['unclassifiable_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
