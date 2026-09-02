#!/usr/bin/env python3
"""Named probe 1 (evidence A): fused capability set == set-union of sources.

Computed over the mechanism incidence matrix. Both-states control: qualification
preserves the union; overwrite of colliding names silently drops a unique
mechanism (extract-text on alpha.ingest vs fetch-url on beta.ingest).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import load_conflict_edges, workflow_alpha, workflow_beta  # noqa: E402
from fusion_union import (  # noqa: E402
    capability_set,
    capability_union_holds,
    incidence_matrix,
    union_fuse,
    union_overwrite,
)

UNIT = "WFA-0102"
ART = REPO / "command-center/wfa/WFA-0102-fusion-union.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def artifact_status() -> str:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact-missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return "artifact-unparseable"
    if not isinstance(doc, dict):
        return "artifact-not-object"
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return f"self-declared:{st}"
    if "SUCCESS:WFA-0102" not in text:
        return "sentinel-absent"
    return "ok"


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    edges, origin = load_conflict_edges()
    alpha = workflow_alpha()
    beta = workflow_beta()
    fused = union_fuse(alpha, beta, edges=edges)
    overwritten = union_overwrite(alpha, beta)

    labeled = {"wf-alpha": alpha, "wf-beta": beta, "union": fused, "overwrite": overwritten}
    inc = incidence_matrix(labeled)
    caps_a = capability_set(alpha)
    caps_b = capability_set(beta)
    expected = caps_a | caps_b
    caps_u = capability_set(fused)
    caps_o = capability_set(overwritten)

    exact = caps_u == expected
    overwrite_loss = expected - caps_o
    overwrite_is_lossy = bool(overwrite_loss) and caps_o != expected
    holds = capability_union_holds(alpha, beta, fused)

    ingest_ids = [s["id"] for s in fused["stages"] if s["id"] == "ingest" or s["id"].endswith("::ingest")]
    qualified_ingest = any("::ingest" in s["id"] for s in fused["stages"])
    both_ingest_kept = len(ingest_ids) == 2

    receipt = artifact_status()
    report = {
        "probe": "probe1-capability-union",
        "unit_id": UNIT,
        "conflict_edge_origin": origin,
        "incidence_columns": inc["columns"],
        "capability_alpha": sorted(caps_a),
        "capability_beta": sorted(caps_b),
        "capability_union_expected": sorted(expected),
        "capability_fused": sorted(caps_u),
        "capability_overwrite": sorted(caps_o),
        "exact_set_union": exact,
        "overwrite_lossy": overwrite_is_lossy,
        "overwrite_missing": sorted(overwrite_loss),
        "qualified_colliding_ingest": qualified_ingest,
        "both_ingest_stages_kept": both_ingest_kept,
        "fused_stage_ids": [s["id"] for s in fused["stages"]],
        "overwrite_stage_ids": [s["id"] for s in overwritten["stages"]],
        "artifact": receipt,
        "pass": False,
    }
    ok = (
        exact
        and holds
        and overwrite_is_lossy
        and "extract-text" in overwrite_loss
        and both_ingest_kept
        and qualified_ingest
        and receipt == "ok"
    )
    report["pass"] = ok
    print(json.dumps(report, indent=2, sort_keys=True))
    if not ok:
        return fail("capability union or overwrite-control")
    print(
        f"SUCCESS:{UNIT}-probe1 fused caps == set-union via incidence; "
        f"overwrite dropped {sorted(overwrite_loss)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
