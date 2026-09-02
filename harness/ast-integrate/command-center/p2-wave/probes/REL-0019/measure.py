"""Measure false-positive / false-negative rates on labelled fixtures.

Rates are k/n with a Wilson 95% interval. A promote threshold is assigned
only when both class denominators meet MIN_SAMPLE. Below that the decision
is SAMPLE-TOO-SMALL and threshold is left null (never rounded).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fixtures import GATE_ORDER, load_all  # noqa: E402
from gates import evaluate, source_module  # noqa: E402

MIN_SAMPLE = 20
FP_BUDGET = 0.20
FN_BUDGET = 0.25
WILSON_Z = 1.95996398454
DEFAULT_SEED = 11130
ALWAYS_ACCEPT_GATE = "drift_detector"


def wilson_interval(k: int, n: int, z: float = WILSON_Z) -> tuple[float, float]:
    if n <= 0:
        raise ValueError("wilson_interval requires n>0")
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    half = z * ((p * (1.0 - p) / n + z2 / (4.0 * n * n)) ** 0.5) / den
    return max(0.0, center - half), min(1.0, center + half)


def rate_block(k: int, n: int, *, checked: bool) -> dict[str, Any]:
    if not checked or n <= 0:
        return {
            "status": "NOT-CHECKED",
            "numerator": k,
            "denominator": n,
            "rate": None,
            "interval": None,
        }
    lo, hi = wilson_interval(k, n)
    return {
        "status": "MEASURED",
        "numerator": k,
        "denominator": n,
        "rate": k / n,
        "interval": {
            "method": "wilson",
            "confidence": 0.95,
            "lower": lo,
            "upper": hi,
        },
    }


def promote_decision(
    fp: dict[str, Any],
    fn: dict[str, Any],
    n_good: int,
    n_bad: int,
    min_sample: int = MIN_SAMPLE,
) -> dict[str, Any]:
    if n_bad < 1:
        return {
            "decision": "NOT-CHECKED",
            "threshold": None,
            "reason": "no known-bad fixture; false-negative rate unmeasurable",
        }
    if n_good < min_sample or n_bad < min_sample:
        return {
            "decision": "SAMPLE-TOO-SMALL",
            "threshold": None,
            "reason": (
                f"n_good={n_good} n_bad={n_bad} below min_sample_per_class={min_sample}; "
                "threshold not assigned and not rounded"
            ),
        }
    threshold = {
        "false_positive_wilson95_upper_max": FP_BUDGET,
        "false_negative_wilson95_upper_max": FN_BUDGET,
        "min_sample_per_class": min_sample,
    }
    fp_hi = fp["interval"]["upper"]
    fn_hi = fn["interval"]["upper"]
    if fp_hi <= FP_BUDGET and fn_hi <= FN_BUDGET:
        return {"decision": "PROMOTE", "threshold": threshold, "reason": "both Wilson uppers inside budget"}
    return {
        "decision": "HOLD",
        "threshold": threshold,
        "reason": f"wilson upper fp={fp_hi:.4f} fn={fn_hi:.4f} exceeds budget",
    }


def _run_gate(
    gate_id: str,
    rows: list[dict[str, Any]],
    seed: int,
    always_accept: str | None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    order = list(range(len(rows)))
    rng.shuffle(order)
    fp_n = fn_n = fp_k = fn_k = 0
    observations: list[dict[str, Any]] = []
    for idx in order:
        row = rows[idx]
        fired = evaluate(gate_id, row["payload"], always_accept=always_accept)
        expect = bool(row["expect_fire"])
        if not expect:
            fp_n += 1
            if fired:
                fp_k += 1
        else:
            fn_n += 1
            if not fired:
                fn_k += 1
        observations.append(
            {
                "fixture_id": row["id"],
                "label": row["label"],
                "expect_fire": expect,
                "fired": fired,
                "error": (fired and not expect) or ((not fired) and expect),
            }
        )
    fp = rate_block(fp_k, fp_n, checked=fp_n > 0)
    fn = rate_block(fn_k, fn_n, checked=fn_n > 0)
    promote = promote_decision(fp, fn, fp_n, fn_n)
    blob = json.dumps(
        [{"i": o["fixture_id"], "f": o["fired"]} for o in observations],
        sort_keys=True,
    )
    return {
        "id": gate_id,
        "source_module": source_module(gate_id),
        "n_known_good": fp_n,
        "n_known_bad": fn_n,
        "known_bad_exercised": fn_n > 0,
        "false_positive": fp,
        "false_negative": fn,
        "promote": promote,
        "observation_fingerprint": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "observations": observations,
    }


def compute(
    *,
    seed: int = DEFAULT_SEED,
    always_accept: str | None = None,
    include_observations: bool = False,
) -> dict[str, Any]:
    catalog = load_all()
    gates = []
    obs_count = 0
    for gid in GATE_ORDER:
        row = _run_gate(gid, catalog[gid], seed, always_accept)
        obs_count += len(row["observations"])
        if not include_observations:
            row = {k: v for k, v in row.items() if k != "observations"}
        gates.append(row)

    drift_rows = catalog["drift_detector"]
    tiny_good = [r for r in drift_rows if r["label"] == "good"][:3]
    tiny_bad = [r for r in drift_rows if r["label"] == "bad"][:3]
    tiny = _run_gate("drift_detector", tiny_good + tiny_bad, seed, always_accept)
    control = {
        "id": "drift_detector_undersized_slice",
        "source_gate": "drift_detector",
        "n_known_good": tiny["n_known_good"],
        "n_known_bad": tiny["n_known_bad"],
        "false_positive": tiny["false_positive"],
        "false_negative": tiny["false_negative"],
        "decision": tiny["promote"]["decision"],
        "promote_threshold": tiny["promote"]["threshold"],
        "flag": tiny["promote"]["reason"],
    }
    return {
        "seed": seed,
        "always_accept": always_accept,
        "min_sample_per_class": MIN_SAMPLE,
        "gates": gates,
        "sample_too_small_control": control,
        "n_observations": obs_count,
    }


def rates_signature(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed": doc["seed"],
        "gates": [
            {
                "id": g["id"],
                "fp": [
                    g["false_positive"]["numerator"],
                    g["false_positive"]["denominator"],
                    g["false_positive"]["rate"],
                    (g["false_positive"]["interval"] or {}).get("upper"),
                ],
                "fn": [
                    g["false_negative"]["numerator"],
                    g["false_negative"]["denominator"],
                    g["false_negative"]["rate"],
                    (g["false_negative"]["interval"] or {}).get("upper"),
                ],
                "fingerprint": g["observation_fingerprint"],
                "decision": g["promote"]["decision"],
            }
            for g in doc["gates"]
        ],
        "control_decision": doc["sample_too_small_control"]["decision"],
        "control_threshold": doc["sample_too_small_control"]["promote_threshold"],
    }
