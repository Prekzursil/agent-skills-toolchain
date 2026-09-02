#!/usr/bin/env python3
"""Probe 2: K-by-severity plus honest single-class output.

Mechanically independent of probe 1:
  * content-sha256 collapse of four byte-identical mirrors with NO derived_from
  * both-states on P0 (three independent classes SATISFIED vs one-class INSUFFICIENT)
  * P3 single independent class is allowed (K=1) without padding
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diversity as D  # noqa: E402

RAW = HERE / "probe2-severity-honest-single.raw.json"


def main() -> int:
    fail: list[str] = []

    three = D.evaluate(D.corpus_three_independent_classes())
    if three["distinct_class_count"] != 3:
        fail.append(f"three-cls:{three['distinct_class_count']}")
    if three["diversity_status"] != "SATISFIED":
        fail.append(f"three-status:{three['diversity_status']}")
    if three["verdict"] != "CONFIRMED":
        fail.append(f"three-verdict:{three['verdict']}")
    if three["honest_output"] != "MULTI-CLASS":
        fail.append(f"three-honest:{three['honest_output']}")
    if three["required_k"] != 3:
        fail.append(f"three-k:{three['required_k']}")

    padded = D.evaluate(D.corpus_four_retellings_of_one_vendor_post())
    if padded["distinct_class_count"] != 1:
        fail.append(f"padded-cls:{padded['distinct_class_count']}")
    if padded["diversity_status"] != "INSUFFICIENT":
        fail.append(f"padded-status:{padded['diversity_status']}")
    if padded["honest_output"] != "SINGLE-CLASS":
        fail.append(f"padded-honest:{padded['honest_output']}")
    if padded["verdict"] == "CONFIRMED":
        fail.append("padded-confirmed")
    if padded["confidence"] != "remote":
        fail.append(f"padded-confidence:{padded['confidence']}")
    if padded["padding_refused"] is not True:
        fail.append("padded-not-refused")

    p3 = D.evaluate(D.corpus_p3_single_independent())
    if p3["required_k"] != 1:
        fail.append(f"p3-k:{p3['required_k']}")
    if p3["diversity_status"] != "SATISFIED":
        fail.append(f"p3-status:{p3['diversity_status']}")
    if p3["honest_output"] != "SINGLE-CLASS":
        fail.append(f"p3-honest:{p3['honest_output']}")
    if p3["verdict"] != "CONFIRMED":
        fail.append(f"p3-verdict:{p3['verdict']}")
    # almost-certain was requested; P3 single-class is capped at likely
    if p3["confidence"] != "likely":
        fail.append(f"p3-confidence:{p3['confidence']}")

    mirrors = D.corpus_byte_identical_mirrors()
    content_only = D.collapse_sources(mirrors["sources"], use_graph=False, use_content=True)
    graph_only = D.collapse_sources(mirrors["sources"], use_graph=True, use_content=False)
    if content_only["distinct_class_count"] != 1:
        fail.append(f"mirrors-content-cls:{content_only['distinct_class_count']}")
    if content_only["collapsed_origin_count"] != 1:
        fail.append(f"mirrors-content-origins:{content_only['collapsed_origin_count']}")
    # Different URLs, no derived_from: graph-only must NOT collapse them.
    if graph_only["distinct_class_count"] != 4:
        fail.append(f"mirrors-graph-should-stay-four:{graph_only['distinct_class_count']}")
    if content_only["naive_declared_class_count"] != 4:
        fail.append(f"mirrors-naive:{content_only['naive_declared_class_count']}")

    scored_mirrors = D.evaluate(mirrors, use_graph=False, use_content=True)
    if scored_mirrors["honest_output"] != "SINGLE-CLASS":
        fail.append(f"mirrors-honest:{scored_mirrors['honest_output']}")
    if scored_mirrors["diversity_status"] != "INSUFFICIENT":
        fail.append(f"mirrors-status:{scored_mirrors['diversity_status']}")

    # Owner waiver is the only way to lower K; missing owner_id must refuse.
    waived = dict(D.corpus_p3_single_independent())
    waived["severity"] = "P1"
    waived["id"] = "RES-0189-waiver-missing-owner"
    waived["owner_waiver"] = {"named_k": 1}
    try:
        D.evaluate(waived)
        fail.append("waiver-without-owner-accepted")
    except ValueError as exc:
        if "owner_id" not in str(exc):
            fail.append(f"waiver-error:{exc}")

    both_states = {
        "positive_three_independent_p0_satisfied": three["diversity_status"] == "SATISFIED",
        "negative_four_retellings_p0_insufficient": padded["diversity_status"] == "INSUFFICIENT",
    }
    if not all(both_states.values()):
        fail.append("both-states-failed")

    payload = {
        "probe": "probe2_severity_honest_single",
        "k_by_severity": D.K_BY_SEVERITY,
        "three_independent": {
            "distinct_class_count": three["distinct_class_count"],
            "required_k": three["required_k"],
            "diversity_status": three["diversity_status"],
            "verdict": three["verdict"],
            "honest_output": three["honest_output"],
            "confidence": three["confidence"],
        },
        "four_retellings_p0": {
            "distinct_class_count": padded["distinct_class_count"],
            "required_k": padded["required_k"],
            "diversity_status": padded["diversity_status"],
            "verdict": padded["verdict"],
            "honest_output": padded["honest_output"],
            "confidence": padded["confidence"],
        },
        "p3_single_independent": {
            "distinct_class_count": p3["distinct_class_count"],
            "required_k": p3["required_k"],
            "diversity_status": p3["diversity_status"],
            "verdict": p3["verdict"],
            "honest_output": p3["honest_output"],
            "confidence": p3["confidence"],
        },
        "byte_identical_mirrors_content_signal": {
            "distinct_class_count": content_only["distinct_class_count"],
            "graph_only_distinct_class_count": graph_only["distinct_class_count"],
            "naive_declared_class_count": content_only["naive_declared_class_count"],
            "diversity_status": scored_mirrors["diversity_status"],
            "honest_output": scored_mirrors["honest_output"],
        },
        "both_states": both_states,
        "fail": fail,
        "pass": not fail,
    }
    RAW.write_text(D.dumps(payload), encoding="utf-8")
    print(
        "p0_three={0}/{1} p0_padded={2}/{3} p3={4}/{5} "
        "mirrors_content={6} mirrors_graph={7}".format(
            three["diversity_status"],
            three["distinct_class_count"],
            padded["diversity_status"],
            padded["distinct_class_count"],
            p3["diversity_status"],
            p3["distinct_class_count"],
            content_only["distinct_class_count"],
            graph_only["distinct_class_count"],
        )
    )
    if fail:
        print("FAILED:RES-0189-probe2 " + ",".join(fail))
        return 1
    print(
        "BOTH-STATES: P0 with three independent classes SATISFIED; "
        "P0 with four restatements of one origin INSUFFICIENT SINGLE-CLASS"
    )
    print("SUCCESS:RES-0189-probe2 severity-k honest-single content-hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
