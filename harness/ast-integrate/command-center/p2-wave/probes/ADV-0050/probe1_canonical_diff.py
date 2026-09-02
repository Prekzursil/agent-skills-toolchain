#!/usr/bin/env python3
"""Probe 1: LICENSE text vs canonical SPDX body.

Mechanically a copyright/whitespace-insensitive body equality plus extra-clause
extraction. A raw byte-diff of a known-canonical file with extra blank lines
MUST stay a zero body-diff; treating that raw inequality as a rider inflates
every result (catalog control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / A.OUTPUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0050-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = A.validate_against_schema(doc)
    print(f"schema_ok={ok} {why}")
    if not ok:
        print("FAILED:ADV-0050-probe1 schema")
        return 1
    if A.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0050-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0050-probe1 self-declared {doc.get('state')}")
        return 1

    live = A.run_probe1()
    art_fp = (doc.get("fingerprints") or {}).get("probe1")
    live_fp = [r["fingerprint"] for r in live["rows"]]
    payload = {
        "probe": "probe1-canonical-diff",
        "unit_id": A.UNIT_ID,
        "pass": False,
        "control_canonical_zero_diff": live["control_canonical_zero_diff"],
        "control_whitespace_zero_diff": live["control_whitespace_zero_diff"],
        "whitespace_raw_texts_differ": live["whitespace_raw_texts_differ"],
        "planted_ml_rider_nonzero": live["planted_ml_rider_nonzero"],
        "planted_ml_classes": live["planted_ml_classes"],
        "extra_license_fixture_zero_diff": live["extra_license_fixture_zero_diff"],
        "known_case_nonzero": live["known_case_nonzero"],
        "known_case_classes": live["known_case_classes"],
        "fingerprint_match": art_fp == live_fp,
        "n_rows": len(live["rows"]),
    }
    payload["pass"] = bool(
        live["pass"]
        and payload["fingerprint_match"]
        and payload["control_canonical_zero_diff"]
        and payload["control_whitespace_zero_diff"]
        and payload["whitespace_raw_texts_differ"]
        and payload["planted_ml_rider_nonzero"]
        and payload["extra_license_fixture_zero_diff"]
        and payload["known_case_nonzero"]
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not payload["pass"]:
        print(f"FAILED:ADV-0050-probe1 live={live['pass']} fp={payload['fingerprint_match']}")
        print(f"  art_fp={art_fp}")
        print(f"  live_fp={live_fp}")
        return 1
    print(
        "SUCCESS:ADV-0050-probe1 canonical zero-diff; whitespace twin still "
        "zero; planted and known-case riders non-zero"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
