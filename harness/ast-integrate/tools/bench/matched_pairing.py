"""Matched-case pairing: compare a fusion with its sources on identical inputs (TST-0296).

Phase 2B step 7 runs source workflows and fused candidates on matched benchmark cases and
certifies only fusions that outperform or materially complement their sources.  The
pairing rule implemented here selects the case subset **every source can actually run**
(an intersection, never a union), records every excluded case with the reason, publishes
fusion-only "complementarity" cases separately, and refuses a head-to-head whose
intersection is below a minimum size.  Scoring a fusion on cases its sources cannot even
attempt is the arithmetic that manufactures a winner, so the engine never crowns one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PAIRING_RULE = "intersection-not-union"
DEFAULT_MIN_INTERSECTION = 10
STATUS_COMPARABLE = "COMPARABLE"
STATUS_BLOCKED_LOW_N = "BLOCKED_LOW_N"
BLOCK_REASON_LOW_N = "intersection_below_minimum"
COMPLEMENTARITY_DEFINITION = "fusion runnable minus union of source runnables"
HEAD_TO_HEAD_NOTE = "pairing selects the case subset; it does not crown a winner"
UNION_NOTE = (
    "Scoring on the union (or folding complementarity) credits the fusion for cases at "
    "least one source cannot attempt."
)


class PairingError(ValueError):
    """Raised when a comparison is malformed or asks for a forbidden fold."""


# --------------------------------------------------------------------------- capability model
def _caps(obj: Mapping[str, Any], key: str) -> frozenset[str]:
    raw = obj.get(key)
    if raw is None:
        raise PairingError(f"{obj.get('id', '<unnamed>')!r} has no {key!r} list")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, Iterable):
        raise PairingError(f"{key!r} of {obj.get('id')!r} is not a list")
    return frozenset(str(c) for c in raw)


def can_run(workflow: Mapping[str, Any], case: Mapping[str, Any]) -> bool:
    """True when every capability the case requires is one the workflow declares."""
    return _caps(case, "required_capabilities") <= _caps(workflow, "capabilities")


def runnable_ids(
    workflow: Mapping[str, Any], cases: Sequence[Mapping[str, Any]]
) -> set[str]:
    """Ids of the cases ``workflow`` can attempt."""
    return {str(c["id"]) for c in cases if can_run(workflow, c)}


# --------------------------------------------------------------------------- scenario loading
def expand_lanes(lanes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Expand ``capability_lanes`` into concrete cases ``<id_prefix>NN`` (1-based)."""
    cases: list[dict[str, Any]] = []
    for lane in lanes:
        cap = str(lane["capability"])
        count = int(lane.get("count", 0))
        prefix = str(lane.get("id_prefix") or f"C-{cap}-")
        if count < 0:
            raise PairingError(f"lane {cap!r} has negative count {count}")
        for i in range(1, count + 1):
            cases.append(
                {
                    "id": f"{prefix}{i:02d}",
                    "lane": cap,
                    "required_capabilities": [cap],
                }
            )
    return cases


