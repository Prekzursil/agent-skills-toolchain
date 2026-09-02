#!/usr/bin/env python3
"""Named probe 1: union(w, w) == w by fingerprint; naive concat fails.

Two signals:
  (1) union(w, rename(w)) fingerprint-equals w (idempotence, rename-invariant).
  (2) naive_concat(w, rename(w)) does NOT equal w — detector control against a
      concatenating implementation that would otherwise pass (1) if we special-
      cased identity-by-object.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fingerprint import (  # noqa: E402
    workflow_fingerprint,
    workflow_fingerprint_without_topology,
)
from scenario import fixtures_ok, workflow_w  # noqa: E402
from union_fusion import mutate_one_gate, naive_concat, rename_workflow, union_fuse  # noqa: E402

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


def main() -> int:
    fixtures_ok()
    w = workflow_w()
    w2 = rename_workflow(w)
    fused = union_fuse(w, w2)
    fused_self = union_fuse(w, w)
    concat = naive_concat(w, w2)
    mutant = mutate_one_gate(w)

    fp_w = workflow_fingerprint(w)
    fp_w2 = workflow_fingerprint(w2)
    fp_u = workflow_fingerprint(fused)
    fp_self = workflow_fingerprint(fused_self)
    fp_c = workflow_fingerprint(concat)
    fp_m = workflow_fingerprint(mutant)
    fp_w_notopo = workflow_fingerprint_without_topology(w)
    fp_m_notopo = workflow_fingerprint_without_topology(mutant)

    n_w = len(w["stages"])
    n_u = len(fused["stages"])
    n_c = len(concat["stages"])

    idempotent = fp_w == fp_w2 == fp_u == fp_self
    concat_differs = fp_c != fp_w
    stage_collapsed = n_u == n_w and n_c == 2 * n_w
    gate_changes = fp_m != fp_w
    # Detector: a fingerprint that dropped topology still sees the gate change
    # (gate lives on a stage). The concat control is the topology/multiplicity
    # one that naive union fails. Both must hold.
    notopo_still_sees_gate = fp_m_notopo != fp_w_notopo
    receipt = check_receipt()

    report = {
        "probe": "probe1-idempotence",
        "unit_id": UNIT,
        "fp_w": fp_w,
        "fp_renamed": fp_w2,
        "fp_union_renamed": fp_u,
        "fp_union_self": fp_self,
        "fp_naive_concat": fp_c,
        "fp_gate_mutant": fp_m,
        "stage_count_w": n_w,
        "stage_count_union": n_u,
        "stage_count_concat": n_c,
        "idempotent_by_fingerprint": idempotent,
        "naive_concat_differs": concat_differs,
        "duplicate_stages_collapsed": stage_collapsed,
        "gate_mutation_changes_fingerprint": gate_changes,
        "no_topology_fingerprint_still_sees_gate": notopo_still_sees_gate,
        "receipt": receipt,
        "pass": False,
    }
    ok = (
        idempotent
        and concat_differs
        and stage_collapsed
        and gate_changes
        and notopo_still_sees_gate
        and receipt == "ok"
    )
    report["pass"] = ok
    print(json.dumps(report, indent=1, sort_keys=True))
    if not ok:
        print(f"FAILED:{UNIT}-probe1 idempotence or concat-control")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 union(w,w)==w by fingerprint; naive concat refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
