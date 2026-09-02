#!/usr/bin/env python3
"""Probe 1: span containment. Resolves each citation to a body and searches
for supporting text. Mechanically different from probe 2 (no bibliographic lookup).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detect import run_detector  # noqa: E402

UNIT = "ADV-0080"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    doc = run_detector()
    rows = {r["id"]: r for r in doc["rows"]}
    genuine = rows.get("plant-genuine-local")
    if not genuine or not genuine["span"].get("supports"):
        return fail("genuine control span did not MATCH")
    if genuine["fabricated"]:
        return fail("genuine control flagged fabricated")

    must_miss_span = [
        "plant-url-wrong-claim",
        "plant-real-doi-wrong-page",
        "plant-nonexistent-doi",
    ]
    for pid in must_miss_span:
        row = rows.get(pid)
        if row is None:
            return fail(f"missing planted pair {pid}")
        if row["span"].get("supports"):
            return fail(f"{pid} span falsely MATCHED")
        if not row["fabricated"]:
            return fail(f"{pid} not classified fabricated")

    identity = rows.get("plant-doi-identity-mismatch")
    if identity is None or not identity["fabricated"]:
        return fail("doi-identity-mismatch not fabricated")

    if doc["planted_recall"] != 1.0 or not doc["all_planted_detected"]:
        return fail(
            f"planted recall {doc['planted_recall']} missed={doc['missed_ids']}"
        )
    if doc["n_false_positives"] != 0:
        return fail(f"false positives {doc['false_positive_ids']}")

    out = {
        "probe": "probe1-span-containment",
        "unit_id": UNIT,
        "pass": True,
        "both_states": True,
        "genuine_span_status": genuine["span"]["status"],
        "genuine_matched_span": genuine["span"].get("matched_span"),
        "planted_recall": doc["planted_recall"],
        "n_detected": doc["n_detected"],
        "n_planted_fabricated": doc["n_planted_fabricated"],
        "n_corpus": doc["n_corpus"],
        "n_corpus_supported": doc["n_corpus_supported"],
        "method": "body-span-and-token-coverage",
        "does_not_consult_metadata_catalog": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"span genuine={genuine['span']['status']} "
        f"recall={doc['planted_recall']} corpus_supported={doc['n_corpus_supported']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 span containment; planted fabrications NOT-FOUND")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
