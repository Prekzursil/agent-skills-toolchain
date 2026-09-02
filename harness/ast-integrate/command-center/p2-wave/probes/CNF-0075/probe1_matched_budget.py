#!/usr/bin/env python3
"""Probe 1: re-run fusion and every source at equal budget; require stage counts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    BUDGET_LIMIT,
    CASES,
    FUSION,
    fusion_union,
    source_retrieve,
    source_transform,
)
from gates import measure_subject  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0075-fusion-superiority.json"
SCHEMA = REPO / "command-center/schema/benchmark-report.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0075-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = (
        "SUCCESS:CNF-0075 emitted only when the artifact at output_path exists, is "
        "non-empty, parses against output_schema, and the score matrix records equal "
        "budgets and includes stage counts for the fusion and every source."
    )
    if sentinel not in text:
        return fail("completion sentinel absent")

    live = measure_subject(
        fusion_union(),
        [source_retrieve(), source_transform()],
        CASES,
        BUDGET_LIMIT,
    )
    matrix = live["matrix"]
    if not matrix["budget_parity"]["equal"]:
        return fail("live budget parity false")
    limits = {c["budget_limit"] for c in matrix["cells"]}
    if limits != {float(BUDGET_LIMIT)}:
        return fail(f"cell budget limits {limits}")

    art_matrix = doc.get("score_matrix") or {}
    art_cells = {(c["workflow_id"], c["case_id"]): c for c in art_matrix.get("cells") or []}
    if len(art_cells) != len(matrix["cells"]):
        return fail(f"cell count {len(art_cells)} != {len(matrix['cells'])}")
    for cell in matrix["cells"]:
        key = (cell["workflow_id"], cell["case_id"])
        got = art_cells.get(key)
        if not got:
            return fail(f"missing cell {key}")
        if float(got["score"]) != float(cell["score"]):
            return fail(f"score drift {key} {got['score']} != {cell['score']}")
        if float(got["budget_limit"]) != float(cell["budget_limit"]):
            return fail(f"budget drift {key}")
        if int(got["stage_count"]) != int(cell["stage_count"]):
            return fail(f"stage_count drift {key}")

    stage_counts = doc.get("stage_counts") or {}
    fusion_sc = (stage_counts.get("fusion") or {}).get("stage_count")
    source_scs = [
        int(s["stage_count"]) for s in (stage_counts.get("sources") or []) if "stage_count" in s
    ]
    if fusion_sc is None or len(source_scs) < 2:
        return fail("stage_counts incomplete")
    live_fusion = next(w for w in matrix["workflows"] if w["id"] == FUSION)
    if int(fusion_sc) != int(live_fusion["stage_count"]):
        return fail("fusion stage_count drift")
    if not doc.get("budget_parity", {}).get("equal"):
        return fail("artifact budget_parity.equal is not true")

    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    print(
        json.dumps(
            {
                "probe": "probe1-matched-budget",
                "unit_id": "CNF-0075",
                "cells": len(matrix["cells"]),
                "budget_limit": BUDGET_LIMIT,
                "budget_parity": True,
                "fusion_stage_count": int(fusion_sc),
                "source_stage_counts": source_scs,
                "fusion_pass_rate": live_fusion["pass_rate"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "cells={0} budget_limit={1} fusion_stages={2} source_stages={3}".format(
            len(matrix["cells"]),
            BUDGET_LIMIT,
            fusion_sc,
            source_scs,
        )
    )
    print("SUCCESS:CNF-0075-probe1 matched-budget rerun with stage counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
