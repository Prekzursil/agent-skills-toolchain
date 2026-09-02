#!/usr/bin/env python3
"""Reference confirmer: emit every confirmation-record field and round-trip."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixtures import well_formed_record  # noqa: E402


def emit() -> dict:
    return well_formed_record()


def round_trip(record: dict) -> dict:
    blob = json.dumps(record, sort_keys=True, separators=(",", ":"))
    parsed = json.loads(blob)
    again = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    return {
        "byte_identical": blob == again,
        "object_equal": parsed == record,
        "bytes": len(blob.encode("utf-8")),
        "fields": sorted(record.keys()),
    }


def main() -> int:
    rec = emit()
    rt = round_trip(rec)
    report = {"record": rec, "round_trip": rt}
    print(json.dumps(report, indent=2, sort_keys=True))
    if not rt["byte_identical"] or not rt["object_equal"]:
        print("FAILED:CNF-0129-confirmer round-trip loss", file=sys.stderr)
        return 1
    required = {
        "kind",
        "claim_id",
        "confirmer",
        "blinding_attestation_hash",
        "baseline_repro",
        "corrected_repro",
        "rollback_repro",
        "regression_diff",
        "discrepancies",
        "verdict",
        "source_probe",
        "verifier_probe",
        "residual_caveat",
    }
    missing = sorted(required - set(rec))
    if missing:
        print(f"FAILED:CNF-0129-confirmer missing {missing}", file=sys.stderr)
        return 1
    print("SUCCESS:CNF-0129-confirmer round-trip lossless")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
