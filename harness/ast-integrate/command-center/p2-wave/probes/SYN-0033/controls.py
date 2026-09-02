"""Named detector controls required by SYN-0033."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sweep import sweep, verdict_for

HERE = Path(__file__).resolve().parent
PLANTED_REG = HERE / "fixtures" / "planted" / "CLAIM-REGISTRY.json"
PLANTED_ADJ = HERE / "fixtures" / "planted" / "SYN-0011.adjudications.json"
EMPTY_REG = HERE / "fixtures" / "empty" / "CLAIM-REGISTRY.json"
EMPTY_ADJ = HERE / "fixtures" / "empty" / "SYN-0011.adjudications.json"

PLANTED_OPEN = "C-P10-MEASURE-D17::C-P2-RESEARCH-D17"
PLANTED_SETTLED = "C-P11-CONFIRMER-Y::C-P5-NOTE-Y"
INTRA_PAIR = "C-P5-IMPL-X::C-P5-IMPL-X-NEG"
SCOPED_PAIR = "C-P10-COUNT-B::C-P2-COUNT-A"


def planted_sweep() -> dict[str, Any]:
    return sweep(PLANTED_REG, PLANTED_ADJ)


def empty_sweep() -> dict[str, Any]:
    return sweep(EMPTY_REG, EMPTY_ADJ)


def planted_cross_phase_detected() -> dict[str, Any]:
    result = planted_sweep()
    ids = set(result["open_ids"])
    ok = PLANTED_OPEN in ids
    return {
        "ok": ok,
        "open_ids": result["open_ids"],
        "examined": result["examined_pair_count"],
        "result": result,
    }


def intra_phase_excluded() -> dict[str, Any]:
    result = planted_sweep()
    reported = {row["id"] for row in result["contradictions"]}
    skipped = set(result["intra_exclusive_skipped"])
    ok = INTRA_PAIR not in reported and INTRA_PAIR in skipped
    return {
        "ok": ok,
        "reported": sorted(reported),
        "intra_exclusive_skipped": result["intra_exclusive_skipped"],
        "intra_phase_pairs_excluded": result["counts"]["intra_phase_pairs_excluded"],
        "result": result,
    }


def settled_not_reopened() -> dict[str, Any]:
    result = planted_sweep()
    by_id = {row["id"]: row for row in result["contradictions"]}
    row = by_id.get(PLANTED_SETTLED)
    ok = (
        row is not None
        and row.get("status") == "SETTLED"
        and row.get("already_adjudicated") is True
        and PLANTED_SETTLED not in result["open_ids"]
    )
    return {
        "ok": ok,
        "row": row,
        "settled_ids": result["settled_ids"],
        "open_ids": result["open_ids"],
        "result": result,
    }


def scoped_differently_silent() -> dict[str, Any]:
    result = planted_sweep()
    reported = {row["id"] for row in result["contradictions"]}
    ok = SCOPED_PAIR not in reported
    return {
        "ok": ok,
        "reported": sorted(reported),
        "scoped_differently_skipped": result["counts"]["scoped_differently_skipped"],
        "result": result,
    }


def empty_zero_has_denominator() -> dict[str, Any]:
    result = empty_sweep()
    verdict = verdict_for(result)
    ok = (
        result["examined_pair_count"] == 0
        and result["counts"]["claims_loaded"] == 0
        and verdict == "NOT-CHECKED"
        and result["open_contradictions_all_named_settling_probe"] is True
    )
    return {
        "ok": ok,
        "examined": result["examined_pair_count"],
        "claims_loaded": result["counts"]["claims_loaded"],
        "verdict": verdict,
        "result": result,
    }


def open_rows_name_settling_probe() -> dict[str, Any]:
    result = planted_sweep()
    missing = [
        row["id"]
        for row in result["contradictions"]
        if row["status"] == "OPEN" and len(str(row.get("settling_probe") or "")) < 8
    ]
    ok = not missing and result["open_contradictions_all_named_settling_probe"] is True
    return {"ok": ok, "missing": missing, "open_ids": result["open_ids"]}


def all_controls() -> dict[str, Any]:
    parts = {
        "planted_detected": planted_cross_phase_detected(),
        "intra_excluded": intra_phase_excluded(),
        "settled_not_reopened": settled_not_reopened(),
        "scoped_silent": scoped_differently_silent(),
        "empty_denominator": empty_zero_has_denominator(),
        "open_named_probe": open_rows_name_settling_probe(),
    }
    ok = all(part.get("ok") for part in parts.values())
    return {"ok": ok, "parts": parts}
