#!/usr/bin/env python3
"""Probe 2: per-seat role vocabulary + honest same-model hard-case class.

Negative control: a single-model council with strong role prompts is scored
as-is. Model ids are not a fire input: swapping every model label must not
change the verdict. Receipt must report that same classification rather than
a tuned story.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    collapsed_council,
    diverse_council,
    hard_same_model_strong_roles,
)
from load import load_detector  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0320.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0320-probe2 {msg}")
    return 1


def main() -> int:
    D = load_detector()
    hard = hard_same_model_strong_roles()
    live = D.detect(hard)
    print("hard_case_id=" + str(hard["id"]))
    print(f"hard_status={live['status']} fired={live['fired']}")
    print(f"hard_mean_pairwise={live['mean_pairwise_jaccard']}")
    print(f"hard_mean_role_vocab={live['mean_role_vocab_score']}")
    print(f"hard_unique_models={live['unique_models']}")

    rows = live["role_vocab"]
    for row in rows:
        print(
            f"seat_role={row['role']} vocab_score={row['score']} "
            f"found={row['found']} missing={row['missing']}"
        )
        if row["score"] < D.VOCAB_FIRE:
            return fail(f"hard-case seat {row['role']} lost role vocabulary")

    mutated = deepcopy(hard)
    for i, seat in enumerate(mutated["seats"]):
        seat["model"] = f"mutant-model-{i}"
    mut = D.detect(mutated)
    print(f"model_label_mutation_status={mut['status']}")
    if mut["fired"] != live["fired"] or mut["status"] != live["status"]:
        return fail("verdict changed after model-id mutation; model id leaked into the rule")
    if abs(mut["mean_pairwise_jaccard"] - live["mean_pairwise_jaccard"]) > 1e-9:
        return fail("similarity moved after model-id mutation")

    # Hard case is expected SILENT given these outputs. If it FIREd, that
    # would still be reported; we refuse only a silent retune in the receipt.
    if live["fired"]:
        return fail(
            "hard same-model strong-role outputs FIRE; fixtures are role-shaped "
            "and should be SILENT, or thresholds were tuned onto model identity"
        )

    collapsed = D.detect(collapsed_council())
    diverse = D.detect(diverse_council())
    if not collapsed["fired"] or diverse["fired"]:
        return fail("anchor pair collapsed/diverse no longer separates")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0320" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    required = [
        "unit_id",
        "artifact_paths",
        "spec_anchor",
        "evidence",
        "test_ids",
        "negative_control_ids",
        "reviewer_verdict",
        "residual_unknowns",
    ]
    missing = [k for k in required if k not in doc]
    if missing:
        return fail(f"receipt missing profile keys {missing}")

    reported = doc.get("hard_same_model_strong_roles") or {}
    if reported.get("fired") is not False:
        return fail("receipt overclaims FIRE on the hard case")
    if str(reported.get("status") or "").upper() != "SILENT":
        return fail("receipt does not honestly report SILENT on the hard case")
    if abs(float(reported.get("mean_pairwise_jaccard")) - live["mean_pairwise_jaccard"]) > 1e-6:
        return fail("receipt hard-case similarity does not match live detector")

    print(
        json.dumps(
            {
                "probe": "probe2-hard-case-vocab",
                "unit_id": "IMP-0320",
                "hard_status": "SILENT",
                "hard_fired": False,
                "role_vocab_rows": rows,
                "model_id_not_a_signal": True,
                "receipt_matches_live": True,
                "pass": True,
            }
        )
    )
    print("SUCCESS:IMP-0320-probe2 role-vocab per seat and honest same-model class")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
