#!/usr/bin/env python3
"""Probe 2: freeze timestamp predates receipts; expansion is bounded.

Different field than probe 1 (rate comparison). This probe reads corpus
timestamps, the one-shot/cross-class bound, BLOCKED denominator control,
and schema discrimination.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import escalate as E  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0004-escalation-policy.json"
SCHEMA = REPO / "command-center/schema/confirmation-policy.schema.json"
SENTINEL_HEAD = "SUCCESS:CNF-0004 emitted only when the artifact at output_path exists"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0004-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL_HEAD not in text:
        return fail("sentinel-absent")

    committed = str(doc.get("committed_at") or "")
    live = C.predates(committed, C.scan(REPO))
    print(
        json.dumps(
            {
                "committed_at": committed,
                "receipt_count": live["confirmation_receipt_count"],
                "predates": live["threshold_predates_every_receipt"],
                "why": live["why"],
            },
            sort_keys=True,
        )
    )
    if not live["threshold_predates_every_receipt"]:
        return fail(f"timestamp {live['why']}")
    art_proof = doc.get("timestamp_proof") or {}
    if art_proof.get("threshold_predates_every_receipt") is not True:
        return fail("artifact timestamp_proof false")
    art_count = art_proof.get("confirmation_receipt_count")
    if art_count is None or int(art_count) != live["confirmation_receipt_count"]:
        return fail("artifact receipt count != live scan")

    cascade = E.cascade_control()
    blocked = E.blocked_flips_decision()
    print(
        json.dumps(
            {
                "cascade_bounded": cascade["bounded"],
                "a_fired": cascade["a_fired"],
                "a_requeue_second": cascade["a_requeue_second"],
                "b_requeued": cascade["b_requeued"],
                "blocked_flipped": blocked["decision_flipped"],
            },
            sort_keys=True,
        )
    )
    if not cascade["bounded"]:
        return fail("cascade not bounded")
    if cascade["a_requeue_second"] or cascade["b_requeued"] or cascade["a_leaked_b_ids"]:
        return fail("cross-class or second-fire enqueue")
    if not blocked["decision_flipped"]:
        return fail("BLOCKED exclusion inert")
    bound = doc.get("expansion_bound") or {}
    if bound.get("bounded") is not True or bound.get("cascade_without_limit") is not False:
        return fail("artifact expansion_bound")
    if (doc.get("answer") or {}).get("cascade_without_limit") is not False:
        return fail("answer claims unbounded cascade")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            return fail("schema accepted garbage")

    print(
        f"predates={live['threshold_predates_every_receipt']} "
        f"receipts={live['confirmation_receipt_count']} "
        f"bounded={cascade['bounded']} blocked_flip={blocked['decision_flipped']}"
    )
    print("SUCCESS:CNF-0004-probe2 bound and timestamp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
