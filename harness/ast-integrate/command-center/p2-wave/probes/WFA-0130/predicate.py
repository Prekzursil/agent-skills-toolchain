"""Frozen WFA-0130 fusion-acceptance predicate (the pin body).

Four metrics on [0, 1], higher-is-better. Stage count is recorded on arms
and is excluded from the numeric ACCEPT/REJECT rule.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

METRIC_IDS = ("correctness", "coverage", "recovery", "usability")

PREDICATE: dict[str, Any] = {
    "schema_version": 1,
    "metric_ids": list(METRIC_IDS),
    "direction": "higher_is_better",
    "scale": [0.0, 1.0],
    "minimum_effect_size": 0.05,
    "noninferiority_margin": 0.02,
    "complement_recall_minimum": 0.05,
    "estimators": {
        "correctness": {
            "id": "correctness",
            "input": "oracle_pass",
            "estimator": "mean",
            "formula": "C = (1/n) * sum_i 1[oracle_pass_i]",
        },
        "coverage": {
            "id": "coverage",
            "input": "attempted",
            "estimator": "mean",
            "formula": "V = (1/n) * sum_i 1[attempted_i]",
        },
        "recovery": {
            "id": "recovery",
            "input": "failure_event, recovered",
            "estimator": "conditional_mean_or_vacuous_one",
            "formula": (
                "R = 1.0 if n_fail==0 else "
                "(1/n_fail) * sum_i 1[recovered_i | failure_event_i]"
            ),
            "vacuous_note": (
                "R=1.0 when no failure events occurred. Omitting failure "
                "events to inflate R is a WFA-0131 gaming vector; n_fail is recorded."
            ),
        },
        "usability": {
            "id": "usability",
            "input": "schema_valid_complete, human_interventions",
            "estimator": "mean",
            "formula": (
                "U = (1/n) * sum_i 1[schema_valid_complete_i "
                "and human_interventions_i==0]"
            ),
        },
    },
    "excluded_from_predicate": [
        "stage_count",
        "token_cost",
        "wall_clock",
        "retry_count",
    ],
    "decision_rule": {
        "accept_iff": (
            "for every source S: noninferior(fusion, S) AND "
            "(outperform(fusion, S) OR complement(fusion, S))"
        ),
        "outperform": (
            "exists metric m: delta(m, S) >= minimum_effect_size"
        ),
        "complement": (
            "complement_recall(S) >= complement_recall_minimum"
        ),
        "noninferior": (
            "for all metrics m: delta(m, S) >= -noninferiority_margin"
        ),
        "complement_recall": (
            "count(fusion.oracle_pass and not source.oracle_pass) / "
            "max(1, count(not source.oracle_pass))"
        ),
        "delta": "metric(fusion, m) - metric(source, m)",
        "tie_breaks": [
            "material_regression_rejects (any delta < -noninferiority_margin vs any source)",
            "when both outperform and complement fire vs a source, label OUTPERFORM",
            "stage_count never breaks ties and is not a metric",
            "all |delta| < MES and complement_recall < minimum rejects (not material)",
        ],
    },
    "n_matched_cases_required": 1,
}


def canonical_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_predicate(predicate: dict[str, Any] | None = None) -> str:
    body = predicate if predicate is not None else PREDICATE
    return hashlib.sha256(canonical_dumps(body).encode("utf-8")).hexdigest()


def metric_values(arm: dict[str, Any]) -> dict[str, float]:
    cases = list(arm.get("cases") or [])
    n = len(cases)
    if n < 1:
        raise ValueError("arm has no matched cases")
    correctness = sum(1.0 if c.get("oracle_pass") else 0.0 for c in cases) / n
    coverage = sum(1.0 if c.get("attempted") else 0.0 for c in cases) / n
    fails = [c for c in cases if c.get("failure_event")]
    if not fails:
        recovery = 1.0
    else:
        recovery = sum(1.0 if c.get("recovered") else 0.0 for c in fails) / len(fails)
    usability = (
        sum(
            1.0
            if (c.get("schema_valid_complete") and int(c.get("human_interventions") or 0) == 0)
            else 0.0
            for c in cases
        )
        / n
    )
    return {
        "correctness": correctness,
        "coverage": coverage,
        "recovery": recovery,
        "usability": usability,
        "n": float(n),
        "n_fail": float(len(fails)),
    }


def complement_recall(fusion: dict[str, Any], source: dict[str, Any]) -> float:
    f_cases = list(fusion.get("cases") or [])
    s_cases = list(source.get("cases") or [])
    if len(f_cases) != len(s_cases) or not f_cases:
        raise ValueError("fusion and source must share a matched case vector")
    source_fails = 0
    recovered = 0
    for fc, sc in zip(f_cases, s_cases):
        if not sc.get("oracle_pass"):
            source_fails += 1
            if fc.get("oracle_pass"):
                recovered += 1
    if source_fails == 0:
        return 0.0
    return recovered / source_fails


def _relation(
    fusion: dict[str, Any],
    source: dict[str, Any],
    predicate: dict[str, Any],
) -> dict[str, Any]:
    mes = float(predicate["minimum_effect_size"])
    margin = float(predicate["noninferiority_margin"])
    cmin = float(predicate["complement_recall_minimum"])
    fm = metric_values(fusion)
    sm = metric_values(source)
    deltas = {m: float(fm[m]) - float(sm[m]) for m in METRIC_IDS}
    noninferior = all(d >= -margin for d in deltas.values())
    outperform = any(d >= mes for d in deltas.values()) and noninferior
    crecall = complement_recall(fusion, source)
    complement = (crecall >= cmin) and noninferior
    if not noninferior:
        label = "REGRESS"
        ok = False
    elif outperform:
        label = "OUTPERFORM"
        ok = True
    elif complement:
        label = "COMPLEMENT"
        ok = True
    else:
        label = "FAIL"
        ok = False
    return {
        "source_id": source.get("arm_id"),
        "fusion_metrics": {m: fm[m] for m in METRIC_IDS},
        "source_metrics": {m: sm[m] for m in METRIC_IDS},
        "deltas": deltas,
        "noninferior": noninferior,
        "outperform": outperform,
        "complement": complement,
        "complement_recall": crecall,
        "label": label,
        "beats_or_complements": ok,
        "fusion_stage_count": fusion.get("stage_count"),
        "source_stage_count": source.get("stage_count"),
        "stage_count_used": False,
    }


def decide(
    fusion: dict[str, Any],
    sources: list[dict[str, Any]],
    predicate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pred = predicate if predicate is not None else PREDICATE
    if len(sources) < 1:
        raise ValueError("at least one source is required")
    per = [_relation(fusion, src, pred) for src in sources]
    accept = all(row["beats_or_complements"] for row in per)
    return {
        "decision": "ACCEPT" if accept else "REJECT",
        "per_source": per,
        "n_sources": len(per),
        "predicate_sha256": digest_predicate(pred),
        "stage_count_excluded": True,
        "fusion_stage_count": fusion.get("stage_count"),
    }
