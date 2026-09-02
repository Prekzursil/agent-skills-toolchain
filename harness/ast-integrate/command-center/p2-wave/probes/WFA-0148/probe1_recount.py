#!/usr/bin/env python3
"""Probe 1: independent array recount vs counts block, plus both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classifier as C  # noqa: E402
import registry as R  # noqa: E402
import reviewer as V  # noqa: E402
import schema_check as S  # noqa: E402

OUT = (
    "command-center/foundry/"
    "WFA-0148-classifier-expressiveness-audit-six-vocabulary-value.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0148-probe1 {msg}")
    return 1


def main() -> int:
    doc, meta = R.load_registry()
    array_hist = R.histogram_from_candidates(doc)
    counts_hist = R.histogram_from_counts_block(doc)
    n_array = R.n_from_array(array_hist)
    n_counts = int(sum(counts_hist.values()))
    match = R.histograms_equal(array_hist, counts_hist)
    unused_zero = R.unused_zero(array_hist, C.UNUSED_DECLARED)
    red = R.mismatch_copy(doc)
    mismatch_detected = not R.histograms_equal(
        R.histogram_from_candidates(red), R.histogram_from_counts_block(red)
    )
    review_hist = V.recount_array_manual(doc.get("candidates") or [])
    print(f"registry_origin={meta['origin']} live_present={meta['live_present']}")
    print(f"array_recount={json.dumps(array_hist, sort_keys=True)}")
    print(f"counts_block={json.dumps(counts_hist, sort_keys=True)}")
    print(f"n_array={n_array} n_counts={n_counts} match={match}")
    print(f"unused_zero={unused_zero} mismatch_detected={mismatch_detected}")
    print(f"reviewer_array_match={R.histograms_equal(array_hist, review_hist)}")
    if n_array != 284:
        return fail(f"array n={n_array} expected 284")
    if not match:
        return fail("array recount != counts block")
    if not unused_zero:
        return fail("an unused value has nonzero array count")
    if not mismatch_detected:
        return fail("both-states: corrupted counts block not detected")
    if not R.histograms_equal(array_hist, review_hist):
        return fail("reviewer manual loop disagrees with signal A")
    for value in C.UNUSED_DECLARED:
        if int(array_hist.get(value, 0)) != 0 or int(counts_hist.get(value, 0)) != 0:
            return fail(f"{value} not zero on both readings")
    art = REPO / OUT
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0148" not in text:
        return fail("sentinel-absent")
    parsed = json.loads(text)
    st = str(parsed.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    pay = S.payload_of(parsed)
    if pay.get("signal_a_array_recount", {}).get("n") != n_array:
        return fail("artifact array n mismatch")
    if pay.get("both_states", {}).get("mismatch_detected") is not True:
        return fail("artifact both-states missing")
    if str(pay.get("kind") or parsed.get("report", {}).get("kind")) != "classifier-audit":
        return fail("report.kind != classifier-audit")
    try:
        S.assert_rejects_garbage()
        errs = S.error_list(parsed)
    except Exception as exc:
        return fail(f"schema:{type(exc).__name__}:{exc}")
    if errs:
        print("FAILED:WFA-0148-probe1 schema errors")
        for line in errs[:8]:
            print(" ", line)
        return 1
    print("schema_valid=True")
    print("SUCCESS:WFA-0148-probe1 array-vs-counts both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
