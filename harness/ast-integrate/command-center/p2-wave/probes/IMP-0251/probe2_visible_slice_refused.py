#!/usr/bin/env python3
"""Probe 2: model-evaluation both-states.

Visible-slice-only verdict refused; held-out evaluation proceeds.
Partition membership is recomputed independently from the case hash.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from overfit_detector.partition import HELD_OUT, VISIBLE, independent_slice, slice_of  # noqa: E402
from science_blueprints.experiment_design import design  # noqa: E402
from science_blueprints.model_evaluation import (  # noqa: E402
    HonestRule,
    VisibleSliceOnlyVerdictError,
    build_eval_corpus,
    evaluate,
    try_evaluate,
)
from science_blueprints.scientific_replication import replicate  # noqa: E402

RAW = HERE / "probe2-visible-slice.raw.json"


def main() -> int:
    cases = build_eval_corpus(80)
    for case in cases:
        if independent_slice(case.id) != slice_of(case.id):
            print("FAILED:IMP-0251-probe2 partition not a pure function of case hash")
            return 1

    model = HonestRule()
    held = try_evaluate(model, cases, slice_name=HELD_OUT)
    vis = try_evaluate(model, cases, slice_name=VISIBLE)
    everyone = try_evaluate(model, cases, slice_name="all")

    if vis.get("refused") is not True or vis.get("reason_id") != "model-eval.visible-slice-only":
        print("FAILED:IMP-0251-probe2 visible slice not refused", json.dumps(vis))
        return 1
    if vis.get("verdict") is not None or vis.get("accuracy") is not None:
        print("FAILED:IMP-0251-probe2 visible slice leaked a verdict", json.dumps(vis))
        return 1
    if everyone.get("refused") is not True:
        print("FAILED:IMP-0251-probe2 all-slice evaluation was accepted", json.dumps(everyone))
        return 1
    if held.get("refused") is not False or held.get("verdict") != "EVALUATED":
        print("FAILED:IMP-0251-probe2 held-out evaluation did not proceed", json.dumps(held))
        return 1
    if held.get("accuracy") != 1.0:
        print("FAILED:IMP-0251-probe2 honest model not exact on held-out", json.dumps(held))
        return 1
    if int(held.get("heldout_n") or 0) < 8:
        print("FAILED:IMP-0251-probe2 held-out slice below floor", json.dumps(held))
        return 1

    raised = False
    try:
        evaluate(model, cases, slice_name=VISIBLE)
    except VisibleSliceOnlyVerdictError as exc:
        raised = exc.reason_id == "model-eval.visible-slice-only"
    if not raised:
        print("FAILED:IMP-0251-probe2 evaluate(visible) did not raise")
        return 1

    proceeded = evaluate(model, cases, slice_name=HELD_OUT)
    if proceeded.get("verdict") != "EVALUATED":
        print("FAILED:IMP-0251-probe2 evaluate(held-out) failed", json.dumps(proceeded))
        return 1

    planned = design(0.5)
    if planned["verdict"] != "PROCEED" or not (60 <= int(planned["required_n_per_arm"]) <= 70):
        print("FAILED:IMP-0251-probe2 experiment-design required n", json.dumps(planned))
        return 1
    stopped = design(0.5, budget_n_per_arm=8)
    if stopped["verdict"] != "STOP":
        print("FAILED:IMP-0251-probe2 experiment-design did not stop under budget")
        return 1

    proto_ok = replicate(
        {
            "effect_size": 0.5,
            "protocol_id": "prot.imp0251-two-sample-v1",
            "steps": ["declare-d", "collect", "report-effect-size"],
        },
        {
            "alpha": 0.05,
            "effect_size": 0.5,
            "id": "fx.replication-ok",
            "mean_a": 0.0,
            "mean_b": 0.5,
            "n_a": 64,
            "n_b": 64,
            "sd_a": 1.0,
            "sd_b": 1.0,
        },
    )
    proto_bad = replicate({"protocol_id": "", "steps": []}, {
        "alpha": 0.05,
        "id": "fx.replication-no-protocol",
        "mean_a": 0.0,
        "mean_b": 0.5,
        "n_a": 64,
        "n_b": 64,
        "sd_a": 1.0,
        "sd_b": 1.0,
    })
    if proto_ok.get("verdict") != "REPLICATED" or proto_bad.get("verdict") != "REJECTED":
        print("FAILED:IMP-0251-probe2 replication both-states", proto_ok, proto_bad)
        return 1

    doc = {
        "all_slice_refused": True,
        "both_states": True,
        "experiment_design_required_n": planned["required_n_per_arm"],
        "heldout_accuracy": held["accuracy"],
        "heldout_n": held["heldout_n"],
        "heldout_proceeded": True,
        "pass": True,
        "replication_missing_protocol_rejected": True,
        "visible_n": held["visible_n"],
        "visible_slice_refused": True,
        "visible_verdict": vis.get("verdict"),
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"visible_slice_refused=True heldout_proceeded=True "
        f"heldout_accuracy={held['accuracy']} heldout_n={held['heldout_n']} "
        f"visible_n={held['visible_n']} required_n={planned['required_n_per_arm']}"
    )
    print("SUCCESS:IMP-0251-probe2 visible-slice refused; held-out proceeds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
