#!/usr/bin/env python3
"""Probe 1: size histogram over >=200 real receipts and a percentile floor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.completion_reducer import MIN_BYTES_DEFAULT  # noqa: E402

import calibrate as C  # noqa: E402

ART = REPO / "command-center/receipts/TST-0007.json"
UNIT = "TST-0007"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    measured = C.run(REPO)
    n_hist = int(measured["n_histogram"])
    n_rcpt = int(measured["n_receipt_class"])
    threshold = int(measured["threshold"])
    p0 = measured["derivation"]["percentiles"]["p0"]
    print(
        f"n_histogram={n_hist} n_receipt_class={n_rcpt} "
        f"threshold={threshold} percentile=p{measured['percentile']} "
        f"p0={p0} MIN_BYTES_DEFAULT={MIN_BYTES_DEFAULT}"
    )
    print("histogram_class_counts " + json.dumps(measured["histogram_class_counts"], sort_keys=True))
    print("receipt_class_counts " + json.dumps(measured["receipt_class_counts"], sort_keys=True))
    for bucket in measured["histogram"]:
        print(f"bucket {bucket['bucket']} count={bucket['count']}")

    if n_hist < 200:
        return fail(f"histogram n={n_hist} < 200")
    if n_rcpt < 1:
        return fail("receipt-class corpus empty")
    if threshold != int(p0):
        return fail(f"threshold {threshold} is not p0 {p0}")
    if threshold in {128, 512, 1024} and threshold != int(p0):
        return fail("threshold looks like a guessed constant")
    if MIN_BYTES_DEFAULT != threshold:
        return fail(
            f"MIN_BYTES_DEFAULT={MIN_BYTES_DEFAULT} != measured threshold {threshold}"
        )
    if not measured["source_matches_threshold"]:
        return fail("source MIN_BYTES_DEFAULT does not match measured threshold")
    if int(measured["derivation"]["observed_min"]) != threshold:
        return fail("observed_min drifted from threshold")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:TST-0007" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    cal = doc.get("calibration") or {}
    if int(cal.get("threshold") or 0) != threshold:
        return fail(f"artifact threshold {cal.get('threshold')} != live {threshold}")
    if int(cal.get("n_histogram") or 0) < 200:
        return fail("artifact histogram n < 200")
    if not (doc.get("histogram") or []):
        return fail("artifact missing histogram")
    print("SUCCESS:TST-0007-probe1 histogram and p0 threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
