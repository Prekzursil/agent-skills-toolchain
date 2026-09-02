#!/usr/bin/env python3
"""Probe 2: the threshold is declared and versioned, not tuned per run.

Mechanically independent of probe 1 (which checks flag/silent). This probe
refuses a per-run override, binds version 1.0.0, and checks two detect() calls
use the same frozen spec_sha256.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from overfit_detector.corpus import build_corpus  # noqa: E402
from overfit_detector.detector import detect  # noqa: E402
from overfit_detector.partition import split  # noqa: E402
from overfit_detector.threshold import (  # noqa: E402
    PerRunThresholdTuneError,
    load_threshold,
)
from overfit_detector.workflows import MemorizeVisibleWorkflow, TrueRuleWorkflow  # noqa: E402

RAW = HERE / "probe2-threshold.raw.json"


def main() -> int:
    spec = load_threshold()
    if spec["version"] != "1.0.0" or spec["id"] != "imp-0206-overfit-gap-v1":
        print("FAILED:IMP-0206-probe2 threshold not versioned", spec)
        return 1
    if spec["gap_abs"] != 0.25 or not spec["frozen"]:
        print("FAILED:IMP-0206-probe2 threshold not frozen at declared 0.25")
        return 1

    refused = False
    try:
        load_threshold(threshold_override=0.99)
    except PerRunThresholdTuneError:
        refused = True
    if not refused:
        print("FAILED:IMP-0206-probe2 per-run override was accepted")
        return 1

    refused_same = False
    try:
        detect(TrueRuleWorkflow(), build_corpus(80), threshold_override=0.25)
    except PerRunThresholdTuneError:
        refused_same = True
    if not refused_same:
        print("FAILED:IMP-0206-probe2 same-value override was accepted")
        return 1

    cases = build_corpus(80)
    visible, _heldout = split(cases)
    overfit = MemorizeVisibleWorkflow(visible)
    honest = TrueRuleWorkflow()
    a = detect(overfit, cases)
    b = detect(overfit, cases)
    c = detect(honest, cases)
    if a["threshold"]["spec_sha256"] != b["threshold"]["spec_sha256"]:
        print("FAILED:IMP-0206-probe2 threshold retuned across runs")
        return 1
    if a["threshold"]["spec_sha256"] != c["threshold"]["spec_sha256"]:
        print("FAILED:IMP-0206-probe2 threshold differs by workflow")
        return 1
    if a["threshold"]["gap_abs"] != spec["gap_abs"]:
        print("FAILED:IMP-0206-probe2 detect() did not use declared gap_abs")
        return 1

    tiny = detect(honest, build_corpus(80)[:4])
    if tiny["verdict"] != "INSUFFICIENT-EVIDENCE":
        print("FAILED:IMP-0206-probe2 underpowered run emitted a verdict", tiny)
        return 1

    doc = {
        "frozen": True,
        "override_refused": True,
        "pass": True,
        "same_across_runs": True,
        "spec_sha256": spec["spec_sha256"],
        "threshold_gap_abs": spec["gap_abs"],
        "threshold_id": spec["id"],
        "underpowered_insufficient_evidence": True,
        "version": spec["version"],
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"threshold_id={spec['id']} version={spec['version']} frozen=True "
        f"override_refused=True same_across_runs=True "
        f"spec_sha256={spec['spec_sha256'][:16]}"
    )
    print("SUCCESS:IMP-0206-probe2 threshold versioned not per-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
