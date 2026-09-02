#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0164.json from a live extraction."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from foundry.stage_extract import projection  # noqa: E402

OUT = "command-center/receipts/IMP-0164.json"
SENTINEL = "SUCCESS:IMP-0164"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0164/probe1_span_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0164/probe2_control_gold.py"
)


def main() -> int:
    reports = S.extract_all()
    control = reports["control"]
    if not control["ok"] or control["span_coverage"] != 1.0:
        print("FAILED:IMP-0164 emit: control coverage is not 1.0")
        return 1
    if not S.gold_matches(control):
        print("FAILED:IMP-0164 emit: control does not match gold")
        return 1
    planted = reports["unanchored"]
    if planted["ok"] or planted["span_coverage"] >= 1.0:
        print("FAILED:IMP-0164 emit: unanchored plant did not fire")
        return 1
    empty = reports["empty"]
    if not empty["honest_null"]:
        print("FAILED:IMP-0164 emit: empty source was not HONEST-NULL")
        return 1
    if reports["unmapped"]["stages"][0]["kind"] != "UNKNOWN":
        print("FAILED:IMP-0164 emit: unmapped kind was snapped")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gold = projection(control)
    coverage = {
        "control": control["span_coverage"],
        "codex": reports["codex"]["span_coverage"],
        "dag": reports["dag"]["span_coverage"],
        "unanchored_plant": planted["span_coverage"],
        "formula": control["span_coverage_formula"],
        "computed_not_sampled": True,
        "control_extracted": control["extracted_count"],
        "control_anchored": control["anchored_count"],
    }
    doc = {
        "unit_id": "IMP-0164",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Typed stage extraction from an imported workflow",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "ts": now,
        "question": (
            "What are the STAGES of an imported workflow, expressed in a "
            "vocabulary that is comparable across sources?"
        ),
        "extractor": {
            "module": "tools/foundry/stage_extract.py",
            "schema": control["schema"],
            "canonical_kinds": [
                "UNIT",
                "FAN_OUT",
                "DYNAMIC_FAN_OUT",
                "BARRIER",
                "PIPELINE",
                "SUBWORKFLOW",
                "LOOP",
                "GATE",
                "UNKNOWN",
            ],
        },
        "span_coverage": coverage,
        "gold_match": True,
        "gold_projection": gold,
        "honest_null_on_empty": empty["honest_null"],
        "unmapped_native_kind_is_unknown": True,
        "unanchored_stage_is_failure": True,
        "extractions": {
            "control": control,
            "codex": reports["codex"],
            "dag": reports["dag"],
            "empty": empty,
            "unmapped": reports["unmapped"],
            "unanchored_plant": planted,
        },
        "tests": [
            {
                "id": "span-coverage-100",
                "name": "span coverage == 1.0 (computed, not sampled)",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "hand-labelled-control",
                "name": "hand-labelled control workflow reproduces exactly",
                "result": "PASS",
                "command": P2,
            },
        ],
        "evidence": [
            {
                "id": "E1",
                "claim": "100% of extracted stages carry a resolvable source span",
                "kind": "computed-coverage",
                "value": coverage["control"],
                "formula": coverage["formula"],
                "extracted": coverage["control_extracted"],
                "anchored": coverage["control_anchored"],
            },
            {
                "id": "E2",
                "claim": "hand-labelled control workflow matches the extracted stage list",
                "kind": "exact-list-equality",
                "matched": True,
                "stage_ids": [s["id"] for s in gold],
            },
        ],
        "both_states": {
            "good": {
                "fixture": "control",
                "ok": control["ok"],
                "span_coverage": control["span_coverage"],
            },
            "bad": {
                "fixture": "control with critic span stripped",
                "ok": planted["ok"],
                "span_coverage": planted["span_coverage"],
                "unanchored_ids": planted["unanchored_ids"],
            },
            "fired_on_bad_state": (not planted["ok"])
            and planted["span_coverage"] < 1.0,
            "silent_on_good_state": control["ok"] and control["span_coverage"] == 1.0,
        },
        "notes": (
            "IMP-0160..IMP-0162 adapter receipts are absent on this worktree. "
            "Fixtures are the typed imported-workflow shape those adapters are "
            "contracted to emit, paired with original source text so spans are "
            "real character offsets. SUCCESS:IMP-0164"
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
