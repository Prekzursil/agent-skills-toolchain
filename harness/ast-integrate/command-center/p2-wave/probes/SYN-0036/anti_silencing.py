#!/usr/bin/env python3
"""Anti-silencing guard: weighting must not remove or downrank a finding."""
from __future__ import annotations


def severity_rank(findings):
    ordered = sorted(
        findings,
        key=lambda f: (int(f["severity"]), str(f["finding_id"])),
    )
    return [str(f["finding_id"]) for f in ordered]


def naive_weight_rank(findings, weights):
    def key(f):
        w = weights.get(str(f["producer_id"]))
        numeric = float(w) if w is not None else 0.0
        return (-numeric, str(f["finding_id"]))

    return [str(f["finding_id"]) for f in sorted(findings, key=key)]


def apply_weights(findings, weights):
    before_ids = [str(f["finding_id"]) for f in findings]
    before_set = set(before_ids)
    attached = []
    for f in findings:
        pid = str(f["producer_id"])
        row = dict(f)
        row["reliability_weight"] = weights.get(pid)
        row["weight_used_for_rank"] = False
        attached.append(row)
    after_set = {str(f["finding_id"]) for f in attached}
    removed = sorted(before_set - after_set)
    ranked = severity_rank(attached)
    naive = naive_weight_rank(findings, weights)
    sev_pos = {fid: i for i, fid in enumerate(ranked)}
    naive_pos = {fid: i for i, fid in enumerate(naive)}
    would_downrank = [fid for fid in ranked if naive_pos[fid] > sev_pos[fid]]
    guarded_ok = ranked == severity_rank(findings) and not removed
    return {
        "downranked_by_weight": [],
        "findings": attached,
        "findings_after": ranked,
        "findings_before": list(before_ids),
        "naive_weight_order": naive,
        "naive_would_downrank": would_downrank,
        "passed": guarded_ok,
        "rank_key": "severity then finding_id; producer weight is metadata only",
        "ranked_ids": ranked,
        "removed": removed,
    }
