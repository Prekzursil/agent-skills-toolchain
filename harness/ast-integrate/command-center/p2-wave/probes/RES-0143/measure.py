#!/usr/bin/env python3
"""Run the protocol over the pinned 30+5 corpus and report survival."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from audit import audit_transform
from corpus import NEGATIVE_CONTROLS, SAMPLE, ensure_on_disk
from protocol import DISPOSITION_NO, DISPOSITION_OK, PROTOCOL_ID, transform


def run_one(rec: dict[str, Any]) -> dict[str, Any]:
    result = transform(rec["text"])
    aud = audit_transform(rec["text"], result)
    return {
        "id": rec["id"],
        "cohort": rec.get("cohort"),
        "expected": rec["expected"],
        "live_disposition": result["disposition"],
        "reason": result.get("reason"),
        "template_id": result.get("template_id"),
        "path": rec.get("path"),
        "sha256": rec.get("sha256"),
        "bytes": rec.get("bytes"),
        "text": rec["text"],
        "precondition": result.get("precondition"),
        "observable": result.get("observable"),
        "local_experiment": result.get("local_experiment"),
        "source_diff": result.get("source_diff"),
        "inferred_labels": result.get("inferred_labels"),
        "claim": result.get("claim"),
        "audit_ok": aud["ok"],
        "audit_errors": aud["errors"],
        "matches_pin": result["disposition"] == rec["expected"],
    }


def measure() -> dict[str, Any]:
    pinned = ensure_on_disk()
    rows = [run_one(r) for r in pinned]
    sample = [r for r in rows if r["id"].startswith("S")]
    neg = [r for r in rows if r["id"].startswith("N")]
    survived = [r for r in sample if r["live_disposition"] == DISPOSITION_OK]
    refused = [r for r in sample if r["live_disposition"] == DISPOSITION_NO]
    n = len(sample)
    k = len(survived)
    neg_ok = all(r["live_disposition"] == DISPOSITION_NO for r in neg)
    pin_ok = all(r["matches_pin"] for r in rows)
    audit_ok = all(r["audit_ok"] for r in rows)
    mismatches = [r["id"] for r in rows if not r["matches_pin"]]
    audit_fail = [r["id"] for r in rows if not r["audit_ok"]]
    return {
        "protocol_id": PROTOCOL_ID,
        "n_sample": n,
        "n_survived": k,
        "n_refused": len(refused),
        "survival_fraction": (k / n) if n else 0.0,
        "survival_not_100_percent": k < n,
        "negative_controls": {
            "n": len(neg),
            "all_not_transformable": neg_ok,
            "ids": [r["id"] for r in neg],
            "dispositions": {r["id"]: r["live_disposition"] for r in neg},
        },
        "pin_ok": pin_ok,
        "audit_ok": audit_ok,
        "mismatches": mismatches,
        "audit_fail": audit_fail,
        "survived_ids": [r["id"] for r in survived],
        "refused_ids": [r["id"] for r in refused],
        "rows": rows,
        "expected_transformable": sum(1 for s in SAMPLE if s["expected"] == DISPOSITION_OK),
        "expected_negative": len(NEGATIVE_CONTROLS),
    }


def main() -> int:
    m = measure()
    slim = {k: v for k, v in m.items() if k != "rows"}
    print(json.dumps(slim, indent=2, sort_keys=True))
    if not (m["pin_ok"] and m["audit_ok"] and m["negative_controls"]["all_not_transformable"] and m["survival_not_100_percent"] and m["n_sample"] == 30):
        print("FAILED:RES-0143-measure")
        return 1
    print(
        f"SUCCESS:RES-0143-measure survived={m['n_survived']}/{m['n_sample']} "
        f"fraction={m['survival_fraction']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
