#!/usr/bin/env python3
"""WFA-0103 best-of-breed fusion operator.

Per aligned stage slot, copy the implementation from the source with the
best measured matched-benchmark score. Selection cites a benchmark run id
and records the losing alternative's score. A TIED slot (no score
separation) is recorded as TIED and resolved by the written lexicographic
source_id rule in TIE-RULE.txt — never by LLM judgement or preference.

The score-only engine lives in tools/workflow_forge/best_of_breed.py
(IMP-0185). This module wraps it with WFA-0103's TIED recording, LLM-basis
refusal, and three-slot ablation rematerialization.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_forge.best_of_breed import (  # noqa: E402
    REPUTATION_NOT_EVIDENCE,
    TIED,
    FusionBuildError,
    ablate_second_best,
    build_best_of_breed,
    fuse_best_of_breed,
    selection_cites_run_ids,
)

WRITTEN_TIE_RULE_ID = "lexicographic-source-id"
LLM_BASIS = frozenset(
    {
        "llm_judgement",
        "llm_judgment",
        "model_preference",
        "reputation",
        "prefer_source",
    }
)
SLOTS = ("retrieve", "rank", "synthesize")


def written_tie_rule() -> str:
    return (HERE / "TIE-RULE.txt").read_text(encoding="utf-8")


def _refuse_llm_selection_basis(evidence: list[dict[str, Any]]) -> None:
    """Refuse rows that name LLM/preference as the selection basis."""
    for row in evidence:
        if not isinstance(row, dict):
            continue
        basis = str(row.get("selection_basis") or "").strip().lower()
        if basis in LLM_BASIS:
            raise FusionBuildError(
                REPUTATION_NOT_EVIDENCE,
                (
                    f"slot {row.get('slot_id')} source {row.get('source_id')} "
                    f"selection_basis={basis!r} is not a measured score"
                ),
                slot_id=row.get("slot_id"),
                source_id=row.get("source_id"),
                selection_basis=basis,
            )


def _annotate_ties(result: dict[str, Any]) -> dict[str, Any]:
    """Record lexicographic resolutions as TIED plus the written rule id."""
    rule = written_tie_rule()
    for row in result.get("selection_record") or []:
        if row.get("resolution") == WRITTEN_TIE_RULE_ID:
            row["resolution"] = "TIED"
            row["tie_rule"] = WRITTEN_TIE_RULE_ID
            row["tie_rule_text"] = rule.strip().splitlines()[0]
            losers = row.get("losers") or []
            if losers and float(losers[0]["score"]) == float(row["score"]):
                row["tied_sources"] = sorted(
                    [row["chosen_source_id"]] + [x["source_id"] for x in losers]
                )
    result["tie_rule_id"] = WRITTEN_TIE_RULE_ID
    result["tie_rule_path"] = (
        "command-center/p2-wave/probes/WFA-0103/TIE-RULE.txt"
    )
    return result


def fuse(
    sources: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    *,
    tie_rule: str = WRITTEN_TIE_RULE_ID,
    **kwargs: Any,
) -> dict[str, Any]:
    """Select per slot by measured score. Raises FusionBuildError on refusal."""
    _refuse_llm_selection_basis(evidence)
    result = fuse_best_of_breed(
        sources, evidence, tie_rule=tie_rule, **kwargs
    )
    return _annotate_ties(result)


def build(
    sources: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return fuse(sources, evidence, **kwargs)
    except FusionBuildError as exc:
        return exc.as_dict()


def rematerialize_composite(
    result: dict[str, Any], slot_id: str
) -> dict[str, Any]:
    """Substitute second-best into one slot and remeasure the composite.

    Composite is the sum of per-slot measured scores. Substituting a strictly
    worse score MUST move the composite; if it does not, that slot's selection
    was not evidence-driven.
    """
    ablation = ablate_second_best(result, slot_id)
    original = float(result["composite_score"])
    rematerialized = original - float(ablation["original_score"]) + float(
        ablation["ablated_score"]
    )
    moved = rematerialized != original
    fused_stages = {s["id"]: s for s in result["workflow"]["stages"]}
    original_stage = copy.deepcopy(fused_stages[slot_id])
    # Second-best implementation identity: different source_id recorded.
    return {
        "slot_id": slot_id,
        "original_source_id": ablation["original_source_id"],
        "original_score": ablation["original_score"],
        "ablated_source_id": ablation["ablated_source_id"],
        "ablated_score": ablation["ablated_score"],
        "original_composite": original,
        "rematerialized_composite": rematerialized,
        "composite_moved": moved,
        "delta": rematerialized - original,
        "original_stage_tools": list(original_stage.get("tools") or []),
        "benchmark_run_id": next(
            r["benchmark_run_id"]
            for r in result["selection_record"]
            if r["slot_id"] == slot_id
        ),
        "loser_score": ablation["ablated_score"],
        "loser_run_id": next(
            x["benchmark_run_id"]
            for r in result["selection_record"]
            if r["slot_id"] == slot_id
            for x in (r.get("losers") or [])
            if x["source_id"] == ablation["ablated_source_id"]
        ),
    }


def ablate_three_slots(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [rematerialize_composite(result, slot) for slot in SLOTS]


def case_hash_parity(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Matched-pair control: both arms of a slot must share case_hash."""
    by_slot: dict[str, set[str]] = {}
    for row in evidence:
        slot = str(row.get("slot_id") or "")
        digest = str(row.get("case_hash") or "")
        by_slot.setdefault(slot, set()).add(digest)
    mismatched = {
        slot: sorted(hashes)
        for slot, hashes in by_slot.items()
        if len(hashes) != 1 or not next(iter(hashes))
    }
    return {
        "slots": sorted(by_slot),
        "mismatched": mismatched,
        "ok": not mismatched and len(by_slot) >= 3,
    }


def fixture_bytes_hash(rel: str) -> str:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def fused_workflow_errors(workflow: dict[str, Any]) -> list[str]:
    sys.path.insert(0, str(REPO / "command-center" / "schema"))
    import validate_workflow as VW  # noqa: E402

    schema_errs: list[str] = []
    try:
        import jsonschema

        schema = VW.load_schema()
        schema_errs = [
            e.message for e in jsonschema.Draft7Validator(schema).iter_errors(workflow)
        ]
    except Exception as exc:  # pragma: no cover - environment
        schema_errs = [f"schema-load:{type(exc).__name__}:{exc}"]
    semantic, _ = VW.semantic_validate(workflow)
    return schema_errs + [f"{v['id']}:{v['detail']}" for v in semantic]


def selection_traces(result: dict[str, Any]) -> dict[str, Any]:
    """Every chosen slot cites a run id and records the loser's score."""
    cited = selection_cites_run_ids(result["selection_record"])
    missing_losers: list[str] = []
    for row in result["selection_record"]:
        losers = row.get("losers") or []
        if not losers or losers[0].get("score") is None:
            missing_losers.append(row["slot_id"])
    return {
        "cited": cited,
        "missing_loser_scores": missing_losers,
        "ok": bool(cited.get("ok")) and not missing_losers,
    }


def dump_compact(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)
