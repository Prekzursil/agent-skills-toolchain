#!/usr/bin/env python3
"""Probe 1: planted collusion SAME-TUPLE fires; a label-only checker is silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import attestation as A  # noqa: E402
import schema_offline as S  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0136-independence-attestation.json"
SENTINEL_HEAD = "SUCCESS:ADV-0136 emitted only when the artifact at output_path exists"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0136-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    payload = A.ledger_payload(doc)
    if doc.get("unit_id") != "ADV-0136":
        print("FAILED:ADV-0136-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL_HEAD not in text or "SUCCESS:ADV-0136" not in text:
        print("FAILED:ADV-0136-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0136-probe1 self-declared", doc.get("state"))
        return 1
    if payload.get("response_side_is_source_of_truth") is not True:
        print("FAILED:ADV-0136-probe1 request-side ledger")
        return 1
    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:ADV-0136-probe1 schema")
        for err in errs[:8]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not S.iter_errors(garbage):
            print("FAILED:ADV-0136-probe1 schema vacuous")
            return 1

    A.write_runtime_logs(REPO)
    events = A.load_jsonl(A.LOGS / "planted-collusion.jsonl")
    result = A.classify_runtime(events)
    same = result["violations"]["SAME-TUPLE"]
    naive = A.naive_same_tuple_by_label(events)
    print(
        "planted_collusion SAME-TUPLE "
        f"fired={bool(same)} n={len(same)} seats={same[0].get('seats') if same else None}"
    )
    print(f"label_only_checker fired={bool(naive)} n={len(naive)}")
    if not same:
        print("FAILED:ADV-0136-probe1 SAME-TUPLE did not fire on planted collusion")
        return 1
    seats = set(same[0].get("seats") or [])
    if seats != {"seat-critic", "seat-advocate"}:
        print("FAILED:ADV-0136-probe1 unexpected seats", seats)
        return 1
    if naive:
        print("FAILED:ADV-0136-probe1 label-only checker fired; it must be silent")
        return 1

    good = A.classify_runtime(A.load_jsonl(A.LOGS / "known-good.jsonl"))["violations"]
    good_same = bool(good["SAME-TUPLE"])
    print(f"known_good SAME-TUPLE fired={good_same} silent={not good_same}")
    if good_same:
        print("FAILED:ADV-0136-probe1 known-good SAME-TUPLE false positive")
        return 1

    planted = payload.get("planted_controls") or []
    if len(planted) != 3 or not all(p.get("fired") is True for p in planted):
        print("FAILED:ADV-0136-probe1 artifact planted_controls incomplete")
        return 1
    print("SUCCESS:ADV-0136-probe1 planted collusion SAME-TUPLE; label-only silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
