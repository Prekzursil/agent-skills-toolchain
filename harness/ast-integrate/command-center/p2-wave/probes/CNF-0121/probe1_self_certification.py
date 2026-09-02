#!/usr/bin/env python3
"""Probe 1: self-certification fixture must be rejected by the fan-in reducer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fanin import evaluate_condition_9  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0121-reviewer-condition-audit.json"
FIXTURE = HERE / "fixtures" / "self_certification.json"


def main() -> int:
    receipt = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate_condition_9(receipt)
    printable = {
        "probe": "probe1-self-certification",
        "unit_id": "CNF-0121",
        "outcome": result.get("outcome"),
        "classification": result.get("classification"),
        "reviewer_identity": result.get("reviewer_identity"),
        "author_identities": result.get("author_identities"),
        "reducer_anchor": result.get("reducer_anchor"),
        "reason": result.get("reason"),
    }
    print(json.dumps(printable, sort_keys=True))
    if result.get("outcome") != "FAIL":
        print("FAILED:CNF-0121-probe1 self-certification was not rejected")
        return 1
    if result.get("classification") != "self-certification":
        print(f"FAILED:CNF-0121-probe1 classification={result.get('classification')}")
        return 1
    if "impl-agent-omega" not in str(result.get("reviewer_identity") or ""):
        print("FAILED:CNF-0121-probe1 reviewer identity missing")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0121-probe1 audit artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0121-probe1 self-declared {doc.get('state')}")
        return 1
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged: dict = {}
    for bag in (doc.get("negative_controls"), doc.get("controls"), report.get("controls")):
        for item in bag or []:
            if isinstance(item, dict) and item.get("id"):
                merged.setdefault(str(item["id"]), {}).update(item)
    planted = merged.get("self-certification") or {}
    planted_c9 = planted.get("condition_9") or {}
    if planted.get("fired_on_bad_state") is not True:
        print("FAILED:CNF-0121-probe1 artifact did not record detector fire")
        return 1
    if planted_c9.get("outcome") != "FAIL":
        print("FAILED:CNF-0121-probe1 artifact self-cert control did not FAIL")
        return 1
    print("SUCCESS:CNF-0121-probe1 self-certification rejected by shared reducer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
