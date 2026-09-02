#!/usr/bin/env python3
"""Probe 2: re-derive violations from raw JSONL; DRIVER-CONFOUND and DECLARED-ONLY fire."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import attestation as A  # noqa: E402
import rederive as R  # noqa: E402
import schema_offline as S  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0136-independence-attestation.json"


def main() -> int:
    A.write_runtime_logs(REPO)
    log_paths = [A.LOGS / f"{name}.jsonl" for name in A.COUNCILS]
    derived = R.rederive_from_logs(log_paths)
    fp_logs = A.violation_fingerprint(derived)
    print("reviewer_from_logs " + json.dumps(fp_logs, default=str))

    if not ART.is_file():
        print("FAILED:ADV-0136-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = A.ledger_payload(doc)
    fp_ledger = A.violation_fingerprint(payload.get("runtime_violations") or {})
    if fp_logs != fp_ledger:
        print("FAILED:ADV-0136-probe2 reviewer/ledger mismatch")
        print(json.dumps({"logs": fp_logs, "ledger": fp_ledger}, indent=2, default=str)[:4000])
        return 1

    confound_logs = A.load_jsonl(A.LOGS / "planted-driver-confound.jsonl")
    confound = A.classify_runtime(confound_logs)["violations"]
    print(
        "planted_driver_confound DRIVER-CONFOUND "
        f"fired={bool(confound['DRIVER-CONFOUND'])} "
        f"drivers={confound['DRIVER-CONFOUND'][0].get('drivers') if confound['DRIVER-CONFOUND'] else None}"
    )
    if not confound["DRIVER-CONFOUND"]:
        print("FAILED:ADV-0136-probe2 DRIVER-CONFOUND did not fire")
        return 1
    drivers = set(confound["DRIVER-CONFOUND"][0].get("drivers") or [])
    if drivers != {"claude-sonnet-4", "claude-opus-4"}:
        print("FAILED:ADV-0136-probe2 unexpected drivers", drivers)
        return 1
    if confound["SAME-TUPLE"]:
        print("FAILED:ADV-0136-probe2 confound fixture should not be SAME-TUPLE")
        return 1

    stripped_logs = A.load_jsonl(A.LOGS / "planted-declared-only.jsonl")
    stripped = A.classify_runtime(stripped_logs)["violations"]
    do = stripped["DECLARED-ONLY"]
    print(
        "adverse_inference DECLARED-ONLY "
        f"fired={bool(do)} seats={[r.get('seat_id') for r in do]}"
    )
    if not do:
        print("FAILED:ADV-0136-probe2 stripped seat silently passed")
        return 1
    if {r.get("seat_id") for r in do} != {"seat-openai-stripped"}:
        print("FAILED:ADV-0136-probe2 DECLARED-ONLY seats", do)
        return 1
    complete = [
        s
        for s in A.classify_runtime(stripped_logs)["seats"]
        if s.get("seat_id") == "seat-anthropic-complete"
    ]
    if not complete or complete[0].get("coverage") != "RESPONSE-ATTESTED":
        print("FAILED:ADV-0136-probe2 complete cross-vendor seat not attested")
        return 1

    good = A.classify_runtime(A.load_jsonl(A.LOGS / "known-good.jsonl"))["violations"]
    if any(good[k] for k in ("SAME-TUPLE", "DECLARED-ONLY", "DRIVER-CONFOUND")):
        print("FAILED:ADV-0136-probe2 known-good not silent")
        print(json.dumps(good, indent=2)[:2000])
        return 1
    print("known_good silent=True")

    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:ADV-0136-probe2 schema")
        for err in errs[:8]:
            print(" ", list(err.path), err.message)
        return 1
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not S.iter_errors(g):
            print("FAILED:ADV-0136-probe2 schema vacuous")
            return 1

    census = payload.get("catalog_census") or {}
    if census.get("all_covered_as_attested_or_declared_only") is not True:
        print("FAILED:ADV-0136-probe2 catalog uncovered")
        return 1
    seats = payload.get("seats") or []
    bad = [
        s
        for s in seats
        if s.get("coverage") not in {"RESPONSE-ATTESTED", "DECLARED-ONLY"}
    ]
    if bad:
        print("FAILED:ADV-0136-probe2 seats without coverage", len(bad))
        return 1
    print(
        "catalog_census "
        f"declared={census.get('declared_independent_seats')} "
        f"declared_only={census.get('declared_only')} "
        f"attested={census.get('response_attested')}"
    )
    print("SUCCESS:ADV-0136-probe2 reviewer JSONL match; confound and DECLARED-ONLY fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
