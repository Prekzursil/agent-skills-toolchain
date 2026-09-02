"""Benchmark-gaming detector: does the metric move without the mechanism?

GAMEABLE  — null-change delta is significant: replace the metric, name it.
INERT     — mechanism-change delta is not significant: measured-nothing.
HONEST    — null stays inside the band, mechanism leaves it.
"""
from __future__ import annotations

from typing import Any

import harness as H
import stats as S


def classify(null_delta: float, mech_delta: float, band: float) -> str:
    if S.significant(null_delta, band):
        return "GAMEABLE"
    if not S.significant(mech_delta, band):
        return "INERT"
    return "HONEST"


def measure_one(name: str, n_runs: int = H.N_RUNS) -> dict[str, Any]:
    meta = next(b for b in H.BENCHMARKS if b["name"] == name)
    n_in_b, raw_b = H.sample_runs(name, "baseline", n_runs)
    n_in_n, raw_n = H.sample_runs(name, "null", n_runs)
    n_in_m, raw_m = H.sample_runs(name, "mechanism", n_runs)
    n_inputs = min(n_in_b, n_in_n, n_in_m)
    if n_inputs < 1:
        raise H.EmptyInputError(f"{name}: n_inputs={n_inputs}")
    base = S.rederive(raw_b)
    null = S.rederive(raw_n)
    mech = S.rederive(raw_m)
    # Band from the baseline raw numbers, not from a pre-baked summary.
    band = base["mde"]
    null_delta = null["mean"] - base["mean"]
    mech_delta = mech["mean"] - base["mean"]
    verdict = classify(null_delta, mech_delta, band)
    return {
        "name": name,
        "metric_id": meta["metric_id"],
        "surface": meta["surface"],
        "n_inputs": n_inputs,
        "n_runs": n_runs,
        "seed": H.SEED,
        "null_change": meta["null_change"],
        "mechanism_change": meta["mechanism_change"],
        "planted": bool(meta.get("planted")),
        "replace_with": meta.get("replace_with"),
        "variance_band": {
            "computed_not_asserted": True,
            "source": "baseline.raw",
            "n": base["n"],
            "mean": base["mean"],
            "std": base["std"],
            "mde": band,
        },
        "baseline": {
            "mean": base["mean"],
            "std": base["std"],
            "raw": list(raw_b),
        },
        "null_change_sample": {
            "mean": null["mean"],
            "std": null["std"],
            "raw": list(raw_n),
            "delta": null_delta,
            "significant": S.significant(null_delta, band),
        },
        "mechanism_change_sample": {
            "mean": mech["mean"],
            "std": mech["std"],
            "raw": list(raw_m),
            "delta": mech_delta,
            "significant": S.significant(mech_delta, band),
        },
        "verdict": verdict,
        "expected": meta["expected"],
    }


def measure_all(n_runs: int = H.N_RUNS) -> dict[str, Any]:
    rows = [measure_one(b["name"], n_runs) for b in H.BENCHMARKS]
    gameable = [r["name"] for r in rows if r["verdict"] == "GAMEABLE"]
    inert = [r["name"] for r in rows if r["verdict"] == "INERT"]
    honest = [r["name"] for r in rows if r["verdict"] == "HONEST"]
    expected_ok = all(r["verdict"] == r["expected"] for r in rows)
    empty = {b["name"]: H.empty_input_control(b["name"]) for b in H.BENCHMARKS}
    empty_ok = all(v == "EmptyInputError" for v in empty.values())
    return {
        "seed": H.SEED,
        "n_runs": n_runs,
        "rows": rows,
        "gameable_named": gameable,
        "inert_named": inert,
        "honest_named": honest,
        "expected_ok": expected_ok,
        "empty_input_control": empty,
        "empty_input_ok": empty_ok,
    }


def receipt_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields sit on report/extensions (receipt_core additionalProperties false)."""
    out = dict(doc)
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        out.update(ext)
    report = doc.get("report")
    if isinstance(report, dict):
        out.update(report)
    return out


def receipt_benchmarks(measured: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for r in measured["rows"]:
        ns = r["null_change_sample"]
        ms = r["mechanism_change_sample"]
        out.append(
            {
                "name": r["name"],
                "metric_id": r["metric_id"],
                "surface": r["surface"],
                "n_inputs": r["n_inputs"],
                "n_runs": r["n_runs"],
                "planted": r["planted"],
                "replace_with": r.get("replace_with"),
                "variance_band": r["variance_band"],
                "baseline": r["baseline"],
                "null_change": {
                    "mean": ns["mean"],
                    "std": ns["std"],
                    "raw": ns["raw"],
                    "delta": ns["delta"],
                    "significant": ns["significant"],
                    "description": r["null_change"],
                },
                "mechanism_change": {
                    "mean": ms["mean"],
                    "std": ms["std"],
                    "raw": ms["raw"],
                    "delta": ms["delta"],
                    "significant": ms["significant"],
                    "description": r["mechanism_change"],
                },
                "verdict": r["verdict"],
                "expected": r["expected"],
            }
        )
    return out
