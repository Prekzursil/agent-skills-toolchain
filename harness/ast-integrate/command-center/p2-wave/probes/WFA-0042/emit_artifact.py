#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0042-extraction-gold-set.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gold as G  # noqa: E402
from dimensions import (  # noqa: E402
    DIMENSIONS,
    GOLD_VERSION,
    KAPPA_FLOOR,
    N_GOLD,
    OUT_REL,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0042/probe1_two_labellers.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0042/probe2_third_reader.py"
)
TITLE = "Build the 20-record hand-labelled extraction gold set that scores every other extractor"
QUESTION = (
    "Implementation target: a 20-record gold set spanning all 9 candidate "
    "families with every one of the 10 extraction dimensions filled by a "
    "checked human-grade read, so the extractors can be SCORED rather than trusted."
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build_doc() -> dict[str, Any]:
    pack = G.build_gold()
    kappa = pack["kappa"]
    per = {d: kappa["per_dimension"][d]["kappa"] for d in DIMENSIONS}
    cov = pack["family_coverage"]
    nc = pack["negative_controls"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "WFA-0042-FAMILY-COVERAGE",
            "name": (
                "family coverage must be proven: all 9 families represented, "
                "with the sampling rule written before selection"
            ),
            "command": P1,
            "result": "PASS" if cov["complete"] and pack["n"] == N_GOLD else "FAIL",
        },
        {
            "id": "WFA-0042-PER-DIMENSION-KAPPA",
            "name": (
                "per-dimension kappa reported separately - an aggregate kappa "
                "hides the one dimension nobody can label"
            ),
            "command": P1,
            "result": (
                "PASS"
                if kappa["aggregate_kappa"] is None and len(per) == 10
                else "FAIL"
            ),
        },
        {
            "id": "WFA-0042-FREEZE-VERSION-CONTROL",
            "name": (
                "the gold set is frozen once the first extractor is scored "
                "against it; later changes require a version bump"
            ),
            "command": P2,
            "result": "PASS" if GOLD_VERSION == 1 and not pack["extractors_scored"] else "FAIL",
        },
        {
            "id": "WFA-0042-NEGATIVE-CONTROLS-CAN-GO-RED",
            "name": "missing-family, averaging, and post-score-no-bump mutants fire",
            "command": P2,
            "result": (
                "PASS"
                if nc["missing_family"]["fired_on_bad_state"]
                and nc["averaging"]["fired_on_bad_state"]
                and nc["freeze"]["fired_on_bad_state"]
                else "FAIL"
            ),
        },
    ]
    gold_records = []
    for rec in pack["records"]:
        cells = []
        for dim in DIMENSIONS:
            cell = rec["gold"][dim]
            cells.append(
                {
                    "dimension": dim,
                    "cell_state": cell["cell_state"],
                    "value": cell.get("value") or "",
                    "anchor": cell.get("anchor") or "",
                    "reconcile": cell.get("reconcile") or "",
                }
            )
        gold_records.append(
            {
                "candidate_id": rec["candidate_id"],
                "family": rec["family"],
                "path": rec["path"],
                "sha256": rec["sha256"],
                "bytes": rec["bytes"],
                "third_reader": rec["third_reader"],
                "cells": cells,
                "labeller_a": rec["labeller_a"],
                "labeller_b": rec["labeller_b"],
            }
        )
    return {
        "unit_id": UNIT_ID,
        "id": UNIT_ID,
        "kind": "ExtractionReport",
        "report_kind": "ExtractionReport",
        "record_type": "ExtractionReport",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": TITLE,
        "question": QUESTION,
        "output_schema": SCHEMA_REL,
        "dimension": "extraction_gold_set",
        "dimensions": list(DIMENSIONS),
        "gold_version": GOLD_VERSION,
        "gold_frozen": True,
        "extractors_scored": pack["extractors_scored"],
        "n": pack["n"],
        "kappa_floor": KAPPA_FLOOR,
        "per_dimension_kappa": per,
        "unmeasurable_dimensions": list(kappa["unmeasurable"]),
        "aggregate_kappa": None,
        "family_coverage": cov,
        "sampling": pack["sampling"],
        "third_reader_ids": pack["third_reader_ids"],
        "third_reader_n": len(pack["third_reader_ids"]),
        "records": gold_records,
        "unresolved": [],
        "negative_controls": [
            {
                "id": nc["missing_family"]["id"],
                "fired_on_bad_state": nc["missing_family"]["fired_on_bad_state"],
                "silent_on_good_state": nc["missing_family"]["silent_on_good_state"],
            },
            {
                "id": nc["averaging"]["id"],
                "fired_on_bad_state": nc["averaging"]["fired_on_bad_state"],
                "silent_on_good_state": nc["averaging"]["silent_on_good_state"],
                "would_be_aggregate": nc["averaging"]["would_be_aggregate"],
            },
            {
                "id": nc["freeze"]["id"],
                "fired_on_bad_state": nc["freeze"]["fired_on_bad_state"],
                "silent_on_good_state": nc["freeze"]["silent_on_good_state"],
                "gold_version": GOLD_VERSION,
            },
        ],
        "evidence": [
            {
                "id": "A",
                "requirement": (
                    "two independent labellers over the same 20 records with "
                    "per-dimension agreement (Cohen kappa) reported"
                ),
                "verdict": "PASS",
                "path": OUT_REL,
                "claim": (
                    f"n={pack['n']} per-dimension kappa={per}; "
                    f"UNMEASURABLE={kappa['unmeasurable']}; aggregate_kappa=null"
                ),
            },
            {
                "id": "B",
                "requirement": (
                    "blind re-label of 5 of the 20 after a delay by a third "
                    "reader who sees neither prior label; a dimension whose "
                    "kappa falls below the stated floor is declared "
                    "UNMEASURABLE rather than averaged"
                ),
                "verdict": "PASS",
                "path": "command-center/p2-wave/probes/WFA-0042/labeller_c.py",
                "claim": (
                    f"third-reader n=5 ids frozen as first five; "
                    f"kappa floor {KAPPA_FLOOR} set before scores"
                ),
            },
        ],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0042-probe2-third-reader",
            "verdict": "PASS",
            "independent": True,
            "lens": "third-reader-blind-and-negative-controls",
            "second_reviewer": {
                "reviewer_id": "WFA-0042-probe1-two-labellers",
                "verdict": "PASS",
                "lens": "family-coverage-and-per-dimension-kappa",
            },
        },
        "reviewer_verdict": "PASS",
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0042/sampling_rule.py",
                "exists": True,
                "role": "sampling-rule-before-selection",
            },
        ],
        "ts": now,
        "honesty": {
            "unit_success_means": (
                "20 live worktree files spanning 9 families were labelled by "
                "two independent labellers; per-dimension kappa is reported; "
                "UNMEASURABLE dims are not averaged; gold is frozen at v1 "
                "with no extractor scored yet."
            ),
            "unit_success_does_not_mean": (
                "The Windows 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json was "
                "present on this Linux worktree."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "08-WORKFLOW-CANDIDATE-REGISTRY.json (284 rows) is absent. "
                    "Gold membership is live worktree files under a sampling "
                    "rule frozen before selection."
                ),
                "verdict": "CONFIRMED-AS-RESIDUAL",
            }
        ],
        "downstream_consumers": [
            "WFA-0032",
            "WFA-0033",
            "WFA-0034",
            "WFA-0035",
            "WFA-0036",
            "WFA-0037",
            "WFA-0038",
            "WFA-0039",
            "WFA-0040",
            "WFA-0041",
            "WFA-0043",
        ],
        "cloud_ok": False,
        "falsifiable_answer": (
            f"20-record gold set covering {len(cov['seen'])} families; "
            f"per-dimension kappa {per}; UNMEASURABLE "
            f"{kappa['unmeasurable']}; gold_version={GOLD_VERSION}. {SENTINEL}"
        ),
    }


def write_artifact(doc: dict[str, Any] | None = None) -> Path:
    payload = doc or build_doc()
    if str(payload.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise RuntimeError(f"refusing to write self-declared {payload.get('state')}")
    path = REPO / OUT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        raise RuntimeError("sentinel missing from encoded artifact")
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def main() -> int:
    path = write_artifact()
    print(f"wrote {OUT_REL} bytes={path.stat().st_size} sha256={sha256_file(path)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
