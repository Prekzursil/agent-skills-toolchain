#!/usr/bin/env python3
"""Probe 1: blinding of re-grader input + planted under-grade catch."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / "command-center" / "receipts" / "CNF-0142.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0142-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if doc.get("unit_id") != "CNF-0142":
        return fail(f"unit_id {doc.get('unit_id')!r}")
    if "SUCCESS:CNF-0142" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    bundle = E.run_bundle()
    claims = bundle["claims"]
    clauses = bundle["clauses"]
    controls = bundle["controls"]
    planted_id = str(controls["planted_under_grade_id"])

    payloads = [E.blind_payload(c) for c in claims]
    for p in payloads:
        leaked = E.FORBIDDEN.intersection(p)
        if leaked:
            return fail(f"payload leaked {sorted(leaked)}")
        blob = E.dumps(p)
        if "author_severity" in blob or '"severity"' in blob:
            return fail("payload text contains severity field")

    smuggled = dict(payloads[0])
    smuggled["author_severity"] = "P3"
    try:
        E.grade_payload(smuggled, clauses)
        return fail("grader accepted a labelled payload")
    except E.BlindError:
        pass

    planted_claim = next(c for c in claims if c["id"] == planted_id)
    if planted_claim["author_severity"] in E.CENSUS:
        return fail("plant is already author-P0/P1; control is vacuous")
    g = E.grade_payload(E.blind_payload(planted_claim), clauses)
    if g["independent_severity"] != "P0":
        return fail(
            f"plant {planted_id} independent={g['independent_severity']} want=P0"
        )
    if g["rubric_clause"] != "S-P0-DATA-LOSS":
        return fail(f"plant clause {g['rubric_clause']}")

    row = bundle["planted_row"]
    if row["direction"] != "under-grade":
        return fail(f"plant direction {row['direction']}")
    if planted_id not in bundle["matrix"]["under_grade"]["ids"]:
        return fail("plant missing from under_grade bucket")

    live_hash = bundle["attestation"]
    art_hash = doc.get("blinding_attestation_hash") or doc.get("blinding_attestation")
    if art_hash != live_hash:
        return fail("blinding attestation mismatch")

    print(
        json.dumps(
            {
                "probe": "probe1-blind-and-plant",
                "unit_id": "CNF-0142",
                "payloads": len(payloads),
                "forbidden_keys_absent": True,
                "grader_rejects_labelled_payload": True,
                "planted_id": planted_id,
                "planted_author": planted_claim["author_severity"],
                "planted_independent": g["independent_severity"],
                "planted_clause": g["rubric_clause"],
                "planted_caught": True,
                "attestation": live_hash,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"blind_payloads={len(payloads)} plant={planted_id} "
        f"author={planted_claim['author_severity']} independent=P0 caught=True"
    )
    print("SUCCESS:CNF-0142-probe1 blind re-grade and planted under-grade catch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