def _validate_cases(cases: Sequence[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for case in cases:
        cid = case.get("id")
        if cid is None or str(cid) == "":
            raise PairingError("case without id")
        if str(cid) in seen:
            raise PairingError(f"duplicate case id {cid!r}")
        seen.add(str(cid))
        _caps(case, "required_capabilities")


def load_scenario(path: Path | str) -> dict[str, Any]:
    """Load a pairing scenario; workflows are returned as a dict keyed by id.

    Cases come from ``cases`` when present, otherwise from ``capability_lanes``.
    """
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, Mapping):
        raise PairingError(f"scenario {path} is not an object")
    if isinstance(doc.get("cases"), list) and doc["cases"]:
        cases = [dict(c) for c in doc["cases"]]
    else:
        cases = expand_lanes(doc.get("capability_lanes") or [])
    _validate_cases(cases)
    raw_wf = doc.get("workflows") or []
    workflows: dict[str, dict[str, Any]] = {}
    items = (
        raw_wf.items()
        if isinstance(raw_wf, Mapping)
        else ((w.get("id"), w) for w in raw_wf)
    )
    for wid, wf in items:
        if not wid:
            raise PairingError("workflow without id")
        if str(wid) in workflows:
            raise PairingError(f"duplicate workflow id {wid!r}")
        row = dict(wf)
        row.setdefault("id", str(wid))
        _caps(row, "capabilities")
        workflows[str(wid)] = row
    comparisons = [dict(c) for c in (doc.get("comparisons") or [])]
    return {
        "id": doc.get("id"),
        "note": doc.get("note"),
        "capability_lanes": list(doc.get("capability_lanes") or []),
        "cases": cases,
        "workflows": workflows,
        "comparisons": comparisons,
    }


# --------------------------------------------------------------------------- pairing engine
def _exclusion_row(
    case: Mapping[str, Any],
    source_ids: Sequence[str],
    missing: Sequence[str],
    fusion_can: bool,
) -> dict[str, Any]:
    if len(missing) == len(source_ids):
        if fusion_can:
            reason = "fusion_only_complementarity: no source can attempt this case"
        else:
            reason = "no_source_can_run:" + ",".join(missing)
    else:
        reason = "source_cannot_run:" + ",".join(missing)
    return {
        "case_id": str(case["id"]),
        "required_capabilities": sorted(_caps(case, "required_capabilities")),
        "missing_sources": list(missing),
        "fusion_can_run": fusion_can,
        "reason": reason,
    }


def pair_comparison(
    *,
    cases: Sequence[Mapping[str, Any]],
    workflows: Mapping[str, Mapping[str, Any]],
    fusion_id: str,
    source_ids: Sequence[str],
    min_intersection: int = DEFAULT_MIN_INTERSECTION,
    comparison_id: str | None = None,
    fold_complementarity: bool = False,
) -> dict[str, Any]:
    """Pair one fusion against its sources on the cases every source can run.

    Returns the published comparison row.  ``fold_complementarity=True`` is refused with a
    :class:`PairingError` because folding fusion-only cases into the head-to-head is the
    exact inflation the rule exists to prevent.
    """
    if fold_complementarity:
        raise PairingError(
            "complementarity_fold_forbidden: fusion-only cases must be published separately, "
            "never folded into the head-to-head score"
        )
    if not source_ids:
        raise PairingError("a comparison needs at least one source workflow")
    if fusion_id in source_ids:
        raise PairingError(f"fusion {fusion_id!r} cannot also be one of its sources")
    if int(min_intersection) < 1:
        raise PairingError(f"min_intersection must be >= 1, got {min_intersection!r}")
    missing_wf = [w for w in (fusion_id, *source_ids) if w not in workflows]
    if missing_wf:
        raise PairingError(f"unknown workflow ids: {missing_wf}")
    _validate_cases(cases)
    fusion = workflows[fusion_id]
    sources = [workflows[s] for s in source_ids]

    # Signal 1: set intersection of expanded runnable-id sets.
    per_source = {s: runnable_ids(workflows[s], cases) for s in source_ids}
    inter_sets = set.intersection(*per_source.values()) if per_source else set()
    # Signal 2 (independent): per-case scan requiring every source to run it.
    inter_scan = {str(c["id"]) for c in cases if all(can_run(w, c) for w in sources)}
    if inter_sets != inter_scan:
        raise PairingError(
            "intersection signals disagree; refusing to publish a pairing"
        )
    intersection = sorted(inter_sets)

    fusion_runnable = runnable_ids(fusion, cases)
    source_union = set.union(*per_source.values()) if per_source else set()
    complementarity_ids = sorted(fusion_runnable - source_union)

    excluded: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda c: str(c["id"])):
        cid = str(case["id"])
        if cid in inter_sets:
            continue
        missing = [s for s in source_ids if not can_run(workflows[s], case)]
        excluded.append(
            _exclusion_row(case, source_ids, missing, cid in fusion_runnable)
        )

    size = len(intersection)
    comparable = size >= int(min_intersection)
    status = STATUS_COMPARABLE if comparable else STATUS_BLOCKED_LOW_N
    head_to_head = (
        {"case_ids": intersection, "n": size, "score": None, "note": HEAD_TO_HEAD_NOTE}
        if comparable
        else None
    )
    return {
        "comparison_id": comparison_id or f"{fusion_id}-vs-{'+'.join(source_ids)}",
        "pairing_rule": PAIRING_RULE,
        "fusion_id": fusion_id,
        "source_ids": list(source_ids),
        "corpus_size": len(cases),
        "min_intersection": int(min_intersection),
        "per_source_runnable_size": {s: len(ids) for s, ids in per_source.items()},
        "fusion_runnable_size": len(fusion_runnable),
        "intersection_size": size,
        "intersection_case_ids": intersection,
        "signals": {
            "set_intersection": intersection,
            "per_case_all_can_run": sorted(inter_scan),
            "agree": True,
        },
        "excluded": excluded,
        "excluded_count": len(excluded),
        "complementarity": {
            "definition": COMPLEMENTARITY_DEFINITION,
            "case_ids": complementarity_ids,
            "count": len(complementarity_ids),
            "folded_into_head_to_head": False,
        },
        "union_inflation_diagnostic": {
            "source_union_case_ids": sorted(source_union),
            "source_union_size": len(source_union),
            "extra_in_source_union_vs_intersection": sorted(source_union - inter_sets),
            "fusion_runnable_outside_intersection": sorted(
                fusion_runnable - inter_sets
            ),
            "manufactures_fusion_win": bool(fusion_runnable - inter_sets),
            "not_used_for_official_result": True,
            "note": UNION_NOTE,
        },
        "comparison_status": status,
        "block_reason": None if comparable else BLOCK_REASON_LOW_N,
        "head_to_head": head_to_head,
        "reported_win": False,
        "winner": None,
    }


def pair_scenario(scenario: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Pair every comparison declared in a loaded scenario."""
    cases = scenario["cases"]
    workflows = scenario["workflows"]
    rows: list[dict[str, Any]] = []
    for cmp in scenario.get("comparisons") or []:
        rows.append(
            pair_comparison(
                cases=cases,
                workflows=workflows,
                fusion_id=str(cmp["fusion"]),
                source_ids=[str(s) for s in cmp["sources"]],
                min_intersection=int(
                    cmp.get("min_intersection", DEFAULT_MIN_INTERSECTION)
                ),
                comparison_id=str(cmp["id"]) if cmp.get("id") else None,
            )
        )
    return rows


__all__ = [
    "BLOCK_REASON_LOW_N",
    "DEFAULT_MIN_INTERSECTION",
    "PAIRING_RULE",
    "PairingError",
    "STATUS_BLOCKED_LOW_N",
    "STATUS_COMPARABLE",
    "can_run",
    "expand_lanes",
    "load_scenario",
    "pair_comparison",
    "pair_scenario",
    "runnable_ids",
]
