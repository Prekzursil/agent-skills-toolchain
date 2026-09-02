#!/usr/bin/env python3
"""Probe 1: negative control — four sources, one vendor-post origin.

The rule must report ONE class, not four. A metric that counts unique URLs
or unique declared-class labels is the padding behaviour this unit forbids.
Collapse signal is the derived_from / upstream_origin graph (bodies differ).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diversity as D  # noqa: E402

RAW = HERE / "probe1-shared-origin-collapse.raw.json"


def main() -> int:
    conclusion = D.corpus_four_retellings_of_one_vendor_post()
    # Graph-only: restatement bodies are different, so content-hash must not
    # be the thing that makes this test pass.
    collapsed = D.collapse_sources(conclusion["sources"], use_graph=True, use_content=False)
    scored = D.evaluate(conclusion, use_graph=True, use_content=False)
    naive_cls = collapsed["naive_declared_class_count"]
    naive_url = collapsed["naive_url_count"]
    n_cls = collapsed["distinct_class_count"]
    n_origin = collapsed["collapsed_origin_count"]
    fail: list[str] = []
    if len(conclusion["sources"]) != 4:
        fail.append(f"planted-source-count:{len(conclusion['sources'])}")
    if naive_cls != 4:
        fail.append(f"naive-declared-not-four:{naive_cls}")
    if naive_url != 4:
        fail.append(f"naive-url-not-four:{naive_url}")
    if n_cls != 1:
        fail.append(f"rule-classes-not-one:{n_cls}")
    if n_origin != 1:
        fail.append(f"rule-origins-not-one:{n_origin}")
    if scored["honest_output"] != "SINGLE-CLASS":
        fail.append(f"honest:{scored['honest_output']}")
    if scored["padding_refused"] is not True:
        fail.append("padding-not-refused")
    if scored["diversity_status"] != "INSUFFICIENT":
        fail.append(f"status:{scored['diversity_status']}")
    if scored["verdict"] == "CONFIRMED":
        fail.append("padded-conclusion-confirmed")
    if scored["required_k"] != 3:
        fail.append(f"p0-k:{scored['required_k']}")
    # Content-hash alone must NOT collapse these four (bodies differ) — proves
    # probe 2's content signal is a different mechanism.
    content_only = D.collapse_sources(conclusion["sources"], use_graph=False, use_content=True)
    if content_only["distinct_class_count"] != 4:
        fail.append(
            f"content-only-should-stay-four:{content_only['distinct_class_count']}"
        )

    payload = {
        "probe": "probe1_shared_origin_collapse",
        "conclusion_id": conclusion["id"],
        "raw_source_count": collapsed["raw_source_count"],
        "naive_declared_class_count": naive_cls,
        "naive_url_count": naive_url,
        "distinct_class_count": n_cls,
        "collapsed_origin_count": n_origin,
        "distinct_classes": collapsed["distinct_classes"],
        "origin_groups": collapsed["origin_groups"],
        "honest_output": scored["honest_output"],
        "diversity_status": scored["diversity_status"],
        "verdict": scored["verdict"],
        "confidence": scored["confidence"],
        "content_only_distinct_class_count": content_only["distinct_class_count"],
        "fail": fail,
        "pass": not fail,
    }
    RAW.write_text(D.dumps(payload), encoding="utf-8")
    print(
        "naive_declared={0} naive_url={1} rule_classes={2} rule_origins={3} "
        "honest={4} status={5} verdict={6}".format(
            naive_cls,
            naive_url,
            n_cls,
            n_origin,
            scored["honest_output"],
            scored["diversity_status"],
            scored["verdict"],
        )
    )
    if fail:
        print("FAILED:RES-0189-probe1 " + ",".join(fail))
        return 1
    print(
        "NEGATIVE-CONTROL: four sources descending from one vendor post "
        "report ONE class, not four (declared-class padding refused)"
    )
    print("SUCCESS:RES-0189-probe1 shared-origin collapse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
