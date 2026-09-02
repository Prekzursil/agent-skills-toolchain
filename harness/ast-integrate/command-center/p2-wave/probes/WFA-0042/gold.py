"""Build the 20-record gold set from A/B labels, kappa, and freeze protocol."""
from __future__ import annotations

from typing import Any

import labeller_a as A
import labeller_b as B
from dimensions import (
    DIMENSIONS,
    FAMILIES,
    GOLD_VERSION,
    KAPPA_FLOOR,
    N_GOLD,
    THIRD_READER_N,
    UNIT_ID,
    honest_null,
    label_key,
)
from io_source import load_source
from kappa import cohen_kappa, round6
from sampling_rule import load_selected, sampling_meta

# No extractor has been scored against this gold yet. First score freezes v1.
EXTRACTORS_SCORED: tuple[str, ...] = ()

# Dimensions where a singleton EVIDENCED from one labeller is not promoted.
CONSERVATIVE_DIMS = frozenset(
    {"benchmark_evidence", "failure_behaviour", "provenance"}
)


def _sources() -> list[dict[str, Any]]:
    rows = []
    for spec in load_selected():
        src = load_source(
            spec["abs_path"],
            rel=spec["path"],
            family=spec["family"],
            candidate_id=spec["candidate_id"],
        )
        src["index"] = spec["index"]
        src["third_reader"] = spec["third_reader"]
        rows.append(src)
    return rows


def reconcile(dim: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    if label_key(a) == label_key(b):
        gold = dict(a)
        gold["reconcile"] = "agree"
        return gold
    if a["cell_state"] == b["cell_state"] == "EVIDENCED":
        gold = dict(a)
        gold["reconcile"] = "same-state-prefer-A"
        gold["note"] = f"B value {b.get('value')!r}"
        return gold
    if dim in CONSERVATIVE_DIMS:
        gold = honest_null(note="A/B disagree; not promoted")
        gold["reconcile"] = "conservative-honest-null"
        return gold
    if a["cell_state"] == "EVIDENCED":
        gold = dict(a)
        gold["reconcile"] = "A-evidenced"
        return gold
    if b["cell_state"] == "EVIDENCED":
        gold = dict(b)
        gold["reconcile"] = "B-evidenced"
        return gold
    gold = dict(a)
    gold["reconcile"] = "prefer-A-non-evidenced"
    return gold


def per_dimension_kappa(
    a_labels: list[dict[str, dict[str, Any]]],
    b_labels: list[dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    unmeasurable: list[str] = []
    for dim in DIMENSIONS:
        series_a = [label_key(row[dim]) for row in a_labels]
        series_b = [label_key(row[dim]) for row in b_labels]
        kap = round6(cohen_kappa(series_a, series_b))
        measurable = kap >= KAPPA_FLOOR
        if not measurable:
            unmeasurable.append(dim)
        out[dim] = {
            "kappa": kap,
            "measurable": measurable,
            "verdict": "MEASURABLE" if measurable else "UNMEASURABLE",
            "n": len(series_a),
        }
    return {
        "per_dimension": out,
        "unmeasurable": unmeasurable,
        "kappa_floor": KAPPA_FLOOR,
        "aggregate_kappa": None,
        "aggregate_kappa_policy": (
            "null — catalog forbids averaging; UNMEASURABLE dims listed "
            "separately and never folded into one number"
        ),
    }


def family_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    seen = {r["family"] for r in records}
    missing = [f for f in FAMILIES if f not in seen]
    return {
        "required": list(FAMILIES),
        "seen": sorted(seen),
        "missing": missing,
        "complete": not missing,
        "n": len(records),
    }


def missing_family_mutant(records: list[dict[str, Any]]) -> dict[str, Any]:
    dropped = [r for r in records if r["family"] != "I-command"]
    cov = family_coverage(dropped)
    return {
        "id": "WFA-0042-MISSING-FAMILY-MUTANT",
        "fired_on_bad_state": not cov["complete"],
        "silent_on_good_state": family_coverage(records)["complete"],
        "missing": cov["missing"],
    }


def averaging_mutant(kappa_pack: dict[str, Any]) -> dict[str, Any]:
    vals = [row["kappa"] for row in kappa_pack["per_dimension"].values()]
    bogus = sum(vals) / len(vals) if vals else 0.0
    good_is_null = kappa_pack["aggregate_kappa"] is None
    has_unmeasurable = bool(kappa_pack["unmeasurable"])
    return {
        "id": "WFA-0042-LOW-KAPPA-AVERAGING-MUTANT",
        "would_be_aggregate": round6(bogus),
        "artifact_aggregate_kappa": kappa_pack["aggregate_kappa"],
        "fired_on_bad_state": has_unmeasurable and good_is_null,
        "silent_on_good_state": good_is_null,
        "unmeasurable": list(kappa_pack["unmeasurable"]),
        "note": (
            "Bad state = publish would_be_aggregate as THE kappa. "
            "Good state = aggregate_kappa stays null; UNMEASURABLE listed."
        ),
    }


def freeze_mutant(*, scored: tuple[str, ...] | None = None, bumped: bool = False) -> dict[str, Any]:
    scored_list = list(EXTRACTORS_SCORED if scored is None else scored)
    needs_bump = bool(scored_list)
    fired = needs_bump and not bumped
    silent = (not EXTRACTORS_SCORED) and GOLD_VERSION == 1
    return {
        "id": "WFA-0042-POST-SCORE-NO-BUMP-MUTANT",
        "gold_version": GOLD_VERSION,
        "extractors_scored": scored_list,
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent,
        "planted_scored": ["WFA-0032"] if scored is None else scored_list,
    }


def build_gold() -> dict[str, Any]:
    sources = _sources()
    if len(sources) != N_GOLD:
        raise RuntimeError(f"n={len(sources)} want {N_GOLD}")
    a_labels = [A.label_source(s) for s in sources]
    b_labels = [B.label_source(s) for s in sources]
    records = []
    for src, la, lb in zip(sources, a_labels, b_labels):
        dims = {dim: reconcile(dim, la[dim], lb[dim]) for dim in DIMENSIONS}
        records.append(
            {
                "candidate_id": src["candidate_id"],
                "family": src["family"],
                "path": src["path"],
                "sha256": src["sha256"],
                "bytes": src["bytes"],
                "third_reader": src["third_reader"],
                "labeller_a": {d: la[d] for d in DIMENSIONS},
                "labeller_b": {d: lb[d] for d in DIMENSIONS},
                "gold": dims,
            }
        )
    kappa_pack = per_dimension_kappa(a_labels, b_labels)
    cov = family_coverage(records)
    if not cov["complete"]:
        raise RuntimeError(f"family coverage missing {cov['missing']}")
    third_ids = [r["candidate_id"] for r in records if r["third_reader"]]
    if len(third_ids) != THIRD_READER_N:
        raise RuntimeError(f"third-reader n={len(third_ids)}")
    return {
        "unit_id": UNIT_ID,
        "gold_version": GOLD_VERSION,
        "extractors_scored": list(EXTRACTORS_SCORED),
        "frozen": True,
        "n": len(records),
        "sampling": sampling_meta(),
        "kappa": kappa_pack,
        "family_coverage": cov,
        "third_reader_ids": third_ids,
        "records": records,
        "negative_controls": {
            "missing_family": missing_family_mutant(records),
            "averaging": averaging_mutant(kappa_pack),
            "freeze": freeze_mutant(scored=("WFA-0032",), bumped=False),
        },
    }


def third_reader_ids() -> list[str]:
    return [r["candidate_id"] for r in build_gold()["records"] if r["third_reader"]]
