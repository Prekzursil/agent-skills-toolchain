"""Vendor/model diversity constraint solver with an explicit waiver record.

IMP-0272. The council's independence assumption rests on vendor/model spread.
When the reachable roster cannot meet the requested minimums, the council
still RUNS (best effort) but the run artifact must carry a waiver recording
independence_assumption=void; suppressing that waiver fails check_artifact.
"""
from __future__ import annotations

from typing import Any

WAIVER_REASON = "diversity-shortfall"
ASSUMPTION_INTACT = "intact"
ASSUMPTION_VOID = "void"
VIOLATION_WAIVER_MISSING = "waiver-missing"
VIOLATION_ASSUMPTION_NOT_VOID = "waiver-independence-not-void"
VIOLATION_SPURIOUS_WAIVER = "spurious-waiver"
VIOLATION_ASSUMPTION_MISMATCH = "assumption-mismatch"


def _vendor_model(seat: dict[str, Any]) -> tuple[str, str]:
    return str(seat.get("vendor") or "").casefold(), str(seat.get("model") or "").casefold()


def observed_diversity(seats: list[dict[str, Any]]) -> dict[str, int]:
    vendors = {str(s.get("vendor") or "").casefold() for s in seats} - {""}
    models = {str(s.get("model") or "").casefold() for s in seats} - {""}
    return {"vendors": len(vendors), "models": len(models)}


def _meets(observed: dict[str, int], request: dict[str, Any]) -> bool:
    return (
        observed["vendors"] >= int(request.get("min_vendors") or 1)
        and observed["models"] >= int(request.get("min_models") or 1)
    )


def _waiver(seats: list[dict[str, Any]], observed: dict[str, int], request: dict[str, Any]) -> dict[str, Any]:
    return {
        "waiver": True,
        "reason": WAIVER_REASON,
        "requested": {
            "min_vendors": int(request.get("min_vendors") or 1),
            "min_models": int(request.get("min_models") or 1),
        },
        "observed": {"vendors": observed["vendors"], "models": observed["models"]},
        "independence_assumption": ASSUMPTION_VOID,
        "seat_ids": [str(s.get("seat_id")) for s in seats],
    }


def solve(request: dict[str, Any], emit_waiver: bool = True) -> dict[str, Any]:
    """Best-effort seating under the diversity constraint.

    Feasible request: seats every reachable seat, no waiver, independence
    intact. Infeasible request (single reachable vendor, shared model, ...):
    the council still runs - every reachable seat is seated - and the artifact
    carries a waiver recording independence_assumption=void. With
    emit_waiver=False the waiver is suppressed (a MUTANT state that
    check_artifact must reject).
    """
    reachable = [dict(s) for s in (request.get("candidate_seats") or []) if s.get("reachable", True)]
    observed = observed_diversity(reachable)
    feasible = _meets(observed, request)
    artifact: dict[str, Any] = {
        "seats": reachable,
        "unseated_unreachable": [
            str(s.get("seat_id"))
            for s in (request.get("candidate_seats") or [])
            if not s.get("reachable", True)
        ],
        "requested": {
            "min_vendors": int(request.get("min_vendors") or 1),
            "min_models": int(request.get("min_models") or 1),
        },
        "observed_diversity": observed,
        "feasible": feasible,
        "independence_assumption": ASSUMPTION_INTACT if feasible else ASSUMPTION_VOID,
        "emit_waiver": emit_waiver,
        "waiver": None,
    }
    if not feasible:
        if emit_waiver:
            artifact["waiver"] = _waiver(reachable, observed, request)
        artifact["waiver_suppressed"] = not emit_waiver
    return artifact


def check_artifact(artifact: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Mechanical check: shortfall requires a void-independence waiver.

    Whenever the observed vendor/model diversity of the artifact's seats is
    below the request, the artifact must carry a waiver whose
    independence_assumption is void and whose observed/requested numbers match
    this recomputation. A satisfying artifact must NOT carry a waiver.
    """
    seats = list(artifact.get("seats") or [])
    observed = observed_diversity(seats)
    violations: list[dict[str, str]] = []
    if not _meets(observed, request):
        waiver = artifact.get("waiver")
        if not isinstance(waiver, dict) or not waiver:
            violations.append(
                {
                    "id": VIOLATION_WAIVER_MISSING,
                    "detail": (
                        f"diversity {observed} below request {request.get('min_vendors')}x"
                        f"{request.get('min_models')} and no waiver present"
                    ),
                }
            )
        else:
            if str(waiver.get("independence_assumption")) != ASSUMPTION_VOID:
                violations.append(
                    {"id": VIOLATION_ASSUMPTION_NOT_VOID, "detail": "waiver does not record independence void"}
                )
            if dict(waiver.get("observed") or {}) != observed:
                violations.append({"id": "waiver-observed-mismatch", "detail": "waiver observed != recomputed"})
    else:
        if artifact.get("waiver"):
            violations.append({"id": VIOLATION_SPURIOUS_WAIVER, "detail": "constraint met but waiver present"})
        if artifact.get("independence_assumption") not in (None, ASSUMPTION_INTACT):
            violations.append({"id": VIOLATION_ASSUMPTION_MISMATCH, "detail": "constraint met but assumption not intact"})
    return {"ok": not violations, "observed_diversity": observed, "violations": violations}
