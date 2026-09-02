#!/usr/bin/env python3
"""Probe 1: 4-class labelled fixture, per-class accuracy (never pooled).

Two-directional classify_bytes must score 1.0 on every class. A pooled
micro-average is recorded only as a non-figure so it cannot hide a class miss.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from crossvendor.divergence import (  # noqa: E402
    CLASSES,
    classify_bytes,
    score_labelled,
    unique_spans,
)
from crossvendor.fixtures import labelled_cases  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0370.json"
UNIT = "IMP-0370"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    cases = labelled_cases()
    report = score_labelled(one_directional=False)
    per_class = report["per_class"]
    printable = {
        "instrument": report["instrument"],
        "n_cases": report["n_cases"],
        "pooled_accuracy_is_not_the_figure": True,
        "per_class": {
            c: {
                "n": per_class[c]["n"],
                "correct": per_class[c]["correct"],
                "accuracy": per_class[c]["accuracy"],
                "errors": per_class[c]["errors"],
            }
            for c in CLASSES
        },
        "error_direction": {
            "total_errors": report["error_direction"]["total_errors"],
            "data_loss_count": report["error_direction"]["data_loss_count"],
        },
    }
    print(json.dumps(printable, sort_keys=True))

    counts = {c: 0 for c in CLASSES}
    for case in cases:
        counts[case["label"]] += 1
    for cls in CLASSES:
        if counts[cls] < 4:
            return fail(f"class {cls} has n={counts[cls]} (need >=4)")
        bucket = per_class[cls]
        if bucket["n"] != counts[cls]:
            return fail(f"{cls} n drifted {bucket['n']} vs {counts[cls]}")
        if bucket["accuracy"] != 1.0:
            return fail(
                f"per-class accuracy {cls}={bucket['accuracy']} "
                f"errors={bucket['errors']}"
            )
        if bucket["correct"] != bucket["n"]:
            return fail(f"{cls} correct {bucket['correct']} != n {bucket['n']}")

    # Independent uniqueness: DIVERGED iff both opcode-unique flags, etc.
    for case in cases:
        u = unique_spans(case["ours"], case["theirs"])
        pred = classify_bytes(case["ours"], case["theirs"])
        if case["label"] == "IDENTICAL":
            if case["ours"] != case["theirs"] or pred != "IDENTICAL":
                return fail(f"{case['id']} identical fixture not equal")
        elif case["label"] == "AHEAD":
            if not u["ours_unique"] or u["theirs_unique"] or pred != "AHEAD":
                return fail(f"{case['id']} ahead uniqueness mismatch {u} {pred}")
        elif case["label"] == "BEHIND":
            if u["ours_unique"] or not u["theirs_unique"] or pred != "BEHIND":
                return fail(f"{case['id']} behind uniqueness mismatch")
        elif case["label"] == "DIVERGED":
            if not (u["ours_unique"] and u["theirs_unique"] and pred == "DIVERGED"):
                return fail(f"{case['id']} diverged uniqueness mismatch {u} {pred}")

    if report["error_direction"]["total_errors"] != 0:
        return fail("two-directional errors must be zero")

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
    recorded = ((doc.get("two_directional") or {}).get("per_class")) or {}
    for cls in CLASSES:
        rec = recorded.get(cls) or {}
        if rec.get("accuracy") != 1.0:
            return fail(f"receipt per-class {cls} accuracy {rec.get('accuracy')}")
        if rec.get("n") != per_class[cls]["n"]:
            return fail(f"receipt n {cls} {rec.get('n')} != live {per_class[cls]['n']}")
        if rec.get("correct") != per_class[cls]["correct"]:
            return fail(f"receipt correct {cls} drifted")
    if doc.get("pooled_accuracy_is_not_the_figure") is not True:
        return fail("receipt must refuse pooled accuracy as the figure")

    print(
        "per_class "
        + " ".join(
            f"{c}={per_class[c]['correct']}/{per_class[c]['n']}" for c in CLASSES
        )
    )
    print("SUCCESS:IMP-0370-probe1 per-class accuracy (never pooled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
