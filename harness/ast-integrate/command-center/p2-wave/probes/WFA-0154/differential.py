"""Recorded-run vs reconstructed-blueprint stage/gate/stop differential.

Naive id-only equality is the known-bad comparator: it reports MATCH on a
pair whose stage[1] was mutated. The real comparator must name that index.
"""
from __future__ import annotations

from typing import Any

MATCH = "MATCH"
CONTRADICTED = "CONTRADICTED"
UNREPLAYABLE = "UNREPLAYABLE"


def naive_id_only(recorded: dict[str, Any] | None, reconstructed: dict[str, Any] | None) -> str:
    if not recorded or not reconstructed:
        return UNREPLAYABLE
    if recorded.get("candidate_id") and recorded.get("candidate_id") == reconstructed.get(
        "candidate_id"
    ):
        return MATCH
    return CONTRADICTED


def _norm_gate(g: Any) -> dict[str, Any]:
    if not isinstance(g, dict):
        return {"raw": g}
    return {
        "id": g.get("id"),
        "after_stage": g.get("after_stage"),
        "predicate": g.get("predicate"),
    }


def _norm_stop(s: Any) -> dict[str, Any]:
    if not isinstance(s, dict):
        return {"raw": s}
    return {
        "kind": s.get("kind"),
        "stage_index": s.get("stage_index"),
        "rule": s.get("rule"),
    }


def compare_pair(
    recorded: dict[str, Any] | None,
    reconstructed: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare one recorded execution to one reconstructed blueprint."""
    if recorded is None and reconstructed is None:
        return {
            "verdict": UNREPLAYABLE,
            "blocker": "missing-recorded-run-and-missing-blueprint",
            "transcript_record_id": None,
            "divergences": [],
            "first_divergence": None,
        }
    if recorded is None:
        return {
            "verdict": UNREPLAYABLE,
            "blocker": "missing-recorded-run",
            "transcript_record_id": None,
            "divergences": [],
            "first_divergence": None,
        }
    if reconstructed is None:
        return {
            "verdict": UNREPLAYABLE,
            "blocker": "missing-reconstructed-blueprint",
            "transcript_record_id": recorded.get("transcript_record_id"),
            "divergences": [],
            "first_divergence": None,
        }

    tid = recorded.get("transcript_record_id")
    divergences: list[dict[str, Any]] = []

    rec_s = list(recorded.get("stages") or [])
    rec_b = list(reconstructed.get("stages") or [])
    n_stages = max(len(rec_s), len(rec_b))
    for i in range(n_stages):
        a = rec_s[i] if i < len(rec_s) else None
        b = rec_b[i] if i < len(rec_b) else None
        if a != b:
            divergences.append(
                {
                    "axis": "stages",
                    "stage_index": i,
                    "transcript_record_id": tid,
                    "recorded": a,
                    "reconstructed": b,
                }
            )

    rec_g = [_norm_gate(g) for g in (recorded.get("gates") or [])]
    rec_gb = [_norm_gate(g) for g in (reconstructed.get("gates") or [])]
    n_gates = max(len(rec_g), len(rec_gb))
    for i in range(n_gates):
        a = rec_g[i] if i < len(rec_g) else None
        b = rec_gb[i] if i < len(rec_gb) else None
        if a != b:
            divergences.append(
                {
                    "axis": "gates",
                    "stage_index": (a or b or {}).get("after_stage") if isinstance(a or b, dict) else i,
                    "gate_index": i,
                    "transcript_record_id": tid,
                    "recorded": a,
                    "reconstructed": b,
                }
            )

    rec_stop = _norm_stop(recorded.get("stopping_point"))
    rec_stop_b = _norm_stop(reconstructed.get("stopping_point"))
    if rec_stop != rec_stop_b:
        divergences.append(
            {
                "axis": "stopping_point",
                "stage_index": rec_stop.get("stage_index"),
                "transcript_record_id": tid,
                "recorded": rec_stop,
                "reconstructed": rec_stop_b,
            }
        )

    first = divergences[0] if divergences else None
    return {
        "verdict": CONTRADICTED if divergences else MATCH,
        "blocker": None,
        "transcript_record_id": tid,
        "divergences": divergences,
        "first_divergence": first,
        "naive_id_only": naive_id_only(recorded, reconstructed),
    }


def mutate_stage(blueprint: dict[str, Any], index: int, new_name: str) -> dict[str, Any]:
    out = dict(blueprint)
    stages = list(out.get("stages") or [])
    if index < 0 or index >= len(stages):
        raise ValueError(f"stage index {index} out of range n={len(stages)}")
    stages[index] = new_name
    out["stages"] = stages
    return out


def replay_family(
    candidates: list[dict[str, Any]],
    blueprints: dict[str, dict[str, Any]],
    runs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for cand in candidates:
        cid = str(cand["id"])
        rec = runs.get(cid)
        bp = blueprints.get(cid)
        cmp = compare_pair(rec, bp)
        first = cmp.get("first_divergence")
        rows.append(
            {
                "candidate_id": cid,
                "family": cand.get("family"),
                "origin": cand.get("notes"),
                "verdict": cmp["verdict"],
                "blocker": cmp.get("blocker"),
                "transcript_record_id": cmp.get("transcript_record_id"),
                "first_divergence": first,
                "divergence_count": len(cmp.get("divergences") or []),
                "naive_id_only": cmp.get("naive_id_only"),
            }
        )
    return rows


def both_states_control(
    recorded: dict[str, Any],
    reconstructed: dict[str, Any],
    mutate_index: int = 1,
    mutant_name: str = "PLANTED-STAGE-MUTANT",
) -> dict[str, Any]:
    unaltered = compare_pair(recorded, reconstructed)
    mutated = mutate_stage(reconstructed, mutate_index, mutant_name)
    altered = compare_pair(recorded, mutated)
    naive = naive_id_only(recorded, mutated)
    named = None
    first = altered.get("first_divergence") or {}
    if first.get("axis") == "stages":
        named = first.get("stage_index")
    ok = (
        unaltered["verdict"] == MATCH
        and not unaltered["divergences"]
        and altered["verdict"] == CONTRADICTED
        and named == mutate_index
        and naive == MATCH
    )
    return {
        "pass": ok,
        "unaltered": {
            "verdict": unaltered["verdict"],
            "divergence_count": len(unaltered["divergences"]),
            "transcript_record_id": unaltered["transcript_record_id"],
        },
        "altered": {
            "verdict": altered["verdict"],
            "mutated_stage_index": mutate_index,
            "named_stage_index": named,
            "transcript_record_id": altered["transcript_record_id"],
            "recorded_stage": (first or {}).get("recorded"),
            "reconstructed_stage": (first or {}).get("reconstructed"),
        },
        "naive_id_only_on_altered": naive,
        "what": (
            "Unaltered reconstruction vs recorded run must MATCH with zero divergences. "
            f"Mutating reconstructed stages[{mutate_index}] must CONTRADICT and name that "
            "index. Naive candidate_id equality still reports MATCH on the mutant "
            "(false green)."
        ),
    }
