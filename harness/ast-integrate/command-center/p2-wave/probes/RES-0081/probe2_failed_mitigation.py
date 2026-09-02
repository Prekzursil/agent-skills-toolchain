#!/usr/bin/env python3
"""Probe 2: failed-mitigation control, partitioned reviewers, E3-without-baseline.

Catalog tests_required control: report at least one study whose mitigation failed
or did not replicate. Reviewer_requirement: two independent reviewers with
PARTITIONED evidence (disjoint source halves; not two same-vendor readers of
the same papers).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from check import (  # noqa: E402
    baseline_stripped_mutant,
    classify_missing_baseline,
    failed_mitigations,
    load_artifact,
    mitigations,
    promoted_mechanisms,
    promotable,
    reviewer_partitions,
)


def main() -> int:
    doc = load_artifact()
    rows = mitigations(doc)
    failed = failed_mitigations(rows)
    extra = doc.get("failed_mitigations") or []
    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, dict):
                failed.append(item)
    if len(failed) < 1:
        print("FAILED:RES-0081-probe2 no failed mitigation")
        return 1
    named = []
    for f in failed:
        sid = str(f.get("id") or f.get("study_id") or "").strip()
        why = str(f.get("why") or f.get("note") or f.get("result") or "").strip()
        if not sid or not why:
            print("FAILED:RES-0081-probe2 failed mitigation missing study/why", f)
            return 1
        named.append(sid)

    # At least one named failure must be an actual published miss, not a paraphrase.
    must = {
        "wei-2023-flan-palm-8b-addition",
        "perez-2022-rlhf-does-not-remove",
        "laban-2023-single-task-finetune",
        "laban-2023-filter-did-not-replicate-wei",
        "sharma-2023-claude2-pm-rl-increases",
    }
    if not (must & set(named)):
        print(f"FAILED:RES-0081-probe2 failed ids not in published set {named}")
        return 1

    revs, err = reviewer_partitions(doc)
    if err:
        print("FAILED:RES-0081-probe2 partition", err)
        return 1

    # Negative control: stripping baselines must zero promotions (E3, not promote).
    mutant = baseline_stripped_mutant(doc)
    try:
        promoted_mut = promoted_mechanisms(mutant)
    except SystemExit as exc:
        # promoted=true with empty baseline is a detector fire — that is the green path.
        promoted_mut = None
        fired = str(exc)
        if "missing baseline" not in fired:
            print("FAILED:RES-0081-probe2 unexpected mutant error", fired)
            return 1
    if promoted_mut is not None and len(promoted_mut) != 0:
        print(f"FAILED:RES-0081-probe2 mutant still promoted {len(promoted_mut)}")
        return 1

    headline = {
        "effect_size": "46% of answers flipped when challenged",
        "baseline": "",
        "study_id": "laban-2023-headline-only",
    }
    if promotable(headline):
        print("FAILED:RES-0081-probe2 headline without baseline promoted")
        return 1
    if classify_missing_baseline(headline) != "E3":
        print("FAILED:RES-0081-probe2 missing baseline not E3")
        return 1

    live = promoted_mechanisms(doc)
    if len(live) < 3:
        print("FAILED:RES-0081-probe2 live promoted too few")
        return 1

    print(
        json.dumps(
            {
                "failed_mitigations": named,
                "reviewer_ids": [r.get("reviewer_id") for r in revs],
                "vendors": [r.get("vendor") for r in revs],
                "partitions": [r.get("source_partition") or r.get("partition") for r in revs],
                "headline_without_baseline_promotable": False,
                "baseline_stripped_promoted": 0,
            },
            indent=1,
        )
    )
    print("SUCCESS:RES-0081-probe2 failed-mitigation partition E3-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
