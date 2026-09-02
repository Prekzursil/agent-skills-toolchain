#!/usr/bin/env python3
"""Probe 1: claim-record schema, status transitions, decision-to-registry coverage.

Instrument: emit the fixture council into an isolated registry, then measure
coverage from the written bytes (not from the emitter's return dict). A planted
influential claim that is dropped before write must show up in
unregistered_influential. A genuine non-influential claim must not be required.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.artifacts.claims import (  # noqa: E402
    REQUIRED_FIELDS,
    TRANSITIONS,
    VERIFICATION_STATUSES,
    coverage_report,
    emit,
    extract_claims,
    load_registry,
    transition,
    validate_record,
)

COUNCIL = HERE / "fixtures" / "council.json"
PLANTED = "CCL-planted-repeat"
NOVEL = "CCL-color-of-bikeshed"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0259-probe1 {msg}")
    return 1


def main() -> int:
    council = json.loads(COUNCIL.read_text(encoding="utf-8"))
    extracted = extract_claims(council)
    ids = {c["id"] for c in extracted}
    if PLANTED not in ids:
        return fail(f"extractor missed planted claim {PLANTED}")
    if NOVEL not in ids:
        return fail(f"extractor missed non-influential claim {NOVEL}")

    schema_ok = []
    for rec in extracted:
        errs = validate_record(rec, root=REPO)
        schema_ok.append({"id": rec["id"], "errors": errs})
        missing = [f for f in REQUIRED_FIELDS if f not in rec]
        if missing:
            return fail(f"schema missing fields {missing} on {rec['id']}")

    verified = [c for c in extracted if c["verification_status"] == "VERIFIED"]
    for rec in verified:
        errs = validate_record(rec, root=REPO)
        if errs:
            return fail(f"fixture VERIFIED invalid {rec['id']}: {errs}")

    # Status transitions: legal path UNVERIFIED -> INFERRED -> VERIFIED on an
    # anchored record; illegal VERIFIED from REJECTED; VERIFIED refused with
    # no anchors.
    sample = next(c for c in extracted if c["id"] == PLANTED)
    parked = dict(sample)
    parked["verification_status"] = "UNVERIFIED"
    inferred = transition(parked, "INFERRED", root=REPO)
    if inferred["verification_status"] != "INFERRED":
        return fail("UNVERIFIED -> INFERRED did not stick")
    verified_again = transition(inferred, "VERIFIED", root=REPO)
    if verified_again["verification_status"] != "VERIFIED":
        return fail("INFERRED -> VERIFIED did not stick")
    rejected = transition(verified_again, "REJECTED", root=REPO)
    illegal = None
    try:
        transition(rejected, "VERIFIED", root=REPO)
    except ValueError as exc:
        illegal = str(exc)
    if not illegal or "illegal transition" not in illegal:
        return fail(f"REJECTED -> VERIFIED must be refused, got {illegal!r}")

    unanchored = dict(sample)
    unanchored["verification_status"] = "UNVERIFIED"
    unanchored["evidence_anchors"] = []
    refused = None
    try:
        transition(unanchored, "VERIFIED", root=REPO)
    except ValueError as exc:
        refused = str(exc)
    if not refused or "cannot enter VERIFIED" not in refused:
        return fail(f"unanchored VERIFIED transition must refuse, got {refused!r}")

    with tempfile.TemporaryDirectory(prefix="imp0259-p1-") as tmp:
        registry_path = Path(tmp) / "CLAIM-REGISTRY.json"
        result = emit(council, registry_path=registry_path, root=REPO)
        live = load_registry(registry_path)
        report = coverage_report(council, live)
        live_ids = {str(c.get("id")) for c in live.get("claims") or []}

    if PLANTED not in live_ids:
        return fail("planted influential claim not in written registry")
    if report["unregistered_influential"]:
        return fail(
            "unregistered influential "
            + json.dumps(report["unregistered_influential"])
        )
    if report["coverage_ratio"] != 1.0:
        return fail(f"coverage_ratio={report['coverage_ratio']} want=1.0")
    if NOVEL in report["unregistered_influential"]:
        return fail("non-influential claim treated as required coverage miss")
    if NOVEL not in report["non_influential_ids"]:
        return fail("novel/non-influential claim not classified as such")
    # False-positive rate of the coverage checker on this fixture: requiring
    # the bikeshed claim would be 1/1; not requiring it is 0.
    false_positive_rate = 0.0 if NOVEL not in report["unregistered_influential"] else 1.0
    if false_positive_rate != 0.0:
        return fail("coverage checker false-positive on novel claim")

    payload = {
        "probe": "probe1-schema-coverage",
        "unit_id": "IMP-0259",
        "pass": True,
        "extracted": sorted(ids),
        "schema_rows": schema_ok,
        "statuses": list(VERIFICATION_STATUSES),
        "transition_count": sum(len(v) for v in TRANSITIONS.values()),
        "illegal_rejected_to_verified": illegal,
        "unanchored_verified_refused": refused,
        "coverage": report,
        "emit_registry_size": result["coverage"]["registry_size"],
        "false_positive_rate_on_novel": false_positive_rate,
        "planted_repeated_question_retrieved": PLANTED in live_ids,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        "coverage "
        f"{report['registered_influential_count']}/{report['influential_count']} "
        f"unregistered={report['unregistered_influential']} "
        f"novel={report['non_influential_ids']}"
    )
    print("SUCCESS:IMP-0259-probe1 schema transitions coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
