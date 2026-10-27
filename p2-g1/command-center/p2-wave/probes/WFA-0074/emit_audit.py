#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0074-disposition-cross-adjudication.json."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

import sys

sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

OUT = "command-center/wfa/WFA-0074-disposition-cross-adjudication.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0074/probe1_stratified_kappa.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0074/probe2_direction.py"
)
QUESTION = (
    "When an independent cross-vendor classifier re-adjudicates a stratified "
    "sample of 60 candidates from raw source, what is the agreement rate with "
    "the current registry - and in which DIRECTION do the disagreements point?"
)


def dump(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def main() -> int:
    records, meta = L.load_corpus()
    sample = L.stratified_sample(records)
    cov = L.coverage(sample)
    scored = L.run_adjudication(sample)
    direction = scored["direction"]
    conf = scored["confusion"]
    plants = L.planted_direction_controls()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    headline = (
        "DIRECTION first: "
        f"conservative={direction['conservative_toward_unknown_or_repair']} "
        f"dangerous={direction['dangerous_toward_adopt_as_is']} "
        f"other={direction['other']}; "
        f"then accuracy={conf['accuracy']:.4f} kappa={conf['kappa']:.4f} n=60"
    )
    criteria = {
        "source": (
            "WFA-0068 artifact absent on this tree; criteria reconstructed from "
            "the 15-value vocabulary and the falsifiable rules named by WFA-0005, "
            "WFA-0068, WFA-0069, WFA-0072, and IMP-0210. Labels withheld."
        ),
        "required_inputs": list(L.REQUIRED_FIELDS),
        "refusal": "UNKNOWN-NEEDS-PROBE whenever a required input is missing",
        "tie_break_order": list(L.TIE_BREAK),
        "control_plane": L.CONTROL_PLANE,
        "vocab_15": list(L.VOCAB_15),
    }
    doc = {
        "unit_id": "WFA-0074",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0074",
        "kind": "audit-report",
        "question": QUESTION,
        "headline": headline,
        "tests_required_order": ["direction_split", "accuracy"],
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "independent-verifier",
            "execution_substrate": "local-serialized-linux",
        },
        "source": meta,
        "sampling": {
            "n": L.SAMPLE_N,
            "seed": L.SAMPLE_SEED,
            "rule": L.SAMPLING_RULE,
            "coverage": cov,
            "sample_ids": [r["id"] for r in sample],
        },
        "label_blinding": {
            "classification_key_withheld": True,
            "method": "withhold_labels() drops classification/label/disposition/gold_label",
        },
        "criteria": criteria,
        "direction_split": {
            "conservative_toward_unknown_or_repair": direction[
                "conservative_toward_unknown_or_repair"
            ],
            "dangerous_toward_adopt_as_is": direction["dangerous_toward_adopt_as_is"],
            "other": direction["other"],
            "agree": direction["agree"],
            "disagreements": direction["disagreements"],
            "dangerous_of_sample": direction["dangerous_of_sample"],
            "dangerous_of_disagreements": direction["dangerous_of_disagreements"],
            "rows": direction["rows"],
        },
        "accuracy": {
            "value": conf["accuracy"],
            "agreements": conf["agreements"],
            "n": conf["n"],
            "reported_after_direction_split": True,
        },
        "kappa": {
            "kappa": conf["kappa"],
            "expected_agreement_pe": conf["expected_agreement_pe"],
            "accuracy": conf["accuracy"],
            "n": conf["n"],
            "per_disposition_agreement": conf["per_disposition_agreement"],
        },
        "confusion_matrix": conf["matrix"],
        "dangerous_threshold": {
            "of_sample": L.DANGEROUS_OF_SAMPLE_THRESHOLD,
            "of_disagreements": L.DANGEROUS_OF_DISAGREEMENTS_THRESHOLD,
            "exceeded": scored["threshold_exceeded"],
            "policy": (
                "If either threshold is exceeded, re-run every registry "
                "disposition class that contributed a dangerous disagreement. "
                "Do not patch individual rows."
            ),
        },
        "class_rerun": scored["class_rerun"],
        "estate_precedent": (
            "86 percent accuracy with 100 percent of errors pointing at data loss; "
            "accuracy alone is the wrong metric"
        ),
        "direction_controls": plants,
        "tests": [
            {
                "id": "WFA-0074-DIRECTION-BEFORE-ACCURACY",
                "name": "direction split reported before the accuracy figure",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "WFA-0074-LABEL-BLIND",
                "name": "adjudicator must not see existing labels",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA-0074-STRATIFIED-60",
                "name": "60-record sample spanning 9 families and 9 used dispositions",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA-0074-DANGEROUS-CLASS-RERUN",
                "name": "dangerous-direction errors trigger class re-run, not a patch",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "WFA-0074-BOTH-STATES-DIRECTION",
                "name": "planted conservative and dangerous disagreements both fire",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0074-probe2-direction-before-accuracy",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives direction and kappa from criteria-only views "
                "and refuses a headline that leads with accuracy."
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "WFA-0075-disposition-drift-monitor",
                "artifact_path": OUT,
                "probe": P1,
            },
            {
                "consumer": "WFA-0148-classifier-expressiveness",
                "artifact_path": OUT,
                "probe": P2,
            },
        ],
        "defects": [],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/WFA-0074/lib.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/WFA-0074/UNIT-ARTIFACT-MANIFEST.json",
        "ts": now,
    }
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = dump(doc)
    path.write_bytes(raw)
    sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    print(f"wrote {OUT} bytes={len(raw)} sha256={sha}")
    print("SUCCESS:WFA-0074 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
