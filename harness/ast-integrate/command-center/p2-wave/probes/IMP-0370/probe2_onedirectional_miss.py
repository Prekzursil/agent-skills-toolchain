#!/usr/bin/env python3
"""Probe 2: one-directional check MISSES DIVERGED; error DIRECTION is data-loss.

Same labelled fixtures as probe 1. one_directional_check must never emit
DIVERGED, must classify every DIVERGED case as AHEAD (safe-to-overwrite),
and every such miss must count as a data-loss error. Two-directional
classify_bytes on the same fixtures must catch every DIVERGED case.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from crossvendor.divergence import (  # noqa: E402
    classify_bytes,
    error_points_at_data_loss,
    one_directional_check,
    score_labelled,
)
from crossvendor.fixtures import labelled_cases  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0370.json"
UNIT = "IMP-0370"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    cases = labelled_cases()
    diverged = [c for c in cases if c["label"] == "DIVERGED"]
    if len(diverged) < 4:
        return fail(f"diverged n={len(diverged)}")

    two = score_labelled(one_directional=False)
    one = score_labelled(one_directional=True)

    one_preds = []
    two_preds = []
    for case in diverged:
        o = one_directional_check(case["ours"], case["theirs"])
        t = classify_bytes(case["ours"], case["theirs"])
        one_preds.append({"id": case["id"], "one": o, "two": t})
        if t != "DIVERGED":
            return fail(f"two-directional missed {case['id']} -> {t}")
        if o == "DIVERGED":
            return fail(f"one-directional emitted DIVERGED on {case['id']}")
        if o != "AHEAD":
            return fail(f"one-directional {case['id']} predicted {o}, expected AHEAD")
        if not error_points_at_data_loss("DIVERGED", o):
            return fail(f"{case['id']} miss not counted as data-loss")

    # The instrument must be incapable of the DIVERGED class.
    for case in cases:
        if one_directional_check(case["ours"], case["theirs"]) == "DIVERGED":
            return fail(f"one-directional emitted DIVERGED on {case['id']}")

    d_acc_one = one["per_class"]["DIVERGED"]["accuracy"]
    d_acc_two = two["per_class"]["DIVERGED"]["accuracy"]
    if d_acc_two != 1.0:
        return fail(f"two-directional DIVERGED accuracy {d_acc_two}")
    if d_acc_one != 0.0:
        return fail(f"one-directional must miss DIVERGED; accuracy={d_acc_one}")
    if one["emitted_diverged_count"] != 0:
        return fail("one-directional emitted_diverged_count != 0")
    if two["emitted_diverged_count"] != len(diverged):
        return fail("two-directional emitted_diverged_count != n(DIVERGED)")

    direction = one["error_direction"]
    if direction["data_loss_count"] != len(diverged):
        return fail(
            f"data_loss_count={direction['data_loss_count']} != {len(diverged)}"
        )
    if direction["total_errors"] != len(diverged):
        return fail(f"total_errors={direction['total_errors']} (expected only DIVERGED misses)")
    if direction["data_loss_fraction_of_errors"] != 1.0:
        return fail("not all one-directional errors point at data loss")
    if direction["non_data_loss_count"] != 0:
        return fail("unexpected non-data-loss errors")

    printable = {
        "two_directional_diverged_accuracy": d_acc_two,
        "one_directional_diverged_accuracy": d_acc_one,
        "one_directional_emitted_diverged": one["emitted_diverged_count"],
        "diverged_n": len(diverged),
        "diverged_pairs": one_preds,
        "error_direction": {
            "total_errors": direction["total_errors"],
            "data_loss_count": direction["data_loss_count"],
            "data_loss_fraction_of_errors": direction["data_loss_fraction_of_errors"],
            "definition": direction["definition"],
        },
        "coverage_added": True,
    }
    print(json.dumps(printable, sort_keys=True))

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0370" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    rec_one = doc.get("one_directional") or {}
    rec_dir = rec_one.get("error_direction") or {}
    if (rec_one.get("per_class") or {}).get("DIVERGED", {}).get("accuracy") != 0.0:
        return fail("receipt one-directional DIVERGED accuracy not 0")
    if rec_one.get("emitted_diverged_count") != 0:
        return fail("receipt one-directional emitted DIVERGED")
    if rec_dir.get("data_loss_count") != len(diverged):
        return fail("receipt data_loss_count drifted")
    if rec_dir.get("data_loss_fraction_of_errors") != 1.0:
        return fail("receipt error-direction fraction drifted")
    rec_two = doc.get("two_directional") or {}
    if (rec_two.get("per_class") or {}).get("DIVERGED", {}).get("accuracy") != 1.0:
        return fail("receipt two-directional DIVERGED accuracy not 1")
    nc = doc.get("negative_control_ids") or []
    if "NC-ONEDIRECTIONAL-MISSES-DIVERGED" not in nc:
        return fail("receipt missing negative_control_ids row")

    print(
        f"one_dir_misses={len(diverged)} data_loss={direction['data_loss_count']} "
        f"two_dir_catches={len(diverged)}"
    )
    print("SUCCESS:IMP-0370-probe2 one-directional misses DIVERGED; errors are data-loss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
