#!/usr/bin/env python3
"""Named probe 2: union(a,b) coverage is a superset of a and of b.

Two signals:
  (1) coverage-vector(union(a,b)) componentwise >= coverage(a) and coverage(b).
  (2) dropping B's unique emit stage from the fusion makes the superset check
      fail — detector control against a vacuous 'always true' comparator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from coverage import coverage_vector, is_superset, missing_from_superset  # noqa: E402
from fingerprint import stage_fingerprint, workflow_fingerprint  # noqa: E402
from scenario import fixtures_ok, workflow_a, workflow_b  # noqa: E402
from union_fusion import drop_stage, naive_concat, union_fuse  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0184.json"
UNIT = "IMP-0184"


def check_receipt() -> str:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt-missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return "receipt-unparseable"
    if not isinstance(doc, dict):
        return "receipt-not-object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    if "SUCCESS:IMP-0184" not in text:
        return "sentinel-absent"
    return "ok"


def emit_stage_id(fused: dict) -> str:
    for stage in fused["stages"]:
        if stage.get("kind") == "emit":
            return str(stage["id"])
    raise AssertionError("union lost emit stage before the lossy control")


def main() -> int:
    fixtures_ok()
    a = workflow_a()
    b = workflow_b()
    fused = union_fuse(a, b)
    fused_ba = union_fuse(b, a)
    concat = naive_concat(a, b)

    cov_a = coverage_vector(a)
    cov_b = coverage_vector(b)
    cov_u = coverage_vector(fused)
    cov_c = coverage_vector(concat)

    super_a = is_superset(cov_u, cov_a)
    super_b = is_superset(cov_u, cov_b)
    concat_also_super = is_superset(cov_c, cov_a) and is_superset(cov_c, cov_b)

    ingest_collapsed = (
        stage_fingerprint(a["stages"][0]) == stage_fingerprint(b["stages"][0])
        and len(fused["stages"]) == 3
        and len(concat["stages"]) == 4
    )
    commutative_fp = workflow_fingerprint(fused) == workflow_fingerprint(fused_ba)

    lossy = drop_stage(fused, emit_stage_id(fused))
    cov_lossy = coverage_vector(lossy)
    lossy_fails_b = not is_superset(cov_lossy, cov_b)
    lossy_missing = missing_from_superset(cov_lossy, cov_b)
    receipt = check_receipt()

    report = {
        "probe": "probe2-capability-superset",
        "unit_id": UNIT,
        "coverage_a": cov_a,
        "coverage_b": cov_b,
        "coverage_union": cov_u,
        "superset_of_a": super_a,
        "superset_of_b": super_b,
        "naive_concat_also_superset": concat_also_super,
        "shared_ingest_collapsed": ingest_collapsed,
        "union_commutative_by_fingerprint": commutative_fp,
        "lossy_drop_emit_fails_superset_b": lossy_fails_b,
        "lossy_missing_capabilities": lossy_missing,
        "receipt": receipt,
        "pass": False,
    }
    ok = (
        super_a
        and super_b
        and concat_also_super
        and ingest_collapsed
        and commutative_fp
        and lossy_fails_b
        and "build.emit" in lossy_missing
        and receipt == "ok"
    )
    report["pass"] = ok
    print(json.dumps(report, indent=1, sort_keys=True))
    if not ok:
        print(f"FAILED:{UNIT}-probe2 coverage superset or lossy-control")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe2 union coverage superset of both parents; "
        "lossy drop of build.emit fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
