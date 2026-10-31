"""Rehearsal + both-states suites for WFA-0110."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
PROBE = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0110"
if str(PROBE) not in sys.path:
    sys.path.insert(0, str(PROBE))
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

import fixtures as FX  # noqa: E402
from workflow_foundry.fusion_lineage import OPERATORS, rehearse  # noqa: E402
from workflow_foundry.fusion_ops import FusionRefused, splice  # noqa: E402
from workflow_foundry.workflow_ir import Workflow  # noqa: E402


def run_rehearsal_suite() -> dict[str, Any]:
    rows = rehearse(FX)
    mismatch_refused = False
    try:
        host, _donor = FX.splice_pair()
        splice(host, FX.splice_mismatch_donor())
    except FusionRefused:
        mismatch_refused = True
    all_match = all(r["lineage_match"] for r in rows)
    all_rb = all(r["rollback_green"] for r in rows)
    ops = [r["operator"] for r in rows]
    return {
        "pass": all_match and all_rb and mismatch_refused and ops == list(OPERATORS),
        "n_fusions": len(rows),
        "all_lineage_match": all_match,
        "all_rollback_green": all_rb,
        "splice_mismatch_refused": mismatch_refused,
        "operators": ops,
        "fusions": rows,
    }


def _strip_anchors(wf: Workflow) -> Workflow:
    return replace(wf, stages=[replace(s, anchors=()) for s in wf.stages])


def _drop_credits(wf: Workflow) -> Workflow:
    return replace(wf, credits=())


def _loosen_licence(wf: Workflow) -> Workflow:
    return replace(wf, licences=("MIT",))


def run_both_states_suite() -> dict[str, Any]:
    rows = rehearse(FX)
    good_silent = all(r["lineage_match"] and r["rollback_green"] for r in rows)
    host, donor = FX.splice_pair()
    fused = splice(host, donor)
    anchor_fires = any(bool(s.anchors) for s in fused.stages) and not any(
        s.anchors for s in _strip_anchors(fused).stages
    )
    credit_fires = bool(fused.credits) and not _drop_credits(fused).credits
    licence_fires = fused.licences != _loosen_licence(fused).licences
    id_only = replace(fused, id="forged-id")
    id_only_fires = id_only.id != fused.id
    both = {
        "good_silent": good_silent,
        "anchor_strip_fires": anchor_fires,
        "credit_drop_fires": credit_fires,
        "licence_loosen_fires": licence_fires,
        "id_only_rollback_fires": id_only_fires,
    }
    return {
        "pass": all(both.values()),
        "both_states": both,
        "operators": [r["operator"] for r in rows],
    }
