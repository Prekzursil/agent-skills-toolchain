"""Live nested vs flat experiment plus detector controls."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from fixtures import (
    agreeing_subcouncils,
    disagreeing_subcouncils,
    double_counted_subcouncils,
    flat_complete_receipts,
)
from mutants import PRIVATE_PREDICATE_SOURCE, averaging_fanin
from reducer import FANIN, predicate_fingerprint, reduce_completion, reduce_many
from topology import FLAT_FANIN, NESTED_FANIN, run_flat, run_nested

HERE = Path(__file__).resolve().parent
TOPOLOGY_SRC = (HERE / "topology.py").read_text(encoding="utf-8")


def _child_verdict_labels(result: dict[str, Any]) -> list[str]:
    return [c["verdict"] for c in result.get("subcouncil_verdicts") or []]


def fingerprints(trace: list[dict[str, Any]]) -> set[str]:
    return {t["predicate_fingerprint"] for t in trace if t.get("predicate_fingerprint")}


def predicate_ids(trace: list[dict[str, Any]]) -> set[int]:
    return {t["predicate_id"] for t in trace if "predicate_id" in t}


def ast_private_predicate(source: str) -> bool:
    """True when source defines a local completion function (the defect)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {
            "parent_complete",
            "local_complete",
            "average_complete",
            "majority_complete",
        }:
            return True
    return False


def production_absences() -> dict[str, bool]:
    repo = HERE.parents[3]
    return {
        "platform/lib/completion_predicate.py": (repo / "platform/lib/completion_predicate.py").is_file(),
        "tools/council/simulate.py": (repo / "tools/council/simulate.py").is_file(),
    }


def run_experiment() -> dict[str, Any]:
    disagree = run_nested(disagreeing_subcouncils())
    agree = run_nested(agreeing_subcouncils())
    doubled = run_nested(double_counted_subcouncils())
    flat_recs, flat_ids = flat_complete_receipts()
    flat = run_flat(flat_recs, flat_ids)

    labels = _child_verdict_labels(disagree)
    averaged = averaging_fanin(labels)

    fps_parent = fingerprints(disagree["trace"])
    fps_flat = fingerprints(flat["trace"])
    ids_parent = predicate_ids(disagree["trace"])
    ids_flat = predicate_ids(flat["trace"])

    same_object = FLAT_FANIN is NESTED_FANIN is FANIN is reduce_many
    same_fingerprint = fps_parent == fps_flat and len(fps_parent) == 1
    same_predicate_id = ids_parent == ids_flat and len(ids_parent) == 1

    planted_fires = ast_private_predicate(PRIVATE_PREDICATE_SOURCE)
    production_clean = not ast_private_predicate(TOPOLOGY_SRC)
    imports_shared = "from reducer import" in TOPOLOGY_SRC and "reduce_many" in TOPOLOGY_SRC

    disagreement_surfaced = (
        disagree["disagreement"] is True
        and disagree["verdict"] != "COMPLETE"
        and "COMPLETE" in labels
        and any(v != "COMPLETE" for v in labels)
        and averaged["verdict"] == "COMPLETE"
    )

    tally = disagree["tally"]
    tally_ok = (
        tally["tally_sum"] == tally["distinct_source_count"] == 2
        and tally["double_count"] is False
        and set(tally["source_ids"]) == {"sub-A", "sub-B"}
    )
    double_detected = doubled["tally"]["double_count"] is True and doubled["verdict"] != "COMPLETE"

    agree_clean = agree["verdict"] == "COMPLETE" and agree["disagreement"] is False
    flat_complete = flat["verdict"] == "COMPLETE"

    return {
        "disagree": disagree,
        "agree": agree,
        "doubled": doubled,
        "flat": flat,
        "averaged_mutant": averaged,
        "child_verdict_labels": labels,
        "same_fanin_object": same_object,
        "same_fingerprint_both_levels": same_fingerprint,
        "same_predicate_id_both_levels": same_predicate_id,
        "fingerprints": {"nested": sorted(fps_parent), "flat": sorted(fps_flat)},
        "predicate_ids": {"nested": sorted(ids_parent), "flat": sorted(ids_flat)},
        "reduce_completion_id": id(reduce_completion),
        "reduce_many_id": id(reduce_many),
        "predicate_fingerprint": predicate_fingerprint(),
        "planted_private_predicate_detected": planted_fires,
        "production_topology_has_no_private_predicate": production_clean,
        "topology_imports_shared_reducer": imports_shared,
        "disagreement_surfaced_not_averaged": disagreement_surfaced,
        "tally_ok": tally_ok,
        "double_count_detected": double_detected,
        "agree_completes_without_spurious_escalation": agree_clean,
        "flat_complete": flat_complete,
        "production_modules_present": production_absences(),
        "reducer_invocation_trace": disagree["trace"],
        "parent_tally_arithmetic": {
            **tally,
            "double_count_control": doubled["tally"],
            "compared_against_distinct_source_count": True,
        },
    }
